"""microvm — hardware isolation at microVM cold-start speed.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md [§5].

Shape studied: Firecracker-style microVMs — hardware isolation with
sub-125ms cold starts — sitting between namespace isolation (cheap, no
hardware boundary) and full VMs (strong, slow, heavy).

Mechanism:
* MicroVM: a VM spec (vCPU, memory, kernel, rootfs) with a heuristic
  cold-start estimator; boots are *planned*, never executed
* COLD_START_BUDGET_MS: the 125ms bar a microVM must clear
* Fleet: a pool of microVMs with burst scaling and a lane picker —
  given a workload's isolation need and startup budget, choose the
  cheapest lane that satisfies both: namespace < microvm < fullvm
* cost estimates per lane (heuristic unit prices, labeled as such)

Honest limits: cold-start times are estimated from a simple heuristic
formula, not measured; per-lane prices are illustrative constants, not
quotes; nothing here boots a real VM.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/microvm"

#: The cold-start bar a microVM must clear, in milliseconds.
COLD_START_BUDGET_MS = 125.0

#: Heuristic boot-time model: base + per-vCPU + per-MB-of-guest-RAM.
_BOOT_BASE_MS = 18.0
_BOOT_PER_VCPU_MS = 9.0
_BOOT_PER_GUEST_MB_MS = 0.06

#: Heuristic hourly price per unit, in dollars (illustrative, not quotes).
LANE_PRICE_PER_HOUR = {
    "namespace": 0.001,
    "microvm": 0.012,
    "fullvm": 0.096,
}

#: Heuristic steady-state memory overhead per lane, in MB.
LANE_OVERHEAD_MB = {
    "namespace": 0.01,
    "microvm": 6.0,
    "fullvm": 180.0,
}

LANES = ("namespace", "microvm", "fullvm")


@dataclass
class MicroVM:
    """A microVM spec. Boots are planned, never executed."""

    name: str
    vcpu: int = 1
    memory_mb: int = 128
    kernel: str = "vmlinux-micro"
    rootfs_mb: int = 64

    def __post_init__(self):
        if self.vcpu < 1:
            raise ValueError("vcpu must be >= 1")
        if self.memory_mb < 32:
            raise ValueError("memory_mb must be >= 32")

    def estimated_cold_start_ms(self) -> float:
        """Heuristic cold-start estimate (formula, not a measurement)."""
        return (
            _BOOT_BASE_MS
            + _BOOT_PER_VCPU_MS * self.vcpu
            + _BOOT_PER_GUEST_MB_MS * self.memory_mb
        )

    def meets_budget(self, budget_ms: float = COLD_START_BUDGET_MS) -> bool:
        return self.estimated_cold_start_ms() <= budget_ms


@dataclass
class Workload:
    """What needs to run, and what it demands."""

    name: str
    needs_hw_isolation: bool
    startup_budget_ms: float
    memory_mb: int = 128


@dataclass
class Placement:
    workload: str
    lane: str
    cold_start_ms: float
    reason: str


def pick_lane(workload: Workload) -> Placement:
    """Cheapest lane satisfying the workload's isolation + startup demands."""
    if not workload.needs_hw_isolation:
        return Placement(
            workload=workload.name,
            lane="namespace",
            cold_start_ms=1.0,
            reason="no hardware boundary needed: namespaces are ~1KB and instant",
        )
    micro = MicroVM(name=workload.name, memory_mb=workload.memory_mb)
    micro_ms = micro.estimated_cold_start_ms()
    if micro_ms <= workload.startup_budget_ms:
        return Placement(
            workload=workload.name,
            lane="microvm",
            cold_start_ms=micro_ms,
            reason=f"hardware isolation within budget ({micro_ms:.1f}ms <= {workload.startup_budget_ms}ms)",
        )
    fullvm_ms = 800.0  # heuristic: a full guest boot, illustrative
    return Placement(
        workload=workload.name,
        lane="fullvm",
        cold_start_ms=fullvm_ms,
        reason="microVM cannot meet the startup budget; full VM is the fallback",
    )


@dataclass
class Fleet:
    """A pool of microVMs with burst scaling and cost accounting."""

    vms: List[MicroVM] = field(default_factory=list)

    def add(self, vm: MicroVM) -> None:
        if any(v.name == vm.name for v in self.vms):
            raise ValueError(f"duplicate vm name {vm.name!r}")
        self.vms.append(vm)

    def burst(self, count: int, template: MicroVM) -> List[MicroVM]:
        """Plan a burst of ``count`` VMs from a template. Raises if any
        would miss the cold-start budget — a burst that can't start fast
        is not a microVM burst."""
        if count < 1:
            raise ValueError("count must be >= 1")
        if not template.meets_budget():
            raise ValueError(
                f"template {template.name!r} misses the {COLD_START_BUDGET_MS}ms "
                f"budget ({template.estimated_cold_start_ms():.1f}ms)"
            )
        return [
            MicroVM(
                name=f"{template.name}-{i}",
                vcpu=template.vcpu,
                memory_mb=template.memory_mb,
                kernel=template.kernel,
                rootfs_mb=template.rootfs_mb,
            )
            for i in range(count)
        ]

    def total_memory_mb(self) -> int:
        return sum(v.memory_mb for v in self.vms)

    def cost_per_hour(self, lane: str = "microvm") -> float:
        """Heuristic hourly cost for the fleet on ``lane`` pricing."""
        if lane not in LANE_PRICE_PER_HOUR:
            raise KeyError(f"unknown lane {lane!r}")
        return len(self.vms) * LANE_PRICE_PER_HOUR[lane]

    def over_budget(self, budget_ms: float = COLD_START_BUDGET_MS) -> List[str]:
        """Names of fleet VMs missing the cold-start budget."""
        return [v.name for v in self.vms if not v.meets_budget(budget_ms)]
