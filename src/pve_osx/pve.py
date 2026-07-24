"""Proxmox VE REST API client.

Thin wrapper around :mod:`proxmoxer` scoped to what this package needs: VM
lifecycle (create/config/start/stop/status), storage introspection (for the
disk-space preflight check), and artifact upload. ``proxmoxer`` is imported
lazily inside :meth:`PveClient.__init__` so importing this module -- and thus
the whole ``pve_osx`` package -- never requires it; only actually connecting
does. Install with the ``pve-osx[api]`` extra.

Anything without a real REST endpoint (a raw QEMU monitor command) is out of
scope here -- see :mod:`pve_osx.ssh`.
"""

from __future__ import annotations

import dataclasses
import typing as _ty


class PveError(RuntimeError):
    """A Proxmox API call failed or returned an unexpected shape."""


@dataclasses.dataclass
class StorageStatus:
    storage: str
    total_bytes: int
    used_bytes: int
    available_bytes: int


class PveClient:
    """Authenticated handle to one Proxmox node's REST API.

    ``token_id``/``token_secret`` are an API token (``pveum user token add``),
    never a password -- this client does not accept one. Connect once per
    process; instances are cheap but not thread-safe (matches ``proxmoxer``).
    """

    def __init__(
        self,
        host: str,
        node: "_ty.Optional[str]",
        token_id: str,
        token_secret: str,
        *,
        verify_ssl: bool = True,
        port: int = 8006,
    ) -> None:
        import proxmoxer  # local import: see module docstring

        user, token_name = token_id.split("!", 1)
        self._api = proxmoxer.ProxmoxAPI(
            host,
            user=user,
            token_name=token_name,
            token_value=token_secret,
            verify_ssl=verify_ssl,
            port=port,
        )
        self.node = node or self._discover_node()

    def _discover_node(self) -> str:
        """Resolve the target node when none was given: only correct for a
        single-node cluster (the common homelab case) -- ambiguous otherwise."""
        nodes = self._api.nodes.get()
        if len(nodes) != 1:
            names = ", ".join(sorted(n["node"] for n in nodes))
            raise PveError(
                f"multiple Proxmox nodes ({names}) -- pass node= explicitly "
                "(or set PVE_NODE) instead of relying on auto-discovery"
            )
        return nodes[0]["node"]

    @classmethod
    def from_env(cls, *, prefix: str = "PVE_") -> "PveClient":
        """Build a client from ``{prefix}HOST``/``{prefix}TOKEN_ID``/``{prefix}TOKEN_SECRET``.

        ``{prefix}NODE`` auto-discovers when unset (see :meth:`_discover_node`
        -- only unambiguous for a single-node cluster). ``{prefix}VERIFY_SSL``
        (default ``false``) controls certificate verification: Proxmox ships a
        self-signed cert by default, so most homelab setups need this off;
        set it to ``true`` once a real certificate is installed.
        """
        import os

        def require(name: str) -> str:
            value = os.environ.get(f"{prefix}{name}")
            if not value:
                raise PveError(f"missing required env var {prefix}{name}")
            return value

        verify_ssl = os.environ.get(f"{prefix}VERIFY_SSL", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        return cls(
            require("HOST"),
            os.environ.get(f"{prefix}NODE"),
            require("TOKEN_ID"),
            require("TOKEN_SECRET"),
            verify_ssl=verify_ssl,
        )

    def _node(self):
        return self._api.nodes(self.node)

    # -- VM lifecycle ---------------------------------------------------

    def list_vms(self) -> "list[dict]":
        return self._node().qemu.get()

    def get_config(self, vmid: int) -> "dict":
        return self._node().qemu(vmid).config.get()

    def set_config(self, vmid: int, **fields) -> None:
        self._node().qemu(vmid).config.put(**fields)

    def status(self, vmid: int) -> "dict":
        return self._node().qemu(vmid).status.current.get()

    def start(self, vmid: int) -> str:
        return self._node().qemu(vmid).status.start.post()

    def stop(self, vmid: int, timeout: int = 20) -> str:
        return self._node().qemu(vmid).status.stop.post(timeout=timeout)

    def next_id(self) -> int:
        return int(self._api.cluster.nextid.get())

    def create_vm(self, vmid: int, **fields) -> str:
        """Create a VM. Raises :class:`PveError` on failure -- callers doing
        multi-step creation (attach disks, set boot order, ...) should catch
        that, ``destroy_vm(vmid)``, and re-raise, so a partial failure never
        leaves an orphaned VM registered (see ``vm create``'s rollback)."""
        try:
            return self._node().qemu.post(vmid=vmid, **fields)
        except Exception as e:  # noqa: BLE001 - re-raised as our own type
            raise PveError(f"create_vm({vmid}) failed: {e}") from e

    def destroy_vm(self, vmid: int, *, purge: bool = True) -> str:
        return self._node().qemu(vmid).delete(purge=1 if purge else 0)

    # -- Storage ----------------------------------------------------------

    def storage_status(self, storage: str) -> StorageStatus:
        data = self._node().storage(storage).status.get()
        return StorageStatus(
            storage=storage,
            total_bytes=int(data["total"]),
            used_bytes=int(data["used"]),
            available_bytes=int(data["avail"]),
        )

    def upload(self, storage: str, content_type: str, filename: str, fileobj) -> None:
        """Upload a file (e.g. an EFI/ISO image) to ``storage``.

        ``content_type`` is a Proxmox storage content type (``iso``, ``images``,
        ``vztmpl``, ...); ``fileobj`` is any file-like object opened for
        binary read.
        """
        self._node().storage(storage).upload.post(
            content=content_type, filename=(filename, fileobj)
        )

    def storage_contents(self, storage: str) -> "list[dict]":
        return self._node().storage(storage).content.get()
