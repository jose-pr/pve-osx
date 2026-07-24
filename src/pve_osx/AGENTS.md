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

## Verified downloads (`pve_osx.artifacts`)

- **`MANIFEST`** — `dict[str, Artifact(url, sha256, size)]`, pinned
  releases/refs with real (not placeholder) checksums. Currently one entry,
  `"opencore-<version>"` — the single OpenCore release zip already bundles
  `Utilities/macserial` (prebuilt Windows/Linux/macOS) and
  `Utilities/macrecovery`, so neither needs its own manifest entry or a
  GenSMBIOS dependency.
- **`fetch(name, dest, *, force=False) -> str`** — downloads `MANIFEST[name]`
  to `dest`, verifying sha256; raises `ChecksumMismatchError` (deleting the bad
  file) on a mismatch. Idempotent: skips re-downloading if `dest` already
  matches.

## Shared connection args (`pve_osx.common`)

- **`PveConnectionArgs(PveOsxCmd)`** — mixin every Proxmox-talking command
  extends. Flags: `--host/--node/--token-id/--token-secret/--insecure`
  (`PveClient`) and `--ssh-host` (`SshClient`), each falling back to the
  matching `PVE_*` env var. `.pve() -> PveClient`, `.ssh() -> SshClient`
  (context manager) build the clients from resolved args; both raise
  `SystemExit` with a clear message if required values are missing.

## `pve-osx vm ...` (`pve_osx.vm`)

Nested command group (`Vm(PveOsxCmd, duho.Cli)`, `_parsername_ = "vm"`).
`VmCmd(PveConnectionArgs)` is the shared leaf base; `cls._register()` attaches
onto `Vm`, not the root.

- **`vm list`** — one line per VM: `vmid  name  status  memMB`.
- **`vm diagnose <vmid> [--screenshot PATH]`** — status + config, a host-side
  `ps` check (PID/%CPU/elapsed via `SshClient.vm_process_status`), and the
  **kvm-pv-ipi livelock heuristic**: warns when `args:` lacks `-kvm-pv-ipi`,
  `cores > 1`, elapsed > 20 minutes, and host CPU > 50% -- the exact signature
  diagnosed by hand on VM 107 (2026-07-23, livelocked 1d15h at ~20% install
  progress). `--screenshot foo.ppm` saves raw; any other extension converts
  via Pillow (`pve-osx[img]`).
- **`vm screenshot <vmid> <out>`** — shorthand for the screenshot half of
  `diagnose`.
- **`vm create <name> [--macos-version --cores --memory --disk-size
  --disk-storage --bridge --vlan --vmid]`** — builds a `MacOSProfile`,
  preflights free space on the target storage (raises `SystemExit` rather than
  attempting a create doomed to run out of room), then `create_vm`; on any
  `PveError` after the VM is registered, destroys it before re-raising so a
  failed create never leaves an orphaned VM. Does not yet attach an
  EFI/installer artifact -- run `efi build` and attach manually.

## `pve-osx efi ...` (`pve_osx.efi`)

Nested command group (`Efi(PveOsxCmd, duho.Cli)`, `_parsername_ = "efi"`).

- **`efi build [--out --model --opencore --cache-dir]`** — fetches the pinned
  OpenCore release (checksum-verified via `pve_osx.artifacts`), generates a
  fresh SMBIOS identity for `--model` via the bundled `macserial -g` (parses
  its `Serial | MLB` output; `SystemUUID`/`ROM` generated directly via
  `uuid.uuid4()`/`os.urandom(6)`), and patches those into
  `PlatformInfo.Generic` of OpenCore's `Docs/Sample.plist`, writing the
  result to `<out>/EFI/OC/config.plist` alongside the rest of `<out>/EFI/`
  copied from the release. Does not yet build a FAT/ISO image from that
  folder -- the printed next step says to write it onto the VM's EFI disk via
  `mtools`/`mcopy` on the Proxmox host.
- **`generate_smbios(macserial_path, model) -> dict`**,
  **`patch_config(sample_plist_path, out_path, smbios)`** — the two steps
  above, usable standalone.
- **`EfiError`** — raised when the extracted OpenCore archive doesn't have the
  expected layout.
