"""``pve-osx efi build`` -- assemble a macOS VM's OpenCore EFI folder.

Everything comes from the single checksum-verified OpenCore release archive
(:data:`pve_osx.artifacts.MANIFEST`) -- it already bundles ``Docs/Sample.plist``
(the config template), ``Utilities/macserial`` (prebuilt for Windows/Linux/macOS),
and ``Utilities/macrecovery`` (for a later ``efi recovery`` command). No separate
GenSMBIOS fetch or interactive tool is needed: SMBIOS identity generation is
just ``macserial -g`` plus a random SmUUID/ROM, done directly here.
"""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import typing as _ty
import uuid
import zipfile

from duho import Cli

from .cli import PveOsx, PveOsxCmd


class EfiError(RuntimeError):
    pass


def _macserial_binary_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "macserial.exe"
    if system == "Linux":
        return "macserial.linux"
    return "macserial"  # Darwin


def _extract_opencore(zip_path: str, dest: str) -> str:
    """Extract the OpenCore release zip to ``dest``, returning its path."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    return dest


def generate_smbios(macserial_path: str, model: str) -> "dict[str, _ty.Any]":
    """Generate a fresh SMBIOS identity for ``model`` via the bundled macserial.

    Returns the ``PlatformInfo.Generic`` fields OpenCore expects:
    ``SystemProductName``, ``SystemSerialNumber``, ``MLB``, ``SystemUUID``,
    ``ROM``.
    """
    import subprocess

    out = subprocess.run(
        [macserial_path, "-g", "-m", model, "-n", "1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    line = next(l for l in out.splitlines() if "|" in l)
    serial, mlb = (part.strip() for part in line.split("|", 1))
    return {
        "SystemProductName": model,
        "SystemSerialNumber": serial,
        "MLB": mlb,
        "SystemUUID": str(uuid.uuid4()).upper(),
        "ROM": os.urandom(6),
    }


def patch_config(sample_plist_path: str, out_path: str, smbios: "dict[str, _ty.Any]") -> None:
    """Load ``Sample.plist``, apply ``smbios`` into ``PlatformInfo.Generic``, save to ``out_path``."""
    with open(sample_plist_path, "rb") as f:
        config = plistlib.load(f)
    generic = config.setdefault("PlatformInfo", {}).setdefault("Generic", {})
    generic.update(smbios)
    with open(out_path, "wb") as f:
        plistlib.dump(config, f)


#: Virtio DXE drivers to enable for completeness -- Sample.plist already lists
#: every one of these (they ship in the same OpenCore release, copied into
#: Drivers/ alongside everything else) but with Enabled=False. Flipping them
#: on costs nothing at boot if the corresponding bus isn't actually used (an
#: unused driver just doesn't find a matching PCI device), and means a VM
#: profile can freely use virtio for disk/net/scsi/serial without a second
#: manual step to wire up the matching firmware driver.
VIRTIO_DRIVERS = (
    "VirtioBlkDxe.efi",
    "VirtioNetDxe.efi",
    "VirtioPciDeviceDxe.efi",
    "VirtioScsiDxe.efi",
    "VirtioSerialDxe.efi",
    "Virtio10.efi",
    "VirtioGpuDxe.efi",
)


def enable_drivers(config_path: str, names: "_ty.Sequence[str]" = VIRTIO_DRIVERS) -> None:
    """Flip ``Enabled`` on for the named entries already present in
    ``UEFI.Drivers`` (in-place on the config.plist at ``config_path``)."""
    with open(config_path, "rb") as f:
        config = plistlib.load(f)
    drivers = config.setdefault("UEFI", {}).setdefault("Drivers", [])
    by_path = {d.get("Path"): d for d in drivers if isinstance(d, dict)}
    for name in names:
        if name in by_path:
            by_path[name]["Enabled"] = True
    with open(config_path, "wb") as f:
        plistlib.dump(config, f)


class Efi(PveOsxCmd, Cli):
    """EFI/OpenCore artifact building."""

    _parsername_ = "efi"

    def __call__(self) -> "int | None":
        raise NotImplementedError(self)


PveOsx._register_subcmd_(Efi)


class EfiCmd(PveOsxCmd):
    """Common base for every ``efi`` leaf command."""

    @classmethod
    def _register(cls) -> None:
        Efi._register_subcmd_(cls)


class EfiBuild(EfiCmd):
    """Build an OpenCore EFI folder for a macOS VM: verified OpenCore
    download, a fresh SMBIOS identity, and a patched config.plist."""

    _parsername_ = "build"
    _logger_name_ = "pve_osx.efi"

    out: str = "efi-out"
    "Output directory for the assembled EFI/ folder"
    ("--out", "-o")

    model: str = "MacPro7,1"
    "Mac model to generate an SMBIOS identity for"
    ("--model", "-m")

    opencore_artifact: str = "opencore-1.0.7"
    "Which pinned OpenCore release to use (see pve_osx.artifacts.MANIFEST)"
    ("--opencore",)

    cache_dir: "_ty.Optional[str]" = None
    "Where to cache downloaded artifacts (defaults to a temp dir)"
    ("--cache-dir",)

    def __call__(self) -> "int | None":
        import tempfile

        from . import artifacts

        cache = self.cache_dir or tempfile.mkdtemp(prefix="pve-osx-artifacts-")
        os.makedirs(cache, exist_ok=True)
        zip_path = os.path.join(cache, f"{self.opencore_artifact}.zip")

        self._logger_.info(f"Fetching {self.opencore_artifact} (checksum-verified)...")
        artifacts.fetch(self.opencore_artifact, zip_path)

        extracted = _extract_opencore(zip_path, os.path.join(cache, "opencore"))
        macserial = os.path.join(extracted, "Utilities", "macserial", _macserial_binary_name())
        sample_plist = os.path.join(extracted, "Docs", "Sample.plist")
        if not os.path.exists(macserial) or not os.path.exists(sample_plist):
            raise EfiError(
                f"OpenCore archive layout unexpected -- missing {macserial} or {sample_plist}"
            )

        self._logger_.info(f"Generating SMBIOS identity for {self.model}...")
        smbios = generate_smbios(macserial, self.model)

        efi_out = os.path.abspath(self.out)
        efi_dir = os.path.join(efi_out, "EFI")
        if os.path.isdir(efi_dir):
            shutil.rmtree(efi_dir)
        shutil.copytree(os.path.join(extracted, "X64", "EFI"), efi_dir)

        config_out = os.path.join(efi_dir, "OC", "config.plist")
        patch_config(sample_plist, config_out, smbios)
        enable_drivers(config_out)

        print(f"EFI folder assembled at: {efi_out}")
        print(f"  model:  {smbios['SystemProductName']}")
        print(f"  serial: {smbios['SystemSerialNumber']}")
        print(f"  mlb:    {smbios['MLB']}")
        print(f"  uuid:   {smbios['SystemUUID']}")
        print(
            "next step: write this EFI/ folder onto the VM's EFI disk (e.g. via "
            "mtools/mcopy on the Proxmox host) -- pve-osx does not build a FAT/ISO "
            "image for it yet"
        )
        return 0


EfiBuild._register()
