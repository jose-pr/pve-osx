# pve-osx

[![Version](https://img.shields.io/badge/pypi-pending-lightgrey.svg)](https://pypi.org/project/pve-osx/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://jose-pr.github.io/pve-osx/)
[![CI](https://img.shields.io/github/actions/workflow/status/jose-pr/pve-osx/test.yml)](https://github.com/jose-pr/pve-osx/actions/workflows/test.yml)

A **remote-first CLI for building and diagnosing macOS/Hackintosh VMs on Proxmox
VE**, controlled over the Proxmox REST API (SSH only for the handful of things
the API genuinely can't do, like a QEMU monitor `screendump`) — no toolkit
checkout has to live on the Proxmox host itself, and every downloaded artifact
(OpenCore ISO, macOS recovery image) is checksum-verified before use.

Based on the work and ideas of [luchina-gabriel/OSX-PROXMOX](https://github.com/luchina-gabriel/OSX-PROXMOX)
(a bash tool that has to run locally on the PVE host, and carries its own
"all rights reserved" copyright notice) — `pve-osx` is an independent Python
implementation, not a derivative work or redistribution of its source. See the
upstream repo for its original shell scripts and troubleshooting notes (TSC,
GPU passthrough, recovery-server issues, etc. — still genuinely useful
reading).

## Features

- **Remote by design** — runs from your workstation against the Proxmox API;
  nothing has to be cloned or installed on the hypervisor.
- **Verified downloads** — OpenCore/recovery artifacts are checked against a
  pinned sha256 manifest before being used; a mismatch aborts instead of
  silently continuing.
- **No destructive re-runs** — unlike the original `install.sh`, nothing wipes
  an existing EFI/SMBIOS configuration without an explicit `--force`.
- **`vm diagnose`** — reproduces, in one command, the manual investigation
  (console screenshot + per-vCPU host-side CPU/elapsed check) that catches the
  known `kvm-pv-ipi` install livelock on multi-vCPU macOS guests.

## Installation

```bash
pip install "pve-osx[all]"
```

Optional features/extras:

| Extra/flag | Adds | Needed for |
| --- | --- | --- |
| `api` | `proxmoxer`, `requests` | Everything with a Proxmox REST endpoint (VM create/config, storage upload) |
| `ssh` | `paramiko` | The few operations the API can't do (`qm monitor` screendump) |
| `img` | `Pillow` | Saving a screenshot as anything but raw `.ppm` |
| `all` | all of the above | Full functionality |

## Quick start

```bash
pve-osx --help
```

## API overview

| Module | Purpose |
| --- | --- |
| `pve_osx.cli` | duho-based CLI root and command wiring |
| `pve_osx.pve` | Proxmox REST client (VM lifecycle, storage upload) |
| `pve_osx.ssh` | SSH exec-only fallback (monitor commands, SFTP) |
| `pve_osx.profiles` | macOS VM profile definitions and hardened CPU-flag defaults |

## Development

```bash
python -m venv .venv/3.12
.venv/3.12/Scripts/pip install -e ".[dev]"
.venv/3.12/Scripts/pytest -q
```

### Releasing

This project follows [Semantic Versioning](https://semver.org/) and keeps a
[`CHANGELOG.md`](CHANGELOG.md). Pushing a tag matching `v*` triggers the release
workflow: test gate → build → publish → docs deploy.

## License

MIT — see [LICENSE](LICENSE).
