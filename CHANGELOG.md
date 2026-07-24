# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
  virtio-blk handling), `qxl` display (SPICE console -- no acceleration
  trade-off for macOS either way without real GPU passthrough), NUMA enabled,
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

[Unreleased]: https://github.com/jose-pr/pve-osx/compare/v0.1.0...HEAD
