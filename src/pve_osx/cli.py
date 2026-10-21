"""Command-line interface, built on the duho declarative CLI framework.

Subcommands are added incrementally (``efi build``, ``vm create``, ``vm list``,
``vm diagnose``, ``vm screenshot``) and self-register onto :class:`PveOsx` from
their own modules -- this module only defines the app root.
"""

from __future__ import annotations

import sys

import duho
from duho import Cli, LoggingArgs


class PveOsxCmd(LoggingArgs, duho.Cmd):
    """Common base for every pve-osx subcommand.

    Leaf commands subclass this, implement ``__call__``, and attach themselves
    to a parent's subcommand tree with ``@duho.subcommand(Parent)``.
    """

    def __call__(self) -> "int | None":
        raise NotImplementedError(self)


class PveOsx(PveOsxCmd, Cli):
    """Provision and diagnose macOS/Hackintosh VMs on Proxmox VE remotely."""

    _parsername_ = "pve-osx"
    _version_ = duho.AUTO
    _distribution_ = "pve-osx"
    _completion_ = True
    # Error messages already carry the "pve-osx:" prefix: print them unchanged.
    _report_error_ = staticmethod(lambda message, code: print(message, file=sys.stderr))


def run(argv: "list[str] | None" = None) -> int:
    """Entry point: return the status; ``--help``, ``--version`` and a usage error
    raise ``SystemExit``."""
    # Import side effect: each module self-registers its commands onto PveOsx
    # (or an intermediate group like Vm) at import time.
    from . import efi as _efi  # noqa: F401
    from . import vm as _vm  # noqa: F401

    if argv is None:
        argv = sys.argv[1:]
    return duho.run(PveOsx, argv, exit="parse")
