"""Shared connection-args mixin every command that talks to Proxmox extends.

Resolution order for host/token/ssh-host is CLI flags -> environment
variables (``PVE_*`` -- the same names :meth:`pve_osx.pve.PveClient.from_env`
reads) -- there is deliberately no third "config file" tier yet; add one only
if the env-var-only flow proves too repetitive in practice.
"""

from __future__ import annotations

import os
import typing as _ty

from .cli import PveOsxCmd


class PveConnectionArgs(PveOsxCmd):
    """Mixin supplying the flags every Proxmox-talking command needs."""

    host: "_ty.Optional[str]" = None
    "Proxmox host (defaults to $PVE_HOST)"
    ("--host",)

    node: "_ty.Optional[str]" = None
    "Proxmox node name (defaults to $PVE_NODE, or auto-discovers for a single-node cluster)"
    ("--node",)

    token_id: "_ty.Optional[str]" = None
    "API token id, user@realm!tokenid (defaults to $PVE_TOKEN_ID)"
    ("--token-id",)

    token_secret: "_ty.Optional[str]" = None
    "API token secret (defaults to $PVE_TOKEN_SECRET)"
    ("--token-secret",)

    insecure: bool = False
    "Skip TLS certificate verification (defaults to $PVE_VERIFY_SSL=false, Proxmox's own default cert)"
    ("--insecure",)

    ssh_host: "_ty.Optional[str]" = None
    "SSH host/alias for operations the API can't do (defaults to $PVE_SSH_HOST, falls back to --host)"
    ("--ssh-host",)

    def pve(self):
        from .pve import PveClient

        host = self.host or os.environ.get("PVE_HOST")
        if not host:
            raise SystemExit("pve-osx: no Proxmox host given (--host or $PVE_HOST)")
        token_id = self.token_id or os.environ.get("PVE_TOKEN_ID")
        token_secret = self.token_secret or os.environ.get("PVE_TOKEN_SECRET")
        if not token_id or not token_secret:
            raise SystemExit(
                "pve-osx: no API token given (--token-id/--token-secret or "
                "$PVE_TOKEN_ID/$PVE_TOKEN_SECRET)"
            )
        verify_ssl = not self.insecure and os.environ.get("PVE_VERIFY_SSL", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        return PveClient(
            host,
            self.node or os.environ.get("PVE_NODE"),
            token_id,
            token_secret,
            verify_ssl=verify_ssl,
        )

    def ssh(self):
        from .ssh import SshClient

        host = self.ssh_host or os.environ.get("PVE_SSH_HOST") or self.host or os.environ.get(
            "PVE_HOST"
        )
        if not host:
            raise SystemExit("pve-osx: no SSH host given (--ssh-host, $PVE_SSH_HOST, or --host)")
        return SshClient(host)
