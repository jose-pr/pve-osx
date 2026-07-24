"""``pve-osx vm ...`` -- VM lifecycle and diagnostics commands."""

from __future__ import annotations

import typing as _ty

import duho
from duho import Cli

from .cli import PveOsx, PveOsxCmd
from .common import PveConnectionArgs

# Below this elapsed time, high CPU is just "still booting" -- not yet
# suspicious. Tuned against the VM 107 incident (livelocked for 1d15h at
# ~20% progress); a real install can legitimately run for tens of minutes.
_LIVELOCK_ELAPSED_THRESHOLD_S = 20 * 60
_LIVELOCK_CPU_THRESHOLD_PERCENT = 50.0


class Vm(PveOsxCmd, Cli):
    """VM lifecycle and diagnostics."""

    _parsername_ = "vm"

    def __call__(self) -> "int | None":
        raise NotImplementedError(self)


PveOsx._register_subcmd_(Vm)


class VmCmd(PveConnectionArgs):
    """Common base for every ``vm`` leaf command."""

    @classmethod
    def _register(cls) -> None:
        Vm._register_subcmd_(cls)


class VmList(VmCmd):
    """List VMs on the node."""

    _parsername_ = "list"

    def __call__(self) -> "int | None":
        pve = self.pve()
        for v in sorted(pve.list_vms(), key=lambda v: v["vmid"]):
            print(f"{v['vmid']}\t{v['name']}\t{v['status']}\t{v.get('mem', 0) // (1024*1024)}MB")
        return 0


VmList._register()


class VmDiagnose(VmCmd):
    """Diagnose a VM's boot/install progress: status, config, a console
    screenshot, and a livelock heuristic for the known kvm-pv-ipi issue."""

    _parsername_ = "diagnose"
    _logger_name_ = "pve_osx.vm"

    vmid: int = 0
    "VM id to diagnose"
    ("vmid",)

    screenshot: "_ty.Optional[str]" = None
    "Save a console screenshot to this path (.ppm written as-is, any other "
    "extension converted via Pillow -- requires the pve-osx[img] extra)"
    ("--screenshot", "-s")

    def __call__(self) -> "int | None":
        pve = self.pve()
        status = pve.status(self.vmid)
        config = pve.get_config(self.vmid)
        print(f"status: {status['status']} (qmpstatus={status.get('qmpstatus')})")

        args = config.get("args", "")
        has_ipi_fix = "-kvm-pv-ipi" in args
        cores = int(config.get("cores", 1))

        with self.ssh() as ssh:
            proc = ssh.vm_process_status(self.vmid)
            if proc is not None:
                elapsed_m = proc.elapsed_seconds // 60
                print(
                    f"host process: pid={proc.pid} cpu={proc.cpu_percent:.0f}% "
                    f"elapsed={elapsed_m}m state={proc.state}"
                )
                if (
                    not has_ipi_fix
                    and cores > 1
                    and proc.elapsed_seconds > _LIVELOCK_ELAPSED_THRESHOLD_S
                    and proc.cpu_percent > _LIVELOCK_CPU_THRESHOLD_PERCENT
                ):
                    print(
                        "WARNING: this looks like the known kvm-pv-ipi livelock -- "
                        f"{cores} vCPUs, {elapsed_m}m elapsed, {proc.cpu_percent:.0f}% "
                        "host CPU, and 'args:' does not disable kvm-pv-ipi. Add "
                        "-kvm-pv-ipi to the CPU flags (pve_osx.profiles.DEFAULT_CPU_FLAGS "
                        "already does this for new VMs) and restart the VM."
                    )
            else:
                print("host process: not running (no pidfile)")

            if self.screenshot:
                data = ssh.screendump(self.vmid)
                self._save_screenshot(data, self.screenshot)
                print(f"screenshot saved: {self.screenshot}")
        return 0

    @staticmethod
    def _save_screenshot(ppm_bytes: bytes, path: str) -> None:
        if path.lower().endswith(".ppm"):
            with open(path, "wb") as f:
                f.write(ppm_bytes)
            return
        try:
            import io as _io

            from PIL import Image
        except ImportError as e:
            raise SystemExit(
                "pve-osx: saving as anything but .ppm needs Pillow "
                "(pip install 'pve-osx[img]'), or pass a .ppm path"
            ) from e
        Image.open(_io.BytesIO(ppm_bytes)).save(path)


VmDiagnose._register()


