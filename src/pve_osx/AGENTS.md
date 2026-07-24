# `pve_osx` — package header

Header-style reference for the `pve_osx` package: every public export with its
signature, arguments, contract, and gotchas, so this package can be consumed
without a source dive. Kept current with the public API. For the project
overview, see the shipped `README.md`, or <https://github.com/jose-pr/pve-osx>.

## CLI (`pve_osx.cli`)

- **`PveOsx`** — the app root (`duho.Cli`), registered as the `pve-osx` console
  script and `python -m pve_osx`. `--version`/shell completion come from duho
  (`_version_ = duho.AUTO`, `_completion_ = True`).
- **`PveOsxCmd`** — common base every subcommand extends (`duho.Cmd` +
  `duho.LoggingArgs`). `cls._register()` attaches a leaf command to `PveOsx`'s
  subcommand tree; call it once at the bottom of the module defining the
  command.
- **`run(argv: list[str] | None = None) -> int | None`** — programmatic
  entry point used by both the console script and `__main__.py`.

## Proxmox REST client (`pve_osx.pve`) — needs the `pve-osx[api]` extra

- **`PveClient(host, node, token_id, token_secret, *, verify_ssl=True, port=8006)`**
  — `node=None` auto-discovers (only unambiguous for a single-node cluster;
  raises `PveError` listing the nodes otherwise). `token_id` is
  `user@realm!tokenid` (an API token, never a password).
  - `PveClient.from_env(prefix="PVE_")` — reads `{PREFIX}HOST/NODE/TOKEN_ID/
    TOKEN_SECRET/VERIFY_SSL`; `VERIFY_SSL` defaults to `false` (Proxmox ships
    a self-signed cert by default).
  - `.list_vms() -> list[dict]`, `.get_config(vmid) -> dict`,
    `.set_config(vmid, **fields)`, `.status(vmid) -> dict`, `.start(vmid)`,
    `.stop(vmid, timeout=20)`, `.next_id() -> int`.
  - `.create_vm(vmid, **fields)` — raises `PveError` on failure; callers doing
    multi-step creation should catch, `.destroy_vm(vmid)`, and re-raise so a
    partial failure never leaves an orphaned VM.
  - `.storage_status(storage) -> StorageStatus(total_bytes, used_bytes,
    available_bytes)`, `.upload(storage, content_type, filename, fileobj)`,
    `.storage_contents(storage) -> list[dict]`.
- **`PveError`** — raised for any API failure/unexpected shape.

## SSH exec-only fallback (`pve_osx.ssh`) — needs the `pve-osx[ssh]` extra

Only for what the REST API cannot do (currently: raw QEMU monitor commands).
Not a general remote-shell wrapper — needing this module for something new is
itself a signal that thing has no REST endpoint.

- **`SshClient(host, *, user=None, port=22, insecure_accept_unknown_hosts=False,
  config_path=None)`** — context manager. Resolves `host` through
  `~/.ssh/config` first (paramiko does not understand `Host` aliases itself),
  so `SshClient("some-ssh-config-alias")` behaves like `ssh some-ssh-config-alias`
  — including picking up its `IdentityFile`. Host keys come from
  `load_system_host_keys()`; unknown hosts are rejected unless
  `insecure_accept_unknown_hosts=True`.
  - `.run(command, timeout=30) -> str` — stdout; raises `SshError` (stderr
    included) on non-zero exit.
  - `.sftp_get(remote_path) -> bytes`.
  - `.monitor(vmid, command) -> str` — one raw QEMU HMP command via
    `qm monitor`.
  - `.screendump(vmid, remote_tmp=None) -> bytes` — the VM's console
    framebuffer as raw PPM bytes (open with e.g. `PIL.Image.open` to convert);
    cleans up its own remote temp file.
- **`SshError`** — raised for a failed command or SFTP transfer.

## VM profiles (`pve_osx.profiles`)

- **`DEFAULT_CPU_FLAGS`** — the hardened default macOS CPU-flag tuple.
  Notably includes `-kvm-pv-ipi` (hyphenated, not `_ipi` — QEMU rejects the
  underscore form for this specific flag): fixes a known KVM+macOS livelock on
  multi-vCPU guests where vCPUs spin at high CPU while the installer barely
  advances. Discovered and verified live against a real hung install
  (2026-07-23).
- **`APPLE_SMC_OSK`** — the public Apple SMC OSK string used by every
  OpenCore/Hackintosh setup (not a secret).
- **`cpu_arg(flags=DEFAULT_CPU_FLAGS, *, base="host") -> str`** — renders the
  `-cpu` QEMU argument value.
- **`qemu_args(smbios_type=2, osk=APPLE_SMC_OSK) -> str`** — renders the full
  `args:` line a macOS guest needs (AppleSMC + USB + CPU flags).
- **`MacOSProfile(name, macos_version, cores=4, memory_mb=8192,
  disk_size_gb=80, disk_storage="local-zfs", efi_storage="local-zfs",
  bridge="vmbr0", vlan_tag=None, extra_cpu_flags=())`** — `cores` defaults
  conservatively (4) since the `kvm-pv-ipi` bug scales with vCPU count.
  `.cpu_flags` = `DEFAULT_CPU_FLAGS + extra_cpu_flags`; `.args()` renders the
  full `args:` line for this profile; `.net_config()` renders the `netN` line.
