# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Bumped the `duho` dependency floor to `>=0.6.0,<0.7` (was the unbounded
  `>=0.3.2`). Pre-1.0, a duho minor bump is a documented API break by
  convention, so pinning to the version actually verified closes the
  auto-adopt gap; no source changes were needed for 0.6.0 itself.

### Added

- Initial rewrite of OSX-PROXMOX as a Python/duho package: remote-first CLI
  over the Proxmox REST API, checksum-verified artifact downloads, and a
  hardened default macOS CPU-flag preset (`-kvm-pv-ipi`, fixing a known
  install livelock on multi-vCPU guests).
- `vm list`/`vm create`/`vm diagnose`/`vm screenshot` commands. `vm diagnose`
  reproduces a manual investigation (console screenshot + host-side CPU/elapsed
  check) as a repeatable heuristic for the kvm-pv-ipi livelock. `vm create`
  preflights free disk space and rolls back (destroys the VM) on partial
  failure instead of leaving it half-configured.
- `efi build` command: assembles an OpenCore EFI folder from the checksum-verified
  release, generating a fresh SMBIOS identity via the bundled `macserial` and
  patching it into `config.plist`. Also enables every `Virtio*.efi` driver
  already declared in `Sample.plist` (harmless if the corresponding bus isn't
  used, forward-compatible if it is).
- Performance-oriented defaults for `vm create`: `nvme0` as the default disk
  bus (macOS's native NVMe driver needs no kext, unlike relying on implicit
  virtio-blk handling), `vmware` display with `memory=128` (measured on a real
  macOS guest to render the desktop correctly with much less input lag, where
  `qxl` gave a near-white, laggy console -- this reverses an earlier
  theoretical assumption that the choice could not matter), NUMA enabled,
  and `vmware-cpuid-freq=on` added to the default CPU flags (cross-referenced
  against three independent macOS-on-Proxmox write-ups).
- `efi build` now fetches and installs the four standard kexts
  (Lilu/VirtualSMC/WhateverGreen/AppleALC) that `Sample.plist` references but
  the OpenCore release doesn't bundle, plus `SMCProcessor.kext`/
  `SMCSuperIO.kext` (VirtualSMC's sensor plugins -- missing these caused a
  real `PowerlogCore` CPU spin on first boot, diagnosed via macOS's own
  automatic diagnostic report).
- `vm create` now sets `agent=enabled=1,type=isa`: the community
  `mac-guest-agent` requires an ISA-serial channel and crash-loops on
  Proxmox's default virtio-serial one.
- New `vm provision` command: post-boot guest setup over SSH (verify Remote
  Login, enable Screen Sharing persistently, install/upgrade
  `mac-guest-agent`, checksum-verified and idempotent).

### Fixed

- `efi build` no longer fails on Linux/macOS: `zipfile.extractall` never
  restores POSIX permissions, so the `macserial` binary extracted from the
  OpenCore release landed non-executable and running it raised
  `PermissionError`. Only a Windows-only development box hid this.
- `generate_smbios` now raises `EfiError` for every macserial failure --
  including the stderr that `capture_output=True` was swallowing -- instead of
  a bare `CalledProcessError` traceback, and reports unparseable output rather
  than raising `StopIteration`.
- `artifacts.fetch` now verifies the manifest's declared byte count as well as
  its sha256. `Artifact.size` was recorded and never checked; checking it
  first aborts a truncated download on a stat rather than after hashing.
- `vm create`'s log line no longer prints the vmid twice ("Creating VM 107 ...
  on vmid 107"); it reports the profile's resources instead.

[Unreleased]: https://github.com/jose-pr/pve-osx/compare/v0.1.0...HEAD
