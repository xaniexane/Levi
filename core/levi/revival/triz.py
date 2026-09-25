"""TRIZ contradiction matrix: when two good things fight, look up what won before.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #21)

The mechanism is deceptively simple: most engineering disagreements are
contradictions — improving X makes Y worse. Formulate the problem as
"what fights what", find that contradiction in the matrix, and it hands
you a short list of inventive principles: generic moves that historically
resolved exactly that kind of fight.

This module keeps the *mechanism* (parameter x parameter -> principles +
application worksheet) with an ORIGINAL, compact parameter set (~20
parameters) and ORIGINAL one-line principle wordings (~20 principles).
The point is the lookup, not encyclopedic coverage of anyone else's
tables: the matrix is honest about its size and its wordings are LEVI's
own.

A "contradiction" is improving parameter A while parameter B degrades.
``Matrix.lookup(improving, worsening)`` returns the principles
historically suited to that clash, plus the worksheet template that
walks the solver from principle to concrete idea.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/triz"

# --------------------------------------------------------------------------
# The compact parameter set (LEVI's own ~20-word vocabulary for "what fights
# what"). Each entry: key -> plain-language description.
# --------------------------------------------------------------------------
PARAMETERS: Dict[str, str] = {
    "weight": "mass of the object or system",
    "size": "length, area, or volume it occupies",
    "speed": "how fast it moves or responds",
    "strength": "resistance to breaking or failing",
    "durability": "how long it lasts in service",
    "energy_use": "power or energy it consumes",
    "force": "output it can exert",
    "precision": "accuracy and tolerance of its behavior",
    "reliability": "consistency over repeated use",
    "complexity": "number of parts and interdependencies",
    "manufacturability": "ease and cost of making it",
    "maintainability": "ease of repairing and servicing",
    "safety": "risk of harm when it fails or is misused",
    "adaptability": "ability to handle new conditions",
    "universality": "range of cases it covers",
    "waste": "material or energy it discards",
    "automation": "how much runs without a human in the loop",
    "information": "how much it must know or measure",
    "stability": "resistance to disturbance",
    "cost": "money to build, run, or replace",
}

# --------------------------------------------------------------------------
# Twenty inventive principles, worded fresh in LEVI's own voice.
# Key -> one-line wording.
# --------------------------------------------------------------------------
PRINCIPLES: Dict[str, str] = {
    "P01": "Split the thing into independent parts that can move or fail separately.",
    "P02": "Pull out the part that causes the trouble — or isolate the quality you actually need.",
    "P03": "Give each region or moment the locally best property instead of one global compromise.",
    "P04": "Flip the geometry: make convex concave, stand it on its head, turn it inside out.",
    "P05": "Merge things: let one part, surface, or moment do several jobs at once.",
    "P06": "Spread the job across many: many cheap instances instead of one heroic one.",
    "P07": "Nest it: put one thing inside another, each carrying what the other can't.",
    "P08": "Lean on the opposite force: balance, float, or buoy the load instead of fighting it.",
    "P09": "Act before you need to: pre-position, pre-stress, pre-cool so the moment is already handled.",
    "P10": "Act early where you can't act later: do the useful work before conditions close in.",
    "P11": "Put in a guard up front: a sacrificial, cheap layer that absorbs the failure first.",
    "P12": "Make the parts equally stressed so nothing is the weak link or the dead weight.",
    "P13": "Do the reverse of the usual motion: instead of moving the object, move what surrounds it.",
    "P14": "Use a curve where a straight line fights you: bend, spiral, roll instead of push.",
    "P15": "Let it move: replace rigid links with hinges, sliders, and joints that yield.",
    "P16": "Overshoot on purpose: do too much of the cheap action so the expensive one gets easier.",
    "P17": "Jump a dimension: solve in 2D what fails in 1D, in 3D what fails in 2D, in time what fails in space.",
    "P18": "Make it vibrate or pulse: replace steady effort with rhythm, bursts, or oscillation.",
    "P19": "Go periodic: intermittent action instead of continuous strain — on, off, on, off.",
    "P20": "Let it change itself: make the structure self-adjusting so it serves each moment differently.",
}


def _norm_param(ref: str) -> str:
    key = ref.strip().lower().replace(" ", "_")
    if key in PARAMETERS:
        return key
    raise ValueError(
        f"unknown parameter: {ref!r}. Available: {', '.join(sorted(PARAMETERS))}"
    )


@dataclass
class Matrix:
    """The contradiction lookup: (improving, worsening) -> principles.

    The default matrix is seeded with a compact, hand-built set of
    contradiction -> principle mappings in LEVI's own wording. Entries
    can be added or replaced with ``set()``; the matrix is yours to
    grow as you learn which principles win for your domain.
    """

    table: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.table:
            self.table = dict(_DEFAULT_TABLE)

    def set(self, improving: str, worsening: str, principles: List[str]) -> None:
        """Teach the matrix one contradiction -> principle list mapping."""
        a = _norm_param(improving)
        b = _norm_param(worsening)
        unknown = [p for p in principles if p not in PRINCIPLES]
        if unknown:
            raise ValueError(f"unknown principle keys: {unknown}")
        self.table[(a, b)] = list(principles)

    def lookup(self, improving: str, worsening: str) -> Dict[str, object]:
        """Return the principles for one contradiction.

        Order is symmetric: a contradiction recorded as (A fights B)
        is also found as (B fights A). If the exact pair is unknown,
        the module falls back to principles that touch *either*
        parameter, and says so honestly instead of inventing an entry.
        """
        a = _norm_param(improving)
        b = _norm_param(worsening)
        keys = self.table.get((a, b)) or self.table.get((b, a))
        if keys is not None:
            return {
                "improving": a,
                "worsening": b,
                "principles": [{"key": k, "wording": PRINCIPLES[k]} for k in keys],
                "exact_match": True,
            }
        fallback = self._fallback(a, b)
        return {
            "improving": a,
            "worsening": b,
            "principles": [{"key": k, "wording": PRINCIPLES[k]} for k in fallback],
            "exact_match": False,
        }

    def _fallback(self, a: str, b: str) -> List[str]:
        """Principles that appear for either parameter anywhere."""
        seen: List[str] = []
        for (x, y), keys in self.table.items():
            if a in (x, y) or b in (x, y):
                for k in keys:
                    if k not in seen:
                        seen.append(k)
        return seen[:6]

    def known_contradictions(self) -> List[Tuple[str, str]]:
        return sorted(self.table)


# --------------------------------------------------------------------------
# Seed data: compact contradiction -> principle mappings (LEVI's own).
# --------------------------------------------------------------------------
_DEFAULT_TABLE: Dict[Tuple[str, str], List[str]] = {
    ("weight", "strength"): ["P05", "P07", "P12"],
    ("size", "speed"): ["P06", "P13", "P17"],
    ("speed", "precision"): ["P09", "P15", "P19"],
    ("strength", "weight"): ["P05", "P07", "P12"],
    ("durability", "cost"): ["P09", "P11", "P06"],
    ("energy_use", "force"): ["P08", "P16", "P18"],
    ("complexity", "reliability"): ["P01", "P02", "P05"],
    ("precision", "manufacturability"): ["P09", "P14", "P03"],
    ("safety", "speed"): ["P09", "P11", "P10"],
    ("adaptability", "complexity"): ["P15", "P20", "P03"],
    ("automation", "information"): ["P06", "P05", "P20"],
    ("maintainability", "complexity"): ["P01", "P07", "P15"],
    ("universality", "precision"): ["P03", "P20", "P17"],
    ("waste", "cost"): ["P16", "P02", "P11"],
    ("stability", "adaptability"): ["P15", "P12", "P18"],
}


# --------------------------------------------------------------------------
# Application worksheet: principle -> concrete idea
# --------------------------------------------------------------------------
def worksheet(lookup_result: Dict[str, object], problem: str) -> Dict[str, object]:
    """Build the application worksheet for one resolved contradiction.

    Each suggested principle becomes one row the solver must answer:
    *how would you apply this wording to YOUR problem?* The worksheet
    doesn't solve anything — it converts a principle list into a
    forced creative checklist, which is where the mechanism actually
    does its work.
    """
    rows = []
    for p in lookup_result["principles"]:
        rows.append(
            {
                "principle": p["key"],
                "wording": p["wording"],
                "prompt": (
                    f"How could '{p['wording']}' resolve the clash between "
                    f"'{lookup_result['improving']}' and "
                    f"'{lookup_result['worsening']}' in this problem?"
                ),
                "idea": "",  # the solver fills this in
            }
        )
    return {
        "problem": problem,
        "improving": lookup_result["improving"],
        "worsening": lookup_result["worsening"],
        "exact_match": lookup_result["exact_match"],
        "rows": rows,
    }
