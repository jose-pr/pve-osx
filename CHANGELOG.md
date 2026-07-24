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

[Unreleased]: https://github.com/jose-pr/pve-osx/compare/v0.1.0...HEAD
