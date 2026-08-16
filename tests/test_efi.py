"""Tests for `pve_osx.efi` -- the extraction/permission and macserial paths.

These do not touch the network: they build a tiny stand-in for the OpenCore
release zip and monkeypatch `subprocess.run`.
"""

import os
import stat
import subprocess
import zipfile

import pytest

from pve_osx import efi


def _fake_opencore_zip(path):
    """A minimal stand-in for the OpenCore release archive: just the members
    the exec-bit fix cares about, plus an unrelated file to prove it is not
    chmod'ed indiscriminately."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Utilities/macserial/macserial", "#!/bin/sh\necho stub\n")
        z.writestr("Utilities/macserial/macserial.linux", "#!/bin/sh\necho stub\n")
        z.writestr("Utilities/macserial/macserial.exe", "MZstub")
        z.writestr("Utilities/macserial/README.md", "not a binary\n")
        z.writestr("Docs/Sample.plist", "<plist/>")
    return path


def test_extract_opencore_makes_macserial_executable(tmp_path, monkeypatch):
    """Regression: zipfile.extractall does not restore POSIX permissions, so
    the extracted macserial landed 0644 and `efi build` raised PermissionError
    on every non-Windows host.

    The chmod calls are recorded so this asserts real behavior on Windows too
    (where the exec bit does not exist and st_mode would prove nothing) -- it
    is the Windows-only dev box that let the bug ship in the first place.
    """
    zip_path = _fake_opencore_zip(str(tmp_path / "opencore.zip"))
    dest = str(tmp_path / "extracted")

    calls = []
    real_chmod = os.chmod
    monkeypatch.setattr(
        os, "chmod", lambda p, m, *a, **k: (calls.append((p, m)), real_chmod(p, m))[0]
    )

    efi._extract_opencore(zip_path, dest)

    chmoded = {os.path.basename(p) for p, _ in calls}
    assert chmoded == {"macserial", "macserial.linux", "macserial.exe"}
    assert all(mode == 0o755 for _, mode in calls)
    assert "README.md" not in chmoded

    if os.name != "nt":  # the exec bit only exists here
        for name in ("macserial", "macserial.linux"):
            path = os.path.join(dest, "Utilities", "macserial", name)
            assert stat.S_IMODE(os.stat(path).st_mode) & 0o111, f"{name} not executable"


def test_extract_opencore_tolerates_missing_utilities(tmp_path):
    """An archive without Utilities/macserial/ must not blow up in the chmod
    helper -- the layout check in EfiBuild is what reports that, with a
    useful message."""
    zip_path = str(tmp_path / "empty.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Docs/Sample.plist", "<plist/>")
    dest = str(tmp_path / "extracted")

    assert efi._extract_opencore(zip_path, dest) == dest
    assert efi._restore_macserial_exec_bit(dest) == []


def test_extract_opencore_replaces_existing_dest(tmp_path):
    zip_path = _fake_opencore_zip(str(tmp_path / "opencore.zip"))
    dest = tmp_path / "extracted"
    dest.mkdir()
    (dest / "stale.txt").write_text("should be gone\n")

    efi._extract_opencore(zip_path, str(dest))

    assert not (dest / "stale.txt").exists()
    assert (dest / "Docs" / "Sample.plist").exists()


def test_generate_smbios_parses_serial_and_mlb(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, stdout="C02XXXXXXXXX | C02XXXXXXXXXXXXXX\n", stderr=""
        ),
    )

    smbios = efi.generate_smbios("macserial", "MacPro7,1")

    assert smbios["SystemProductName"] == "MacPro7,1"
    assert smbios["SystemSerialNumber"] == "C02XXXXXXXXX"
    assert smbios["MLB"] == "C02XXXXXXXXXXXXXX"
    assert len(smbios["ROM"]) == 6
    assert smbios["SystemUUID"] == smbios["SystemUUID"].upper()


def test_generate_smbios_surfaces_macserial_stderr(monkeypatch):
    """Regression: check=True + capture_output=True meant a macserial failure
    reached the user as a bare CalledProcessError traceback with the reason
    (in stderr) thrown away."""

    def boom(*a, **k):
        raise subprocess.CalledProcessError(
            1, a[0], output="", stderr="cannot open /dev/urandom\n"
        )

    monkeypatch.setattr(subprocess, "run", boom)

    with pytest.raises(efi.EfiError) as exc:
        efi.generate_smbios("macserial", "MacPro7,1")
    assert "cannot open /dev/urandom" in str(exc.value)
    assert "MacPro7,1" in str(exc.value)


def test_generate_smbios_reports_unrunnable_binary(monkeypatch):
    """The exec-bit bug's own symptom: PermissionError from subprocess must
    come back as an EfiError naming the path, not a bare OSError."""

    def boom(*a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(subprocess, "run", boom)

    with pytest.raises(efi.EfiError) as exc:
        efi.generate_smbios("/tmp/oc/Utilities/macserial/macserial", "MacPro7,1")
    assert "macserial" in str(exc.value)


def test_generate_smbios_rejects_unparseable_output(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, stdout="nothing here\n", stderr=""
        ),
    )

    with pytest.raises(efi.EfiError) as exc:
        efi.generate_smbios("macserial", "MacPro7,1")
    assert "Serial | MLB" in str(exc.value)
