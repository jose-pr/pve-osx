"""macOS VM profile definitions and hardened QEMU CPU-flag defaults.

The default CPU-flag preset bakes in a fix discovered diagnosing a real hung
install (VM 107 on asgard-borr, 2026-07-23): ``kvm-pv-ipi`` left enabled on a
16-vCPU macOS guest causes a livelock where vCPUs spin at high CPU while the
installer barely advances (that VM sat at ~20% progress for 1 day 15 hours).
Disabling it (``-kvm-pv-ipi``) is a known fix for multi-vCPU macOS guests under
KVM. Note the flag name uses hyphens (``kvm-pv-ipi``), not underscores --
QEMU rejects the underscore form outright for this specific flag even though
the older ``kvm_pv_unhalt``/``kvm_pv_eoi`` flags accept either.
"""

from __future__ import annotations

import dataclasses
import typing as _ty

#: The Apple SMC OSK string used by every OpenCore/Hackintosh guide -- a
#: public constant embedded in every real macOS installation, not a secret.
APPLE_SMC_OSK = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"

#: Hardened default CPU flags for a macOS guest. Callers may extend/override
#: via :attr:`MacOSProfile.extra_cpu_flags`, but should not need to.
DEFAULT_CPU_FLAGS: "tuple[str, ...]" = (
    "kvm=on",
    "vendor=GenuineIntel",
    "+kvm_pv_unhalt",
    "+kvm_pv_eoi",
    "-kvm-pv-ipi",  # the fix: see module docstring
    "+hypervisor",
    "+invtsc",
)


def cpu_arg(flags: "_ty.Sequence[str]" = DEFAULT_CPU_FLAGS, *, base: str = "host") -> str:
    """Render the ``-cpu`` QEMU argument value for a macOS guest."""
    return ",".join((base, *flags))


def qemu_args(smbios_type: int = 2, osk: str = APPLE_SMC_OSK) -> str:
    """Render the ``args:`` line every macOS guest needs (AppleSMC + USB + CPU)."""
    return (
        f'-device isa-applesmc,osk="{osk}" '
        f"-smbios type={smbios_type} "
        "-device qemu-xhci -device usb-kbd -device usb-tablet "
        "-global nec-usb-xhci.msi=off "
        "-global ICH9-LPC.acpi-pci-hotplug-with-bridge-support=off "
        f"-cpu {cpu_arg()}"
    )


@dataclasses.dataclass
class MacOSProfile:
    """A macOS VM's shape: identity, resources, disks, and CPU-flag preset.

    Only ``name`` and ``macos_version`` are required; everything else has a
    sane default. ``extra_cpu_flags`` are appended after :data:`DEFAULT_CPU_FLAGS`
    (later flags win on conflict, matching QEMU's own last-one-wins semantics).
    """

    name: str
    macos_version: str  # e.g. "sequoia", "sonoma" -- used to pick the OpenCore/recovery artifact
    cores: int = 4  # deliberately conservative default; the kvm-pv-ipi bug scales with vCPU count
    memory_mb: int = 8192
    disk_size_gb: int = 80
    disk_storage: str = "local-zfs"
    efi_storage: str = "local-zfs"
    bridge: str = "vmbr0"
    vlan_tag: "_ty.Optional[int]" = None
    extra_cpu_flags: "tuple[str, ...]" = ()

    @property
    def cpu_flags(self) -> "tuple[str, ...]":
        return DEFAULT_CPU_FLAGS + self.extra_cpu_flags

    def args(self) -> str:
        return qemu_args() if not self.extra_cpu_flags else (
            qemu_args().rsplit("-cpu ", 1)[0] + f"-cpu {cpu_arg(self.cpu_flags)}"
        )

    def net_config(self) -> str:
        net = f"vmxnet3,bridge={self.bridge}"
        if self.vlan_tag is not None:
            net += f",tag={self.vlan_tag}"
        return net
