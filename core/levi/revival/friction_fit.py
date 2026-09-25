"""Friction-fit composition: geometry as the fastener.

Studied from: lost-crafts-20260916/report.md [Batch 4] (Kigumi Joinery)

The studied shape: traditional joinery that uses *no fasteners* — parts
hold together because the interface geometry (tenon, mortise, taper)
creates interference, and friction on the contact surfaces does the
rest. Flexibility is a seismic strategy: joints that can slip a little
absorb energy instead of snapping.

LEVI-native re-expression: a small, honest mechanical model of that
idea. A joint is two matching interfaces (peg + socket) described by
contact area, interference (how much oversize the peg is), taper angle,
and the material's friction coefficient. From that geometry LEVI
computes:

* **fit class** — clearance / transition / interference from tolerances
* **holding force** — Coulomb friction over the elastic normal force
  raised by the interference fit
* **safety surface** — a rating of the contact quality (the skill
  interface is the safety surface: no clean interface, no joint)
* **seismic flexibility** — how much slip the joint tolerates before
  the holding force degrades, as an energy-absorption estimate

Honest limits: this is a first-order model (Coulomb friction, linear
elastic normal force), not finite-element analysis. Numbers are
comparative design guidance, not engineering sign-off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple


ORIGIN = "levi-revival/friction-fit"


class FitClass(str, Enum):
    CLEARANCE = "clearance"  # parts move freely — no joint
    TRANSITION = "transition"  # light touch — alignment only
    INTERFERENCE = "interference"  # friction does the work


# --- tolerance bands (fraction of nominal size) ---------------------------
_CLEARANCE_MIN = 0.0005  # >= 0.05% oversize clearance
_INTERFERENCE_MIN = -0.002  # <= 0.2% undersize starts real interference


@dataclass
class Interface:
    """One side of a joint: a peg or a socket described by geometry."""

    name: str
    role: str  # "peg" | "socket"
    nominal: float  # nominal contact width (mm)
    length: float  # contact length along insertion (mm)
    tolerance: float  # +/- machining tolerance (mm), >= 0
    taper_deg: float = 0.0  # wedge angle; 0 = parallel
    friction_mu: float = 0.35  # Coulomb coefficient of the material pair
    elastic_k: float = 100.0  # normal-force stiffness per mm of interference (N/mm)

    def __post_init__(self) -> None:
        if self.role not in ("peg", "socket"):
            raise ValueError(f"role must be 'peg' or 'socket', got {self.role!r}")
        for attr in ("nominal", "length", "tolerance", "friction_mu", "elastic_k"):
            if getattr(self, attr) < 0:
                raise ValueError(f"{attr} must be >= 0")
        if not (0.0 <= self.taper_deg <= 15.0):
            raise ValueError("taper_deg must be within 0..15 degrees")


@dataclass
class Joint:
    """A mated peg+socket pair: the whole joint lives or dies at the interface."""

    peg: Interface
    socket: Interface
    name: str = ""

    def __post_init__(self) -> None:
        if self.peg.role != "peg" or self.socket.role != "socket":
            raise ValueError("joint needs one peg and one socket")
        if not self.name:
            self.name = f"{self.peg.name}-{self.socket.name}"

    # -- geometry as fastener ------------------------------------------------
    def clearance(self) -> float:
        """Signed gap: socket min width minus peg max width (mm).

        Negative => interference (the peg is oversize).
        """
        socket_min = self.socket.nominal - self.socket.tolerance
        peg_max = self.peg.nominal + self.peg.tolerance
        return socket_min - peg_max

    def fit_class(self) -> FitClass:
        rel = self.clearance() / self.peg.nominal
        if rel >= _CLEARANCE_MIN:
            return FitClass.CLEARANCE
        if rel > _INTERFERENCE_MIN:
            return FitClass.TRANSITION
        return FitClass.INTERFERENCE

    def interference(self) -> float:
        """Oversize depth driving the elastic normal force (mm, >= 0)."""
        return max(0.0, -self.clearance())

    def contact_area(self) -> float:
        """Effective friction surface (mm^2), shortened by taper wedge-out."""
        import math

        wedge_loss = 1.0 - math.tan(math.radians(self.peg.taper_deg)) * 0.5
        width = self.peg.nominal - self.interference() * 0.5
        return max(0.0, width * self.peg.length * wedge_loss)

    def holding_force(self) -> float:
        """Estimated pull-apart resistance (N): mu * normal force.

        Normal force comes from the elastic interference squeeze.
        """
        normal = (
            self.peg.elastic_k * self.interference() * (1.0 + self.peg.taper_deg / 90.0)
        )
        return self.peg.friction_mu * normal

    # -- the skill interface is the safety surface ---------------------------
    def safety_surface(self) -> Tuple[float, List[str]]:
        """Score 0..1 of interface quality + the reasons."""
        notes: List[str] = []
        score = 1.0
        rel_tol = (self.peg.tolerance + self.socket.tolerance) / self.peg.nominal
        if rel_tol > 0.01:
            score -= 0.4
            notes.append("tolerances too loose for the nominal size")
        if self.peg.taper_deg > 5.0:
            score -= 0.2
            notes.append("steep taper wedges out contact area")
        if abs(self.peg.friction_mu - self.socket.friction_mu) > 0.05:
            score -= 0.15
            notes.append("mismatched friction data between the two sides")
        fit = self.fit_class()
        if fit is FitClass.CLEARANCE:
            score -= 0.5
            notes.append("clearance fit: geometry cannot hold, add a fastener")
        elif fit is FitClass.TRANSITION:
            notes.append("transition fit: holds only as alignment")
        else:
            notes.append("interference fit: geometry is the fastener")
        return max(0.0, round(score, 3)), notes

    # -- flexibility as seismic strategy -------------------------------------
    def seismic_slip_allowance(self) -> float:
        """Slip (mm) the joint can absorb before holding force degrades.

        Heuristic: a good friction joint trades a little slip for
        energy absorption — modeled as a fraction of contact length,
        scaled by the safety surface score.
        """
        score, _ = self.safety_surface()
        return round(self.peg.length * 0.02 * score, 3)


@dataclass
class Frame:
    """A composition of joints: the whole holds if every joint holds."""

    joints: List[Joint] = field(default_factory=list)

    def add(self, joint: Joint) -> None:
        self.joints.append(joint)

    def weakest(self) -> Tuple[Joint, float]:
        if not self.joints:
            raise ValueError("frame has no joints")
        return min(((j, j.holding_force()) for j in self.joints), key=lambda t: t[1])

    def total_holding(self) -> float:
        return sum(j.holding_force() for j in self.joints)

    def seismic_report(self) -> dict:
        """Per-joint slip allowance; the frame's flexibility budget."""
        return {j.name: j.seismic_slip_allowance() for j in self.joints}
