"""agent_sandbox — minimum-viable agent sandbox, no Docker, no VM, no root.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§5 — named recipe].

Shape studied: production agent containment built from primitives —
bubblewrap + Landlock + seccomp + PR_SET_NO_NEW_PRIVS + non-root +
cgroups — instead of a container daemon or a virtual machine.

Mechanism:
* PRIMITIVES: the containment primitives with what each one guarantees
* PROFILES: three ready-made recipes — agent-exec (offline),
  agent-exec-network (declared egress only), interactive-shell
* recommended(): build a SandboxSpec from a profile with overrides
* validate(): fail-closed checks; build() refuses to emit a recipe that
  violates them
* to_bwrap_argv(): renders the spec as a bubblewrap-style argv —
  a *recipe*, never executed by this module
* dry_run(): human-readable walkthrough of what the sandbox would do

Honest limits: the argv mapping is a heuristic translation of the spec
into bubblewrap-shaped flags, not a tested invocation. Landlock and
seccomp policy *contents* (which syscalls, which paths) are the
operator's job — this module enforces that a policy is declared, not
what it says. It plans sandboxes; it never spawns them.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/agent_sandbox"

#: Containment primitives and the guarantee each one provides.
PRIMITIVES: Dict[str, str] = {
    "bubblewrap": "unprivileged sandbox launcher; owns the namespace setup",
    "landlock": "unprivileged filesystem access rules, stacked per layer",
    "seccomp": "syscall allowlist; the kernel refuses anything unlisted",
    "no_new_privs": "PR_SET_NO_NEW_PRIVS: exec can never gain privilege",
    "non_root": "everything runs as an unprivileged uid, mapped, never 0",
    "cgroups": "cpu/memory/pid ceilings enforced by the kernel",
    "readonly_root": "the root filesystem is mounted read-only",
    "net_isolation": "no network namespace member: zero egress by default",
}

#: Ready-made profiles: primitive set + network stance.
PROFILES: Dict[str, Dict[str, object]] = {
    "agent-exec": {
        "primitives": [
            "bubblewrap",
            "landlock",
            "seccomp",
            "no_new_privs",
            "non_root",
            "cgroups",
            "readonly_root",
            "net_isolation",
        ],
        "allow_network": False,
        "blurb": "offline agent worker: compute only, no egress",
    },
    "agent-exec-network": {
        "primitives": [
            "bubblewrap",
            "landlock",
            "seccomp",
            "no_new_privs",
            "non_root",
            "cgroups",
            "readonly_root",
        ],
        "allow_network": True,
        "blurb": "networked agent worker: declared egress only, seccomp mandatory",
    },
    "interactive-shell": {
        "primitives": [
            "bubblewrap",
            "landlock",
            "no_new_privs",
            "non_root",
            "cgroups",
            "net_isolation",
        ],
        "allow_network": False,
        "blurb": "human-driven shell: looser syscall set, still no root, no net",
    },
}


@dataclass
class SandboxSpec:
    """A validated-by-construction sandbox recipe."""

    name: str
    primitives: List[str]
    allow_network: bool = False
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=lambda: ["/proc", "/sys"])
    cpu_seconds: Optional[int] = None
    memory_mb: Optional[int] = 512
    max_pids: int = 64

    def has(self, primitive: str) -> bool:
        return primitive in self.primitives


def recommended(
    profile: str,
    name: Optional[str] = None,
    allowed_paths: Optional[List[str]] = None,
    memory_mb: Optional[int] = None,
) -> SandboxSpec:
    """Build a SandboxSpec from a named profile with optional overrides."""
    if profile not in PROFILES:
        raise KeyError(f"unknown sandbox profile {profile!r}")
    base = PROFILES[profile]
    return SandboxSpec(
        name=name or profile,
        primitives=list(base["primitives"]),  # type: ignore[arg-type]
        allow_network=bool(base["allow_network"]),
        allowed_paths=list(allowed_paths or []),
        memory_mb=512 if memory_mb is None else memory_mb,
    )


def validate(spec: SandboxSpec) -> List[str]:
    """Fail-closed checks. Empty list means the recipe may be emitted."""
    violations: List[str] = []
    for mandatory in ("no_new_privs", "non_root"):
        if not spec.has(mandatory):
            violations.append(f"missing mandatory primitive: {mandatory}")
    if spec.allow_network and not spec.has("seccomp"):
        violations.append("network allowed without a seccomp syscall allowlist")
    if spec.allow_network and spec.has("net_isolation"):
        violations.append("net_isolation contradicts allow_network=True")
    if not spec.allow_network and not spec.has("net_isolation"):
        violations.append("offline sandbox should declare net_isolation")
    for unknown in spec.primitives:
        if unknown not in PRIMITIVES:
            violations.append(f"unknown primitive: {unknown}")
    if spec.memory_mb is not None and spec.memory_mb <= 0:
        violations.append("memory_mb must be positive")
    if spec.max_pids < 1:
        violations.append("max_pids must be >= 1")
    return violations


def build(spec: SandboxSpec) -> SandboxSpec:
    """Return ``spec`` if valid, else raise — fail closed, never half-built."""
    violations = validate(spec)
    if violations:
        raise ValueError("sandbox spec refused: " + "; ".join(violations))
    return spec


def to_bwrap_argv(spec: SandboxSpec) -> List[str]:
    """Render the spec as a bubblewrap-shaped argv (recipe only, heuristic)."""
    build(spec)  # fail closed: never render an invalid spec
    argv = ["bwrap"]
    if spec.has("non_root") or spec.has("no_new_privs"):
        argv += ["--unshare-user", "--uid", "1000", "--gid", "1000"]
    argv += ["--unshare-pid", "--unshare-ipc", "--unshare-uts", "--die-with-parent"]
    if spec.has("net_isolation"):
        argv.append("--unshare-net")
    if spec.has("readonly_root"):
        argv += ["--ro-bind", "/", "/"]
    for path in spec.allowed_paths:
        argv += ["--bind", path, path]
    for path in spec.denied_paths:
        argv += (
            ["--tmpfs", path]
            if path in ("/proc",)
            else ["--ro-bind", "/dev/null", path]
        )
    if spec.has("seccomp"):
        argv += ["--seccomp", "<allowlist-fd>"]
    argv += ["--", "<command>"]
    return argv


def dry_run(spec: SandboxSpec) -> List[str]:
    """Human-readable walkthrough of what the sandbox would enforce."""
    build(spec)
    steps = [
        f"launch '{spec.name}' via bubblewrap as uid 1000 (never root)",
        "PR_SET_NO_NEW_PRIVS: no exec path can ever gain privilege",
    ]
    if spec.has("landlock"):
        steps.append("landlock: filesystem rules stacked, unprivileged")
    if spec.has("seccomp"):
        steps.append("seccomp: only allowlisted syscalls reach the kernel")
    if spec.has("readonly_root"):
        steps.append("root filesystem mounted read-only")
    for path in spec.allowed_paths:
        steps.append(f"bind {path} read-write into the sandbox")
    if spec.has("net_isolation"):
        steps.append("no network namespace: zero egress, loopback only")
    elif spec.allow_network:
        steps.append("network allowed: egress must be declared per-host elsewhere")
    if spec.memory_mb:
        steps.append(
            f"cgroup ceiling: {spec.memory_mb}MB RAM, {spec.max_pids} pids max"
        )
    return steps
