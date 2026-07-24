"""Command-line interface, built on the duho declarative CLI framework.

Subcommands are added incrementally (``efi build``, ``vm create``, ``vm list``,
``vm diagnose``, ``vm screenshot``) and self-register onto :class:`PveOsx` from
their own modules -- this module only defines the app root.
"""

from __future__ import annotations

import duho
from duho import Cli, LoggingArgs


class PveOsxCmd(LoggingArgs, duho.Cmd):
    """Common base for every pve-osx subcommand.

    Leaf commands subclass this, implement ``__call__``, and attach themselves
    to the :class:`PveOsx` root's subcommand tree via ``cls._register()``.
    """

    def __call__(self) -> "int | None":
        raise NotImplementedError(self)

    @classmethod
    def _register(cls) -> None:
        PveOsx._register_subcmd_(cls)


class PveOsx(PveOsxCmd, Cli):
    """Provision and diagnose macOS/Hackintosh VMs on Proxmox VE remotely."""

    _parsername_ = "pve-osx"
    _version_ = duho.AUTO
    _distribution_ = "pve-osx"
    _completion_ = True


def run(argv: "list[str] | None" = None) -> "int | None":
    import sys

    if argv is None:
        argv = sys.argv[1:]
    return duho.main(PveOsx, argv)