class VmScreenshot(VmCmd):
    """Save a VM's current console screenshot (shorthand for ``vm diagnose --screenshot``)."""

    _parsername_ = "screenshot"

    vmid: int = 0
    "VM id"
    ("vmid",)

    out: str = "screenshot.png"
    "Output path (.ppm written as-is, anything else converted via Pillow)"
    ("out",)

    def __call__(self) -> "int | None":
        with self.ssh() as ssh:
            data = ssh.screendump(self.vmid)
        VmDiagnose._save_screenshot(data, self.out)
        print(f"screenshot saved: {self.out}")
        return 0


VmScreenshot._register()


class VmCreate(VmCmd):
    """Create a macOS VM from a profile.

    On any failure after the VM is registered, the partially-created VM is
    destroyed before re-raising -- a failed create never leaves an orphaned
    VM behind (closes the "no rollback" finding from the original tool's
    audit).
    """

    _parsername_ = "create"
    _logger_name_ = "pve_osx.vm"

    name: str = ""
    "VM name"
    ("name",)

    macos_version: str = "sequoia"
    "macOS version (used to pick the OpenCore/recovery artifact in a later step)"
    ("--macos-version",)

    cores: int = 4
    "vCPU count (kept conservative by default -- the kvm-pv-ipi bug scales with core count)"
    ("--cores",)

    memory_mb: int = 8192
    "Memory in MB"
    ("--memory",)

    disk_size_gb: int = 80
    "Main disk size in GB"
    ("--disk-size",)

    disk_storage: str = "local-zfs"
    "Storage for the main disk"
    ("--disk-storage",)

    bridge: str = "vmbr0"
    "Network bridge"
    ("--bridge",)

    vlan_tag: "_ty.Optional[int]" = None
    "VLAN tag (optional)"
    ("--vlan",)

    vmid: "_ty.Optional[int]" = None
    "VM id (defaults to the next free id)"
    ("--vmid",)

    disk_bus: str = "nvme0"
    "Disk bus for the main disk (nvme0 -- macOS's native NVMe driver, no kext needed)"
    ("--disk-bus",)

    display: str = "qxl"
    "Display adapter (qxl enables a SPICE console instead of default+noVNC)"
    ("--display",)

    def __call__(self) -> "int | None":
        from .pve import PveError
        from .profiles import MacOSProfile

        profile = MacOSProfile(
            name=self.name,
            macos_version=self.macos_version,
            cores=self.cores,
            memory_mb=self.memory_mb,
            disk_size_gb=self.disk_size_gb,
            disk_storage=self.disk_storage,
            bridge=self.bridge,
            vlan_tag=self.vlan_tag,
            disk_bus=self.disk_bus,
            display=self.display,
        )

        pve = self.pve()

        # Preflight: refuse to even attempt create if the target storage
        # doesn't have room -- closes the "no disk-space preflight" finding.
        status = pve.storage_status(profile.disk_storage)
        needed = profile.disk_size_gb * 1024**3
        if status.available_bytes < needed:
            raise SystemExit(
                f"pve-osx: storage '{profile.disk_storage}' has "
                f"{status.available_bytes / 1024**3:.1f}GB free, need "
                f"{profile.disk_size_gb}GB -- refusing to create"
            )

        vmid = self.vmid or pve.next_id()
        self._logger_.info(f"Creating VM {vmid} ({profile.name}) on vmid {vmid}")
        try:
            pve.create_vm(
                vmid,
                name=profile.name,
                bios="ovmf",
                machine="q35",
                cores=profile.cores,
                memory=profile.memory_mb,
                numa=1 if profile.numa else 0,
                ostype="other",
                scsihw="virtio-scsi-pci",
                net0=profile.net_config(),
                args=profile.args(),
                vga=profile.display,
                efidisk0=f"{profile.efi_storage}:1,pre-enrolled-keys=0",
                **{
                    profile.disk_bus: (
                        f"{profile.disk_storage}:{profile.disk_size_gb},cache=none,discard=on"
                    )
                },
                boot=f"order={profile.disk_bus}",
            )
        except PveError:
            self._logger_.error(f"create failed, cleaning up VM {vmid}")
            try:
                pve.destroy_vm(vmid)
            except PveError:
                self._logger_.error(
                    f"VM {vmid} may be left half-configured -- destroy_vm cleanup itself failed"
                )
            raise
        print(f"created VM {vmid} ({profile.name})")
        print(
            "note: no EFI/OpenCore artifact or macOS installer media attached yet "
            "-- run 'pve-osx efi build' and attach it before first boot"
        )
        return 0


VmCreate._register()
