"""pve-osx: provision and diagnose macOS/Hackintosh VMs on Proxmox VE remotely.

Talks to Proxmox over its REST API (:mod:`pve_osx.pve`) for everything that has
a real endpoint (VM create/config/start/stop/status, storage upload), and falls
back to SSH (:mod:`pve_osx.ssh`) only for the handful of things the API cannot
do (e.g. a raw QEMU monitor ``screendump``). No install of this package, or any
git checkout of it, needs to live on the Proxmox host itself.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
