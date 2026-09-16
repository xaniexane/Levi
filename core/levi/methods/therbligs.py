"""Therbligs: elemental motion vocabulary for task analysis.

History: Frank (and Lillian) Gilbreth's motion-study vocabulary — 17
(later 18) *elemental motions* into which any manual task can be
decomposed: Search, Find, Select, Grasp, Hold, Transport Loaded, Transport
Empty, Position, Pre-Position, Assemble, Disassemble, Use, Inspect,
Release Load, Unavoidable Delay, Avoidable Delay, Plan, Rest. Plotted on
the SIMO chart (Simultaneous Motion Chart) with timings, they reveal which
elements are waste. (The name is "Gilbreth" spelled backward, minus the
transposed *th* — a trademark dodge against Taylor's camp.)

The mechanism is a *finite vocabulary of waste*: once you can name
"Search" and "Select" as distinct elements, you can see that a workflow
spends 40% of its time in them — and redesign to eliminate them. Naming
precedes fixing.

In LEVI: therblig analysis for *digital* motions. A laborious workflow is
decomposed into elemental ops with timings; :meth:`TaskPlan.analyze`
reports the time share per therblig and flags the waste elements —
Search, Select, Avoidable Delay, Plan-as-rework, Rest-as-waiting — as
automation candidates. The assistant is the motion-study analyst you never
hired. Plans persist as JSON under ``~/.levi/methods/``.

Honesty: USEFUL PATTERN — absorbed into industrial engineering long ago;
the vocabulary survives in textbooks, not on factory floors. Revived here
as a measurement discipline, not a science of one best way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import _persist


# ---------------------------------------------------------------------------
# The 18 therbligs. ``effective`` follows the Gilbreth classification:
# the "do" therbligs advance the work; the rest are candidates for
# elimination or reduction.
# ---------------------------------------------------------------------------

THERBLIGS: tuple[dict, ...] = (
    {"name": "Search", "code": "Sh", "effective": False,
     "blurb": "hunting for the object, file, thread, or control"},
    {"name": "Find", "code": "F", "effective": False,
     "blurb": "the moment of locating what was sought"},
    {"name": "Select", "code": "St", "effective": False,
     "blurb": "choosing among alternatives"},
    {"name": "Grasp", "code": "G", "effective": True,
     "blurb": "taking hold of the object of work"},
    {"name": "Hold", "code": "H", "effective": False,
     "blurb": "retaining without progressing"},
    {"name": "Transport Loaded", "code": "TL", "effective": True,
     "blurb": "moving the work itself"},
    {"name": "Transport Empty", "code": "TE", "effective": False,
     "blurb": "moving to the work (travel without payload)"},
    {"name": "Position", "code": "P", "effective": True,
     "blurb": "orienting for the next operation"},
    {"name": "Pre-Position", "code": "PP", "effective": True,
     "blurb": "staging so the next operation is trivial"},
    {"name": "Assemble", "code": "A", "effective": True,
     "blurb": "putting parts together"},
    {"name": "Disassemble", "code": "DA", "effective": True,
     "blurb": "taking apart for inspection or rework"},
    {"name": "Use", "code": "U", "effective": True,
     "blurb": "the actual value-adding operation"},
    {"name": "Inspect", "code": "I", "effective": False,
     "blurb": "checking quality — necessary but non-advancing"},
    {"name": "Release Load", "code": "RL", "effective": True,
     "blurb": "letting go once the operation is done"},
    {"name": "Unavoidable Delay", "code": "UD", "effective": False,
     "blurb": "waiting imposed by the process itself"},
    {"name": "Avoidable Delay", "code": "AD", "effective": False,
     "blurb": "waiting caused by poor arrangement — pure waste"},
    {"name": "Plan", "code": "Pn", "effective": False,
     "blurb": "pausing to decide the next move (rework-signal when large)"},
    {"name": "Rest", "code": "R", "effective": False,
     "blurb": "recovery — legitimate in bodies, suspicious in workflows"},
)

_BY_NAME = {t["name"].lower(): t for t in THERBLIGS}

# Waste elements get elimination suggestions keyed by name.
_WASTE_ADVICE = {
    "Search": "index it, pin it, or shortcut it — searching is layout failure",
    "Find": "reduce the search space so finding is instantaneous",
    "Select": "pre-decide with defaults, templates, or rules",
    "Hold": "put it down — holding is a queue with one slot",
    "Transport Empty": "bring the work to the worker, not the reverse",
    "Inspect": "build the check into the step (poka-yoke), don't bolt it on",
    "Unavoidable Delay": "overlap it with other work; make it visible",
    "Avoidable Delay": "eliminate outright — rearrange the workstation",
    "Plan": "convert repeated planning into a checklist or template",
    "Rest": "in a digital workflow, rest is usually waiting in disguise",
}


def describe(name: str) -> dict:
    """Return the therblig record for ``name`` (case-insensitive)."""
    try:
        return dict(_BY_NAME[name.strip().lower()])
    except KeyError:
        raise ValueError(
            f"unknown therblig {name!r}; valid: {', '.join(t['name'] for t in THERBLIGS)}"
        ) from None


@dataclass
class TaskStep:
    therblig: str
    note: str
    seconds: float

    def __post_init__(self) -> None:
        describe(self.therblig)  # fail-closed on unknown therblig
        if self.seconds < 0:
            raise ValueError("step seconds must be non-negative")
        self.therblig = describe(self.therblig)["name"]


@dataclass
class Analysis:
    total_seconds: float
    shares: list[dict]  # per-therblig: name, seconds, pct, effective
    waste_seconds: float
    waste_pct: float
    recommendations: list[str]

    def summary(self) -> str:
        lines = [
            f"total: {self.total_seconds:.1f}s, "
            f"waste: {self.waste_seconds:.1f}s ({self.waste_pct:.0f}%)"
        ]
        for share in self.shares:
            flag = "" if share["effective"] else "  <-- waste"
            lines.append(
                f"  {share['name']:<18} {share['seconds']:>7.1f}s "
                f"({share['pct']:>4.0f}%){flag}"
            )
        lines.extend("  ! " + r for r in self.recommendations)
        return "\n".join(lines)


class TaskPlan:
    """A workflow decomposed into timed therblig steps."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("plan name must be non-empty")
        self.name = name.strip()
        self.steps: list[TaskStep] = []
        self._store = _persist.store_path(store or f"therbligs-{_slug(self.name)}")
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"therblig store {self._store} does not match plan {self.name!r}"
            )
        for sd in data.get("steps", []):
            self.steps.append(TaskStep(sd["therblig"], sd.get("note", ""),
                                       float(sd.get("seconds", 0))))

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name,
             "steps": [vars(s) for s in self.steps]},
        )

    # -- analysis -----------------------------------------------------------
    def add_step(self, therblig: str, note: str, seconds: float) -> TaskStep:
        step = TaskStep(therblig, note, seconds)
        self.steps.append(step)
        return step

    def analyze(self) -> Analysis:
        if not self.steps:
            raise ValueError("no steps to analyze")
        total = sum(s.seconds for s in self.steps)
        by_name: dict[str, float] = {}
        for s in self.steps:
            by_name[s.therblig] = by_name.get(s.therblig, 0.0) + s.seconds
        shares = []
        waste_seconds = 0.0
        for t in THERBLIGS:
            secs = by_name.get(t["name"], 0.0)
            if secs <= 0:
                continue
            shares.append({
                "name": t["name"],
                "seconds": secs,
                "pct": (100.0 * secs / total) if total else 0.0,
                "effective": t["effective"],
            })
            if not t["effective"]:
                waste_seconds += secs
        shares.sort(key=lambda s: s["seconds"], reverse=True)
        recommendations = []
        for share in shares:
            if not share["effective"] and share["pct"] >= 10.0:
                advice = _WASTE_ADVICE.get(share["name"], "reduce or eliminate")
                recommendations.append(
                    f"{share['name']} is {share['pct']:.0f}% of the workflow: {advice}"
                )
        return Analysis(
            total_seconds=total,
            shares=shares,
            waste_seconds=waste_seconds,
            waste_pct=(100.0 * waste_seconds / total) if total else 0.0,
            recommendations=recommendations,
        )


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower())[:40].strip("-")


__all__ = [
    "THERBLIGS",
    "describe",
    "TaskStep",
    "Analysis",
    "TaskPlan",
]
