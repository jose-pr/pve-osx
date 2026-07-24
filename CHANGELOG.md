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
  trade-off for macOS either way without real GPU passthrough), and NUMA
  enabled.

[Unreleased]: https://github.com/jose-pr/pve-osx/compare/v0.1.0...HEAD
