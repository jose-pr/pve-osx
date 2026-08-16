"""Tests for `pve_osx.artifacts.fetch` -- no network: `urlretrieve` is
monkeypatched to write whatever the case under test needs."""

import hashlib
import os

import pytest

from pve_osx import artifacts


def _artifact_for(payload: bytes) -> artifacts.Artifact:
    return artifacts.Artifact(
        url="https://example.invalid/thing.zip",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


@pytest.fixture
def manifest_entry(monkeypatch):
    """Install a single fake manifest entry and a urlretrieve that writes
    `served`, returning a setter so a test can serve the wrong bytes."""
    state = {"served": b""}

    def serve(payload: bytes) -> artifacts.Artifact:
        artifact = _artifact_for(payload)
        state["served"] = payload
        monkeypatch.setitem(artifacts.MANIFEST, "fixture-1.0", artifact)
        return artifact

    def fake_urlretrieve(url, filename):
        with open(filename, "wb") as f:
            f.write(state["served"])
        return filename, None

    monkeypatch.setattr(artifacts.urllib.request, "urlretrieve", fake_urlretrieve)
    serve.set_served = lambda payload: state.__setitem__("served", payload)
    return serve


def test_fetch_writes_verified_content(manifest_entry, tmp_path):
    manifest_entry(b"good payload")
    dest = str(tmp_path / "thing.zip")

    assert artifacts.fetch("fixture-1.0", dest) == dest
    with open(dest, "rb") as f:
        assert f.read() == b"good payload"
    assert not os.path.exists(dest + ".part")


def test_fetch_rejects_wrong_size_before_hashing(manifest_entry, tmp_path, monkeypatch):
    """`Artifact.size` used to be declared and never checked. A truncated
    download must abort on the stat, without hashing the file at all."""
    manifest_entry(b"good payload")
    manifest_entry.set_served(b"short")
    dest = str(tmp_path / "thing.zip")

    hashed = []
    real_sha256 = artifacts._sha256
    monkeypatch.setattr(
        artifacts, "_sha256", lambda p: (hashed.append(p), real_sha256(p))[1]
    )

    with pytest.raises(artifacts.ChecksumMismatchError) as exc:
        artifacts.fetch("fixture-1.0", dest)

    assert "bytes" in str(exc.value)
    assert hashed == [], "size mismatch should abort before hashing"
    assert not os.path.exists(dest + ".part"), "bad download left behind"
    assert not os.path.exists(dest)


def test_fetch_rejects_wrong_content_of_right_size(manifest_entry, tmp_path):
    manifest_entry(b"good payload")
    manifest_entry.set_served(b"evil payload")  # same length, different bytes
    dest = str(tmp_path / "thing.zip")

    with pytest.raises(artifacts.ChecksumMismatchError) as exc:
        artifacts.fetch("fixture-1.0", dest)

    assert "sha256" in str(exc.value)
    assert not os.path.exists(dest + ".part")


def test_fetch_is_idempotent(manifest_entry, tmp_path):
    manifest_entry(b"good payload")
    dest = str(tmp_path / "thing.zip")
    artifacts.fetch("fixture-1.0", dest)

    manifest_entry.set_served(b"never downloaded again")
    assert artifacts.fetch("fixture-1.0", dest) == dest
    with open(dest, "rb") as f:
        assert f.read() == b"good payload"


def test_fetch_replaces_a_stale_wrong_size_file(manifest_entry, tmp_path):
    manifest_entry(b"good payload")
    dest = tmp_path / "thing.zip"
    dest.write_bytes(b"stale")

    artifacts.fetch("fixture-1.0", str(dest))

    assert dest.read_bytes() == b"good payload"


def test_manifest_entries_are_pinned_and_plausible():
    """Cheap guard against a placeholder checksum or a moving ref sneaking in;
    does not touch the network."""
    for name, artifact in artifacts.MANIFEST.items():
        assert artifact.url.startswith("https://"), name
        assert len(artifact.sha256) == 64, name
        assert int(artifact.sha256, 16) != 0, name
        assert artifact.size > 0, name
