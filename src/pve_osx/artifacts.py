"""Checksum-verified downloads of third-party artifacts (currently: OpenCore).

The original tool's audit finding this closes: it downloaded the OpenCore ISO
over HTTPS but never verified it against anything -- a compromised upstream
release silently becomes every subsequent VM's firmware. Every entry in
:data:`MANIFEST` here is pinned to a specific release/ref with a real sha256
computed from the actual file (not a placeholder); :func:`fetch` refuses to
return unverified or mismatched content.

The single OpenCore release archive already bundles everything else this
package needs -- ``Utilities/macserial`` (prebuilt for Windows/Linux/macOS,
used directly instead of fetching GenSMBIOS as a wrapper around it) and
``Utilities/macrecovery`` -- so there is deliberately no separate manifest
entry for either; fetching the same content from two different pinned refs
would just create a discrepancy risk between them.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import urllib.request


class ChecksumMismatchError(RuntimeError):
    """A downloaded artifact's sha256 did not match its manifest entry."""


@dataclasses.dataclass(frozen=True)
class Artifact:
    url: str
    sha256: str
    size: int


#: Pinned, checksum-verified third-party artifacts. Update deliberately (new
#: URL + a freshly-computed sha256 from the real file), never just relax the
#: check.
MANIFEST: "dict[str, Artifact]" = {
    "opencore-1.0.7": Artifact(
        url="https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.7/OpenCore-1.0.7-RELEASE.zip",
        sha256="2ffab6ebf58c7aefb0bcb3a1a385d207746823d6dd87d44bd666e1286939943e",
        size=10437696,
    ),
    # The four kexts every macOS guest needs -- Sample.plist already lists
    # them (Enabled=True) in Kernel.Add, but the OpenCore release zip does
    # not bundle the actual kext files; they're separate Acidanthera
    # projects with their own release cadence.
    "lilu-1.7.2": Artifact(
        url="https://github.com/acidanthera/Lilu/releases/download/1.7.2/Lilu-1.7.2-RELEASE.zip",
        sha256="53967d7dcfaab01023a33df2e969a89522f13d6654a6a56ac4711b62dabf3ab8",
        size=781360,
    ),
    "virtualsmc-1.3.7": Artifact(
        url="https://github.com/acidanthera/VirtualSMC/releases/download/1.3.7/VirtualSMC-1.3.7-RELEASE.zip",
        sha256="12f1d379969f926306fa92d94ddbf33b32b31176589dc42089d864a26b31b700",
        size=1377786,
    ),
    "whatevergreen-1.7.0": Artifact(
        url="https://github.com/acidanthera/WhateverGreen/releases/download/1.7.0/WhateverGreen-1.7.0-RELEASE.zip",
        sha256="6d6ffe8334ad60f784a662794e67b2560b79d757d506841dc8ca9994ab39979b",
        size=571730,
    ),
    "applealc-1.9.7": Artifact(
        url="https://github.com/acidanthera/AppleALC/releases/download/1.9.7/AppleALC-1.9.7-RELEASE.zip",
        sha256="81a8ba79986130e8c845fff595950226cbc30e588f8d37089e467f776469c29d",
        size=3752348,
    ),
    # Community QEMU guest agent for macOS -- upstream QEMU's own qemu-ga
    # doesn't build/ship for Darwin; see pve_osx.vm's agent-transport note
    # (this agent needs an ISA-serial channel, not Proxmox's default
    # virtio-serial -- vm create sets agent=enabled=1,type=isa for exactly
    # that reason).
    "mac-guest-agent-2.5.6": Artifact(
        url="https://github.com/mav2287/mac-guest-agent/releases/download/v2.5.6/mac-guest-agent",
        sha256="fa501be5d8707b92b6b112d359007bb12163d5e95b3931f1fd7307b42afc03aa",
        size=531304,
    ),
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, dest: str, *, force: bool = False) -> str:
    """Download ``MANIFEST[name]`` to ``dest``, verifying its sha256.

    Raises :class:`ChecksumMismatchError` (and deletes the bad file) on a
    mismatch -- never returns a path to unverified content. Skips the
    download if ``dest`` already exists and already matches the checksum
    (idempotent re-runs); pass ``force=True`` to re-download regardless.
    """
    artifact = MANIFEST[name]
    if not force and os.path.exists(dest) and _sha256(dest) == artifact.sha256:
        return dest

    tmp = f"{dest}.part"
    urllib.request.urlretrieve(artifact.url, tmp)
    actual = _sha256(tmp)
    if actual != artifact.sha256:
        os.remove(tmp)
        raise ChecksumMismatchError(
            f"{name}: expected sha256 {artifact.sha256}, got {actual} -- refusing to use it"
        )
    os.replace(tmp, dest)
    return dest
