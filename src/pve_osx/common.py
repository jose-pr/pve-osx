"""Shared connection-args mixin every command that talks to Proxmox extends.

Resolution order for host/token/ssh-host is CLI flags -> environment
variables (``PVE_*`` -- the same names :meth:`pve_osx.pve.PveClient.from_env`
reads) -- there is deliberately no third "config file" tier yet; add one only
if the env-var-only flow proves too repetitive in practice.
"""

from __future__ import annotations

import os
import typing as _ty

from duho import CommandError, Meta
from duho.text import parse_bool

from .cli import PveOsxCmd


class PveConnectionArgs(PveOsxCmd):
    """Mixin supplying the flags every Proxmox-talking command needs."""

    # Each variable is named on its own field: a class-wide `_env_prefix_ = "PVE_"`
    # would also reach the options of every command that extends this mixin
    # (`PVE_NAME`, `PVE_VMID`, ...).
    host: "_ty.Annotated[_ty.Optional[str], Meta(env='PVE_HOST')]" = None
    "Proxmox host (defaults to $PVE_HOST)"
    ("--host",)

    node: "_ty.Annotated[_ty.Optional[str], Meta(env='PVE_NODE')]" = None
    "Proxmox node name (defaults to $PVE_NODE, or auto-discovers for a single-node cluster)"
    ("--node",)

    token_id: "_ty.Annotated[_ty.Optional[str], Meta(env='PVE_TOKEN_ID')]" = None
    "API token id, user@realm!tokenid (defaults to $PVE_TOKEN_ID)"
    ("--token-id",)

    token_secret: "_ty.Annotated[_ty.Optional[str], Meta(env='PVE_TOKEN_SECRET')]" = (
        None
    )
    "API token secret (defaults to $PVE_TOKEN_SECRET)"
    ("--token-secret",)

    insecure: bool = False
    "Skip TLS certificate verification (defaults to $PVE_VERIFY_SSL=false, Proxmox's own default cert)"
    ("--insecure",)

    ssh_host: "_ty.Annotated[_ty.Optional[str], Meta(env='PVE_SSH_HOST')]" = None
    "SSH host/alias for operations the API can't do (defaults to $PVE_SSH_HOST, falls back to --host)"
    ("--ssh-host",)

    @staticmethod
    def _verify_ssl_requested() -> bool:
        """``$PVE_VERIFY_SSL`` as a boolean (default false); text that is not one
        ends the command, since guessing would decide whether TLS is checked."""
        text = os.environ.get("PVE_VERIFY_SSL", "false")
        try:
            return parse_bool(text)
        except ValueError:
            raise CommandError(
                f"pve-osx: $PVE_VERIFY_SSL is {text!r}, not a boolean "
                "(true or false)"
            ) from None

    def pve(self):
        from .pve import PveClient

        host = self.host
        if not host:
            raise CommandError("pve-osx: no Proxmox host given (--host or $PVE_HOST)")
        token_id = self.token_id
        token_secret = self.token_secret
        if not token_id or not token_secret:
            raise CommandError(
                "pve-osx: no API token given (--token-id/--token-secret or "
                "$PVE_TOKEN_ID/$PVE_TOKEN_SECRET)"
            )
        verify_ssl = not self.insecure and self._verify_ssl_requested()
        return PveClient(
            host,
            self.node,
            token_id,
            token_secret,
            verify_ssl=verify_ssl,
        )

    def ssh(self):
        from .ssh import SshClient

        host = self.ssh_host or self.host
        if not host:
            raise CommandError(
                "pve-osx: no SSH host given (--ssh-host, $PVE_SSH_HOST, or --host)"
            )
        return SshClient(host)
