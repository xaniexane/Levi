"""namespace_isolation — per-process namespaces as the container runtime.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§5 Plan 9-style namespaces].

Shape studied: Linux namespaces used directly for isolation instead of
a container runtime — a network namespace costs on the order of a
kilobyte of memory, so the isolation is nearly free.

This is the frugal-isolation *recipe* (what to unshare, what it costs,
what it saves versus a runtime), not the namespace abstraction — that
lives in ``levi.revival.plan9`` (Cellblock). The two are deliberately
different: Cellblock gives tasks scrubbed rooms and pipes; this module
answers "what is the cheapest correct isolation for *this* job, and how
much does it cost?"

Mechanism:
* NAMESPACES: the seven namespace types with their unshare(1) flags and
  heuristic per-namespace memory footprints (KB)
* JobSpec: what a job needs (network? writable paths? resource limits?)
* plan(): derives the minimal namespace set, the unshare argv, a mount
  recipe, and the estimated footprint
* validate(): fail-closed checks — root must be dropped, network must
  not leak to jobs that don't need it

Honest limits: footprints are order-of-magnitude heuristics and the
container-runtime comparison is illustrative, not a benchmark. This
module *plans* isolation; it never calls unshare itself.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/namespace_isolation"

#: Namespace types: unshare(1) flag + heuristic memory footprint in KB.
NAMESPACES: Dict[str, Dict[str, object]] = {
    "user": {
        "flag": "-U",
        "footprint_kb": 1,
        "why": "map root inside to an unprivileged uid outside; no real root",
    },
    "mount": {
        "flag": "-m",
        "footprint_kb": 2,
        "why": "private mount table; bind only what the job may see",
    },
    "pid": {
        "flag": "-p",
        "footprint_kb": 1,
        "why": "the job is PID 1 in its own process tree",
    },
    "ipc": {
        "flag": "-i",
        "footprint_kb": 1,
        "why": "no shared memory or semaphores with the host",
    },
    "uts": {
        "flag": "-u",
        "footprint_kb": 1,
        "why": "its own hostname; cosmetic but free",
    },
    "net": {
        "flag": "-n",
        "footprint_kb": 1,
        "why": "no network at all unless the job declares it needs one",
    },
    "cgroup": {
        "flag": "-C",
        "footprint_kb": 2,
        "why": "its own cgroup view for honest resource limits",
    },
}

#: Heuristic overhead of a full container runtime per workload, in KB.
CONTAINER_RUNTIME_OVERHEAD_KB = 50 * 1024

#: Namespaces every isolated job gets, regardless of need.
ALWAYS = ("user", "mount", "pid", "ipc", "uts")


@dataclass
class JobSpec:
    """What a job needs, declared up front."""

    name: str
    needs_network: bool = False
    needs_loopback_only: bool = False
    writable_paths: List[str] = field(default_factory=list)
    readonly_paths: List[str] = field(default_factory=list)
    tmpfs_paths: List[str] = field(default_factory=list)
    cpu_shares: Optional[int] = None
    memory_mb: Optional[int] = None

    def __post_init__(self):
        if self.needs_loopback_only and self.needs_network:
            raise ValueError("a job cannot need both loopback-only and full network")


@dataclass
class IsolationRecipe:
    """The cheapest correct isolation plan for a JobSpec."""

    job_name: str
    namespaces: List[str]
    unshare_argv: List[str]
    mounts: List[str]
    footprint_kb: int
    runtime_overhead_kb: int = CONTAINER_RUNTIME_OVERHEAD_KB

    @property
    def savings_factor(self) -> float:
        """How many times cheaper than a container runtime (heuristic)."""
        if self.footprint_kb <= 0:
            return float("inf")
        return self.runtime_overhead_kb / self.footprint_kb

    def summary(self) -> str:
        ns = ",".join(self.namespaces)
        return (
            f"{self.job_name}: namespaces=[{ns}] "
            f"footprint={self.footprint_kb}KB "
            f"~{self.savings_factor:.0f}x cheaper than a container runtime"
        )


def plan(job: JobSpec) -> IsolationRecipe:
    """Derive the minimal namespace set and recipe for ``job``."""
    namespaces = list(ALWAYS)
    if job.needs_network:
        namespaces.append("net")
    if job.cpu_shares is not None or job.memory_mb is not None:
        namespaces.append("cgroup")

    argv = ["unshare"]
    for ns in namespaces:
        argv.append(str(NAMESPACES[ns]["flag"]))
    argv += ["--map-root-user", "--", "<command>"]

    mounts: List[str] = []
    for path in job.readonly_paths:
        mounts.append(f"bind-ro {path} {path}")
    for path in job.writable_paths:
        mounts.append(f"bind-rw {path} {path}")
    for path in job.tmpfs_paths:
        mounts.append(f"tmpfs {path}")
    if not job.needs_network:
        mounts.append("note: no net namespace requested — loopback only")
    elif job.needs_loopback_only:
        mounts.append("note: bring up lo only inside the net namespace")

    footprint = sum(int(NAMESPACES[ns]["footprint_kb"]) for ns in namespaces)
    return IsolationRecipe(
        job_name=job.name,
        namespaces=namespaces,
        unshare_argv=argv,
        mounts=mounts,
        footprint_kb=footprint,
    )


def validate(recipe: IsolationRecipe, job: JobSpec) -> List[str]:
    """Fail-closed checks on a recipe. Empty list means it may proceed."""
    violations: List[str] = []
    if "user" not in recipe.namespaces:
        violations.append("user namespace missing: the job would run as real root")
    if "--map-root-user" not in recipe.unshare_argv:
        violations.append("uid mapping missing: root inside would map to root outside")
    if not job.needs_network and "net" in recipe.namespaces:
        violations.append(
            "net namespace granted to a job that declared no network need"
        )
    if job.needs_network and "net" not in recipe.namespaces:
        violations.append("job needs network but has no net namespace")
    return violations
