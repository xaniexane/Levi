"""Intelligence Fusion Kernel — LEVI-native recreation.

Idea studied: the hybrid-synthetic-intelligence design drop (V2) proposed a
distinct *fusion kernel* that classifies a problem, estimates uncertainty,
selects the cheapest sufficient mix of intelligence paradigms, runs parallel
hypotheses, and verifies before acting.

This is the LEVI-native version: an engineering router, not a sentience
claim. The "intelligence genome" is a routing recipe — numbers are cost and
suitability signals for composition, never measures of machine "intelligence
percentages." Symbolic work stays symbolic (deterministic policy checks,
arithmetic, schemas); neural work stays neural; humans stay in the loop on
anything consequential.

Stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Paradigms LEVI can compose. Each maps to a concrete LEVI surface where it
# exists today (or stays honestly marked as not-yet-built).
PARADIGMS = (
    "generative",  # model-backed drafting / language work
    "symbolic",  # deterministic rules, policy, arithmetic, schemas
    "cognitive",  # goal stacks, working memory, structured plans
    "predictive",  # active-inference style: predict -> act -> observe -> update
    "collective",  # multi-agent decomposition + consensus
    "evolutionary",  # sandboxed variant generation + selection
    "embodied",  # tool/device/environment interaction with feedback
    "human",  # keeper judgment / HITL gate
)

KINDS = (
    "question",  # simple factual or how-to question
    "math",  # arithmetic / deterministic computation
    "research",  # open-ended multi-source investigation
    "dynamic",  # changing environment, needs observe-and-adapt
    "optimization",  # combinatorial search / scheduling / prioritization
    "judgment",  # values, trade-offs, decisions for the keeper
    "build",  # software or artifact construction
)

# Cheapest-sufficient default mixes per problem kind. Weights are routing
# signals in [0, 1]; symbolic is cheap and verifiable, generative is
# expressive but costly, human is the gate for judgment calls.
_DEFAULT_MIXES: Dict[str, Dict[str, float]] = {
    "question": {"generative": 0.8, "symbolic": 0.2, "cognitive": 0.1},
    "math": {"symbolic": 1.0, "generative": 0.1, "cognitive": 0.2},
    "research": {
        "generative": 0.7,
        "collective": 0.6,
        "cognitive": 0.8,
        "symbolic": 0.3,
    },
    "dynamic": {"predictive": 0.9, "embodied": 0.7, "generative": 0.4, "symbolic": 0.3},
    "optimization": {
        "evolutionary": 0.8,
        "collective": 0.5,
        "symbolic": 0.6,
        "generative": 0.2,
    },
    "judgment": {"human": 0.9, "generative": 0.5, "symbolic": 0.4, "cognitive": 0.6},
    "build": {
        "cognitive": 0.9,
        "generative": 0.7,
        "symbolic": 0.7,
        "collective": 0.5,
        "evolutionary": 0.3,
        "human": 0.5,
    },
}

_MATH_HINTS = (
    "compute",
    "calculate",
    "sum",
    "total",
    "average",
    "%",
    "how much",
    "equation",
    "formula",
    "budget",
)
_RESEARCH_HINTS = (
    "research",
    "compare",
    "survey",
    "landscape",
    "what are the",
    "options for",
    "investigate",
)
_DYNAMIC_HINTS = (
    "monitor",
    "watch",
    "track",
    "changing",
    "live",
    "stream",
    "adapt",
    "ongoing",
)
_OPTIMIZE_HINTS = (
    "optimize",
    "schedule",
    "prioritize",
    "best combination",
    "plan",
    "route",
    "minimize",
    "maximize",
)
_JUDGMENT_HINTS = (
    "should i",
    "decide",
    "worth it",
    "trade-off",
    "tradeoff",
    "recommend",
    "choose between",
)
_BUILD_HINTS = (
    "build",
    "write code",
    "implement",
    "create",
    "script",
    "automate",
    "refactor",
)


@dataclass
class IntelligenceGenome:
    """A routing recipe for one task. Weights are composition signals."""

    task: str
    kind: str
    uncertainty: str  # low | medium | high
    mix: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    risk: str = "low"  # low | medium | high

    def dominant(self) -> List[str]:
        """Paradigms carrying the mix, strongest first."""
        return sorted(
            (p for p, w in self.mix.items() if w >= 0.5),
            key=lambda p: self.mix[p],
            reverse=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "kind": self.kind,
            "uncertainty": self.uncertainty,
            "intelligence_mix": dict(self.mix),
            "constraints": dict(self.constraints),
            "risk": self.risk,
        }


def classify(problem: str) -> str:
    """Classify a problem into one of KINDS. Heuristic, honest about it."""
    text = (problem or "").lower()
    checks: List[Tuple[str, Tuple[str, ...]]] = [
        ("math", _MATH_HINTS),
        ("build", _BUILD_HINTS),
        ("research", _RESEARCH_HINTS),
        ("optimization", _OPTIMIZE_HINTS),
        ("dynamic", _DYNAMIC_HINTS),
        ("judgment", _JUDGMENT_HINTS),
    ]
    for kind, hints in checks:
        if any(h in text for h in hints):
            return kind
    return "question"


def estimate_uncertainty(problem: str, kind: str) -> str:
    """Rough uncertainty estimate: unknowns, stakes, vagueness."""
    text = (problem or "").lower()
    high_markers = (
        "unknown",
        "unclear",
        "not sure",
        "might",
        "maybe",
        "risky",
        "never done",
        "first time",
        "complex",
    )
    hits = sum(1 for m in high_markers if m in text)
    if kind in ("research", "dynamic", "judgment") or hits >= 2:
        return "high"
    if kind in ("optimization", "build") or hits == 1:
        return "medium"
    return "low"


def select_mix(
    kind: str, uncertainty: str = "low", capabilities: Optional[Dict[str, bool]] = None
) -> Dict[str, float]:
    """Return the cheapest-sufficient paradigm mix for a kind.

    ``capabilities`` maps paradigm -> available; unavailable paradigms are
    dropped and their weight redistributed to the closest available sibling
    (generative <-> collective, symbolic <-> cognitive, predictive <->
    embodied). Human is never dropped — it degrades to an explicit note.
    """
    base = dict(_DEFAULT_MIXES.get(kind, _DEFAULT_MIXES["question"]))
    if uncertainty == "high":
        base["cognitive"] = min(1.0, base.get("cognitive", 0) + 0.2)
        base["symbolic"] = min(1.0, base.get("symbolic", 0) + 0.1)
    if not capabilities:
        return base
    available = {p for p, ok in capabilities.items() if ok}
    siblings = {
        "generative": "collective",
        "collective": "generative",
        "symbolic": "cognitive",
        "cognitive": "symbolic",
        "predictive": "embodied",
        "embodied": "predictive",
        "evolutionary": "symbolic",
    }
    out: Dict[str, float] = {}
    for p, w in base.items():
        if p in available:
            out[p] = w
            continue
        sib = siblings.get(p)
        if sib and sib in available and sib in out:
            out[sib] = min(1.0, out[sib] + w * 0.5)
        elif sib and sib in available:
            out[sib] = w * 0.5
        # else: paradigm genuinely unavailable — dropped, honestly.
    return out


def assess_risk(kind: str, uncertainty: str) -> str:
    if kind == "judgment" or uncertainty == "high":
        return "high"
    if kind in ("build", "optimization", "dynamic") or uncertainty == "medium":
        return "medium"
    return "low"


class FusionKernel:
    """Compose a governed plan for one task: classify, estimate, select,
    verify. The kernel never executes tools itself — it produces the recipe
    that a governed loop (Plan->Preview->Permission->Execute->Verify->
    Receipt) can run."""

    def __init__(self, capabilities: Optional[Dict[str, bool]] = None):
        self.capabilities = capabilities or {p: True for p in PARADIGMS}

    def compose(
        self, task: str, constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        kind = classify(task)
        uncertainty = estimate_uncertainty(task, kind)
        mix = select_mix(kind, uncertainty, self.capabilities)
        genome = IntelligenceGenome(
            task=task,
            kind=kind,
            uncertainty=uncertainty,
            mix=mix,
            constraints=dict(constraints or {}),
            risk=assess_risk(kind, uncertainty),
        )
        plan = {
            "genome": genome.to_dict(),
            "loop": [
                "perceive",
                "classify",
                "estimate_uncertainty",
                "select_intelligence_mix",
                "generate_hypotheses",
                "verify_symbolically",
                "policy_gate",
                "act_or_ask",
                "observe",
                "measure",
                "consolidate",
            ],
            "verification": (
                "symbolic checks first; generative output cross-checked; "
                "human gate when risk is high"
            ),
            "human_gate_required": genome.risk == "high",
        }
        return plan

    def explain(self, task: str) -> str:
        """One-paragraph plain-language account of the chosen composition."""
        plan = self.compose(task)
        g = plan["genome"]
        dom = ", ".join(
            f"{p} ({w:.1f})"
            for p, w in sorted(
                g["intelligence_mix"].items(), key=lambda kv: kv[1], reverse=True
            )[:3]
        )
        gate = (
            "keeper approval required"
            if plan["human_gate_required"]
            else "no keeper gate"
        )
        return (
            f"Task classified as '{g['kind']}' with {g['uncertainty']} uncertainty "
            f"and {g['risk']} risk. Composition leans on {dom}. {gate.capitalize()}."
        )


def compose(
    task: str,
    capabilities: Optional[Dict[str, bool]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Module-level convenience wrapper."""
    return FusionKernel(capabilities=capabilities).compose(
        task, constraints=constraints
    )
