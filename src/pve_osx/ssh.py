"""SSH exec-only fallback for the handful of operations the Proxmox REST API
cannot do -- currently just a raw QEMU monitor command (``screendump`` has no
REST endpoint) and its follow-up SFTP fetch.

``paramiko`` is imported lazily inside :meth:`SshClient.__init__`, matching
:mod:`pve_osx.pve`'s lazy-``proxmoxer`` pattern; install with the
``pve-osx[ssh]`` extra. This client deliberately does *not* grow into a general
remote-shell wrapper -- if a step needs this module, that is itself a signal
worth noting (it means the REST API had no endpoint for it).
"""

from __future__ import annotations

import dataclasses
import io
import typing as _ty


class SshError(RuntimeError):
    """An SSH command or SFTP transfer failed."""


@dataclasses.dataclass
class VmProcessStatus:
    """Host-side view of a VM's QEMU process, for the ``vm diagnose`` heuristic."""

    pid: int
    cpu_percent: float
    elapsed_seconds: int
    state: str


def _parse_elapsed(etime: str) -> int:
    """Parse ``ps -o etime``'s ``[[DD-]HH:]MM:SS`` format into seconds."""
    days = 0
    if "-" in etime:
        d, etime = etime.split("-", 1)
        days = int(d)
    parts = [int(p) for p in etime.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class SshClient:
    """A connected SSH session to the Proxmox host, for exec-only fallbacks.

    Use as a context manager: ``with SshClient(host) as ssh: ...`` -- closes
    the underlying transport on exit. Host key policy defaults to using the
    local ``known_hosts`` (never auto-accepting unknown keys silently);
    pass ``insecure_accept_unknown_hosts=True`` to opt into the looser
    behavior explicitly, e.g. for a freshly-reinstalled host.
    """

    def __init__(
        self,
        host: str,
        *,
        user: "_ty.Optional[str]" = None,
        port: int = 22,
        insecure_accept_unknown_hosts: bool = False,
        config_path: "_ty.Optional[str]" = None,
    ) -> None:
        import os

        import paramiko  # local import: see module docstring

        # Unlike the real `ssh` binary, paramiko does not understand
        # ~/.ssh/config Host aliases at all -- connecting with the alias
        # literally (as opposed to the HostName it resolves to) both fails
        # DNS and, even if it resolved, would look up the wrong known_hosts
        # entry (recorded under the real host, not the alias). Resolve the
        # alias ourselves first so `SshClient("asgard-borr")` behaves the way
        # `ssh asgard-borr` already does for the user.
        resolved_host, resolved_user, resolved_port, identities = host, user, port, []
        cfg_path = config_path or os.path.expanduser("~/.ssh/config")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                ssh_config = paramiko.SSHConfig()
                ssh_config.parse(f)
            lookup = ssh_config.lookup(host)
            resolved_host = lookup.get("hostname", host)
            resolved_user = user or lookup.get("user")
            resolved_port = int(lookup.get("port", port))
            identities = lookup.get("identityfile", [])

        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        if insecure_accept_unknown_hosts:
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {}
        if identities:
            connect_kwargs["key_filename"] = identities
        self._client.connect(
            resolved_host, port=resolved_port, username=resolved_user, **connect_kwargs
        )

    def __enter__(self) -> "SshClient":
        return self

    def __exit__(self, *exc) -> None:
        self._client.close()

    def run(self, command: str, *, timeout: "_ty.Optional[float]" = 30) -> str:
        """Run ``command``, return its stdout. Raises :class:`SshError` on a
        non-zero exit, including stderr in the message."""
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace")
        if exit_status != 0:
            err = stderr.read().decode(errors="replace")
            raise SshError(f"{command!r} exited {exit_status}: {err.strip()}")
        return out

    def sftp_get(self, remote_path: str) -> bytes:
        sftp = self._client.open_sftp()
        try:
            buf = io.BytesIO()
            sftp.getfo(remote_path, buf)
            return buf.getvalue()
        finally:
            sftp.close()

    # -- QEMU monitor (HMP) -- the one thing with no REST endpoint ---------

    def monitor(self, vmid: int, command: str) -> str:
        """Run a raw QEMU Human Monitor Protocol command against ``vmid``."""
        # `qm monitor` is interactive; piping one line in via echo and letting
        # it exit on EOF is the same trick used diagnosing VM 107 by hand.
        escaped = command.replace("'", "'\\''")
        return self.run(f"echo '{escaped}' | qm monitor {vmid}")

    def screendump(self, vmid: int, *, remote_tmp: "_ty.Optional[str]" = None) -> bytes:
        """Capture the VM's current console framebuffer as raw PPM bytes.

        Returns the PPM file content directly (see :mod:`PIL.Image` to convert
        to PNG) -- no local temp file management needed by the caller.
        """
        remote_path = remote_tmp or f"/tmp/pve-osx-screendump-{vmid}.ppm"
        self.monitor(vmid, f"screendump {remote_path}")
        data = self.sftp_get(remote_path)
        self.run(f"rm -f {remote_path}")
        return data

    # -- host-side process info -- no REST equivalent (that's per-guest, this
    # is the host's view of the QEMU process itself) -----------------------

    def vm_process_status(self, vmid: int) -> "_ty.Optional[VmProcessStatus]":
        """The host-side QEMU process for ``vmid``: PID, %CPU, and how long
        it's been running. Returns ``None`` if the VM isn't running (no pidfile).
        """
        pid_raw = self.run(
            f"cat /var/run/qemu-server/{vmid}.pid 2>/dev/null || true"
        ).strip()
        if not pid_raw:
            return None
        out = self.run(f"ps -o pid,pcpu,etime,stat -p {pid_raw} --no-headers").strip()
        if not out:
            return None
        pid, pcpu, etime, stat = out.split(None, 3)
        return VmProcessStatus(
            pid=int(pid),
            cpu_percent=float(pcpu),
            elapsed_seconds=_parse_elapsed(etime),
            state=stat,
        )
