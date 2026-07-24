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
  - `.sftp_get(remote_path) -> bytes`, `.sftp_put(local_path, remote_path)`.
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
  (2026-07-23). Also includes `vmware-cpuid-freq=on` (cross-referenced against
  three independent macOS-on-Proxmox write-ups, 2026-07-23 — all three list
  it) so macOS reads its CPU frequency correctly instead of guessing from
  calibration.
- **`APPLE_SMC_OSK`** — the public Apple SMC OSK string used by every
  OpenCore/Hackintosh setup (not a secret).
- **`cpu_arg(flags=DEFAULT_CPU_FLAGS, *, base="host") -> str`** — renders the
  `-cpu` QEMU argument value.
- **`qemu_args(smbios_type=2, osk=APPLE_SMC_OSK) -> str`** — renders the full
  `args:` line a macOS guest needs (AppleSMC + USB + CPU flags).
- **`MacOSProfile(name, macos_version, cores=4, memory_mb=8192,
  disk_size_gb=80, disk_storage="local-zfs", efi_storage="local-zfs",
  bridge="vmbr0", vlan_tag=None, extra_cpu_flags=(), disk_bus="nvme0",
  display="qxl", numa=True)`** — `cores` defaults conservatively (4) since the
  `kvm-pv-ipi` bug scales with vCPU count. `disk_bus` defaults to `nvme0`
  (macOS's native NVMe driver needs no kext/EFI driver at all -- more
  standard than `virtio0`, which was verified working in practice on
  2026-07-23 but relies on OVMF's implicit virtio-blk handling rather than a
  driver macOS actually ships). `display` defaults to `qxl` for a SPICE
  console (see `pve_osx.efi` note below on why this costs nothing -- macOS
  has no native accelerated driver for any of `std`/`vmware`/`qxl` without
  real GPU passthrough, so `qxl` is strictly better for remote-console
  quality at zero cost). `.cpu_flags` = `DEFAULT_CPU_FLAGS + extra_cpu_flags`;
  `.args()` renders the full `args:` line for this profile; `.net_config()`
  renders the `netN` line (always `vmxnet3` -- macOS's *native*
  `AppleVmxnet3.kext` beats any virtio-net kext, so there's no `net_bus`
  option to change).

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
  --disk-storage --bridge --vlan --vmid --disk-bus --display]`** — builds a
  `MacOSProfile`, preflights free space on the target storage (raises
  `SystemExit` rather than attempting a create doomed to run out of room),
  then `create_vm` (`vga=<display>`, `numa=1`, `agent=enabled=1,type=isa`,
  main disk on `<disk-bus>=...`, `boot=order=<disk-bus>`); on any `PveError`
  after the VM is registered, destroys it before re-raising so a failed
  create never leaves an orphaned VM. Does not yet attach an EFI/installer
  artifact -- run `efi build` and attach manually.
- **`vm provision <guest_host> [--guest-user --skip-agent
  --skip-screen-sharing]`** — post-*boot* guest-side setup over SSH (separate
  from `vm create`'s pre-boot VM config): verifies Remote Login, enables
  Screen Sharing persistently (`launchctl enable system/com.apple.screensharing`
  + `bootstrap`), and installs/upgrades the community `mac-guest-agent`
  (checksum-verified via `pve_osx.artifacts`, idempotent -- falls back to
  `--upgrade` if already installed). Requires SSH already reachable (Remote
  Login is a one-time manual console step -- pve-osx can't enable it before
  SSH exists) and passwordless sudo for `--guest-user` (also a one-time
  manual step: `echo '<user> ALL=(ALL) NOPASSWD: ALL' | sudo tee
  /etc/sudoers.d/pve-osx` -- pve-osx never handles a password itself).

### The `mac-guest-agent` transport gotcha

`mac-guest-agent` v2.5.0+ requires an **ISA-serial** channel and refuses
Proxmox's *default* virtio-serial one outright (crash-loops every ~10s,
diagnosed live 2026-07-23 via its own log at `/var/log/mac-guest-agent.log`).
`vm create` sets `agent=enabled=1,type=isa` for exactly this reason; for a
VM created before this fix, run `qm set <vmid> --agent enabled=1,type=isa`
and restart it.

## `pve-osx efi ...` (`pve_osx.efi`)

Nested command group (`Efi(PveOsxCmd, duho.Cli)`, `_parsername_ = "efi"`).

- **`efi build [--out --model --opencore --cache-dir]`** — fetches the pinned
  OpenCore release (checksum-verified via `pve_osx.artifacts`), generates a
  fresh SMBIOS identity for `--model` via the bundled `macserial -g` (parses
  its `Serial | MLB` output; `SystemUUID`/`ROM` generated directly via
  `uuid.uuid4()`/`os.urandom(6)`), patches those into `PlatformInfo.Generic`
  of OpenCore's `Docs/Sample.plist`, enables every `Virtio*.efi` entry already
  declared (disabled) in `UEFI.Drivers`, appends `SMCProcessor.kext`/
  `SMCSuperIO.kext` to `Kernel.Add`, and fetches+installs the six standard
  kexts (`STANDARD_KEXTS`) into `<out>/EFI/OC/Kexts/` -- writing the patched
  config to `<out>/EFI/OC/config.plist` alongside the rest of `<out>/EFI/`
  copied from the release (which already includes the Virtio DXE driver
  files themselves, no separate fetch needed for those). Does not yet build a
  FAT/ISO image from that folder -- the printed next step says to write it
  onto the VM's EFI disk via `mtools`/`mcopy` on the Proxmox host.
- **`generate_smbios(macserial_path, model) -> dict`**,
  **`patch_config(sample_plist_path, out_path, smbios)`** — the two steps
  above, usable standalone.
- **`VIRTIO_DRIVERS`** — tuple of `Virtio*.efi` filenames enabled by default
  (Blk/Net/PciDevice/Scsi/Serial/Virtio10/Gpu) -- enabling an entry whose bus
  isn't actually used is harmless (it just never matches a PCI device), so
  this is on unconditionally for forward-compatibility rather than tied to
  the profile's actual `disk_bus` choice.
- **`enable_drivers(config_path, names=VIRTIO_DRIVERS)`** — flips `Enabled`
  on for the named `UEFI.Drivers` entries already present in the plist at
  `config_path`, in place. **Not safe to assume the entries exist** --
  some hand-built configs (e.g. the original OSX-PROXMOX tool's live output,
  found 2026-07-23) only keep the drivers actually in use, not
  `Sample.plist`'s full disabled-placeholder list; in that case append fresh
  entries instead (see the live-EFI patch pattern used that day, not
  currently exposed as a reusable function -- `enable_drivers` alone is
  correct for a fresh `Sample.plist`-based build, which is all `efi build`
  itself produces).
- **`STANDARD_KEXTS`** — `dict[artifact_name, tuple[path_in_zip, ...]]` for
  the four kexts `Sample.plist` already references in `Kernel.Add`
  (Lilu/VirtualSMC/WhateverGreen/AppleALC) but whose actual files the
  OpenCore zip does not bundle (each is a separate Acidanthera project/release
  cadence). `install_kexts(cache_dir, kexts_dir)` fetches (checksum-verified)
  and copies them all.
- **`EXTRA_KERNEL_ADD`** / **`add_kernel_entries(config_path,
  entries=EXTRA_KERNEL_ADD)`** — `SMCProcessor.kext`/`SMCSuperIO.kext` have no
  `Sample.plist` placeholder at all (unlike the Virtio drivers), so this
  appends whole new `Kernel.Add` entries rather than flipping `Enabled` on an
  existing one; skips any `BundlePath` already present, so safe to call more
  than once. These two matter beyond "completeness": without them,
  `VirtualSMC.kext` alone can't answer most SMC sensor queries, which is what
  caused a real `PowerlogCore`/`SMCGetKeyFromIndex` CPU spin diagnosed live on
  a fresh boot (2026-07-23, via `/Library/Logs/DiagnosticReports/
  PerfPowerServices_*.cpu_resource.diag` -- macOS's own automatic
  excessive-CPU watchdog report).
- **`EfiError`** — raised when the extracted OpenCore archive doesn't have the
  expected layout.

### Why `qxl` costs nothing for macOS

Neither `qxl` nor Proxmox's other display options (`std`, `vmware`) have a
native macOS guest driver -- without real GPU passthrough, macOS always gets
an unaccelerated generic framebuffer regardless of which one is picked. So
`qxl`'s SPICE support (clipboard, dynamic resolution, lower latency than
noVNC, usable with `remote-viewer`) is a pure win for remote-console quality
with no acceleration trade-off either way. Real acceleration needs a
physical GPU dedicated via VFIO passthrough -- out of scope until a host
actually has a spare GPU (asgard-borr, checked 2026-07-23, has none; its only
`VGA compatible controller` is the server's Matrox BMC/IPMI chip, not a
passthrough candidate).
