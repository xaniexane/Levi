# LEVI Linux Computer

The LEVI Linux computer is a **reproducible LEVI environment on Chauncey's own
hardware** — his phone and his Linux machines. It is explicitly NOT hosted
cloud infrastructure: there is no LEVI server farm, no rented VM, no SaaS
control plane. Everything below runs on machines he owns, with free software,
and LEVI's core stays stdlib-only.

Two halves:

- **(a) Termux + proot Ubuntu on Android** — a full Linux userland for LEVI on
  his phone (`~/workspace/your_files/levi-termux/ubuntu-proot.sh`).
- **(b) `levi sandbox` on Linux hosts** — an isolated environment for running
  untrusted or experimental LEVI work (`core/levi/sandbox/`, `levi sandbox`).

Related but different: `levi.surgeon.sandbox` is the Stage-1 propose → HITL →
apply gate. It inspects *text* and never executes anything. `levi sandbox`
(the subject of this doc) *executes commands* — that is why its isolation
contracts below matter.

---

## (a) Termux + proot Ubuntu on Android

Phones are hostile to real toolchains: Termux gives you a shell but no
standard Linux userland (glibc quirks, packages that must build from source).
The fix is the hard-route classic: **proot-distro** — a user-mode `proot`
rootfs that needs no root on the phone.

```
Phone (Android)
 └─ Termux
     ├─ native LEVI ............ setup.sh          (fast, minimal)
     └─ proot-distro → Ubuntu
         └─ full LEVI .......... ubuntu-proot.sh   (full Linux userland)
```

`ubuntu-proot.sh` (run **inside Termux** on the phone) does this:

1. **Environment + network checks.** Refuses to run outside Termux; checks
   connectivity first and **fails loudly with guidance** when offline —
   everything it does (apt, the ~100MB Ubuntu rootfs, LEVI itself) needs the
   network, so it says so up front instead of dying mid-`apt-get`.
2. **Installs `proot-distro`** via `pkg` (skipped if present).
3. **Installs the Ubuntu rootfs** (skipped if already installed; `--force`
   reinstalls).
4. **Provisions the userland** inside Ubuntu: `build-essential`, `python3`,
   `pip`, `git`, `curl`, `ca-certificates` — apt is idempotent, so re-running
   is safe.
5. **Installs LEVI** into `/root/levi` — either by streaming
   `levi-termux.tar.gz` through `proot-distro login` into the rootfs (no temp
   copy on the phone), or by `git clone` with `--clone`. Existing installs are
   pulled, not re-cloned, unless `--force`.
6. **Installs launchers**: a `levi` launcher inside Ubuntu (real
   `pip install -e .` first, PYTHONPATH wrapper fallback — LEVI core is
   stdlib-only so the fallback needs zero compilation), plus a Termux-side
   `levi-ubuntu` shortcut: `levi-ubuntu status`, `levi-ubuntu agent chat`, or
   bare `levi-ubuntu` for an interactive Ubuntu shell.
7. **Smoke-tests** `levi status` inside the proot.

Idempotent where reasonable: every step checks before it acts. The script is
**additive** — it does not modify `setup.sh` or `levi-termux.tar.gz`; the
native-Termux LEVI and the proot-Ubuntu LEVI are independent installs, each
with its own `~/.levi` data.

### Honest limits of the phone path

- **proot is not a VM and not a container.** There is no separate kernel;
  user-mode emulation only. Kernel modules, raw sockets, and anything
  kernel-level will not work.
- The proot shares the phone's network and storage; its privacy boundary is
  the same as Termux itself.
- On-device AI (`levi-local`/llama-server, torch training) has no Android
  build — LEVI inside the proot still falls back to the offline rule engine,
  honestly reported.
- pip on a phone CPU is slow; prefer the PYTHONPATH path when in a hurry.

---

## (b) `levi sandbox` on Linux hosts

`levi sandbox run -- <cmd>` executes a command in an isolated environment on
a Linux machine; `levi sandbox info` prints every backend and its isolation
contract. Backend selection is best-first and automatic:

| Backend | Tool | Isolation level | What you actually get |
|---|---|---|---|
| `bubblewrap` | `bwrap` | **strong** | user/pid/ipc/uts namespaces; whole tree read-only; private tmpfs HOME; no network by default |
| `unshare` | `unshare -Ur` | **basic** | user + mount namespaces only; fresh HOME dir |
| `subprocess` | (none) | **none — degraded** | no isolation at all; LOUD warning + `--i-understand` required |

### What each backend honestly guarantees

**bubblewrap (strong).** Guarantees: new user namespace (uid 0 inside,
unprivileged outside), new pid/ipc/uts namespaces, the entire filesystem
bound read-only with only HOME and /tmp writable (tmpfs), a private empty
HOME per run (your dotfiles and `~/.levi` stay outside), no network unless
`--net` is passed, and `--die-with-parent`. Limitations: it shares the host
kernel (kernel exploits are out of scope); with `--net` the sandbox sees your
real, unfiltered network; it needs unprivileged user namespaces enabled.

**unshare (basic).** Guarantees: a user namespace (root inside, unprivileged
outside), a mount namespace (mount changes stay inside), and a fresh empty
HOME directory for the run. Limitations, stated plainly: **no filesystem
hiding** — your files are still visible *and writable*; **no network
isolation**; **no pid/ipc isolation** — host processes are visible. It is
weaker than bubblewrap in every dimension.

**subprocess (none, degraded).** Guarantees nothing — it is the same process
tree, filesystem, HOME and network as you. It exists only so `levi sandbox
run` still functions on minimal hosts. The CLI prints a LOUD banner and
**refuses to run** unless you pass `--i-understand`. Do not run untrusted
code here.

### Design rules (binding)

1. **Never claim more isolation than provided.** Each backend carries a
   machine-readable contract (`BackendSpec`: guarantees + limitations); the
   CLI prints the backend name and isolation level *before* executing.
2. **No silent downgrades.** `--backend bubblewrap` on a host without `bwrap`
   is an error, not a quiet fallback to `unshare`. A forced backend that is
   unavailable raises.
3. **Network is off by default** under bubblewrap (empty network namespace);
   `--net` opts in explicitly and is reported on the run line.
4. **The degraded backend is opt-in and loud.** `PermissionError` in the
   library, banner + refusal in the CLI, `--i-understand` to proceed.

### Examples

```bash
levi sandbox info
levi sandbox run -- pytest tests/test_sandbox.py -x
levi sandbox run --net -- python3 tools/fetch_public_feed.py
levi sandbox run --backend unshare -- make -C /tmp/experiment
levi sandbox run --backend subprocess --i-understand -- ./trusted-local.sh
```

### Shared command name (backward compatibility)

The `sandbox` command name predates this module: `levi sandbox --path <dir>`
is the older syntax+smoke check from the factory track, and it still works
unchanged. The Linux-computer subcommands (`run`, `info`) are attached to the
same command; with no subcommand, the legacy behavior runs. Both are honest
about what they are — the legacy check never claimed isolation, and
`levi sandbox run/info` never claims more than its backend provides.

### Scope note

This is a pragmatic isolation ladder for *Chauncey's own machines*, not a
security boundary for hostile multi-tenant workloads. For genuinely
adversarial code, use a dedicated VM or throwaway hardware — `levi sandbox`
says exactly what it is on every run so that decision stays informed.
