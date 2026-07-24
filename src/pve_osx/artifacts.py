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
