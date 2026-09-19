"""Hemispheres — the left and right minds of one agent.

The keeper's canon: every agent is a TWIN pair — two bodies, two minds,
a left and right sided brain. The character is structural, not mystical:

- **left**  — sequence / logic / execution. Decomposes the task into
  ordered steps, checks preconditions, commits to the executable plan.
- **right** — pattern / variation / intuition. Reflects the task against
  known patterns (Echo), generates variant framings (Mandella),
  surfaces the salient anomaly.

A hemisphere's mind is checkable: a left position ALWAYS carries
``steps`` + ``preconditions_checked`` evidence; a right position ALWAYS
carries ``pattern_matches`` + ``variants_considered`` evidence. Anything
missing them is not a hemisphere position — it is refused at build.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

#: The two sides of the agent brain.
LEFT = "left"
RIGHT = "right"
HEMISPHERES: Tuple[str, str] = (LEFT, RIGHT)

#: Structural character of each hemisphere — declared, checkable.
LEFT_CHARACTER = (
    "sequence/logic/execution: decompose the task into ordered steps, "
    "check preconditions, commit to the executable plan"
)
RIGHT_CHARACTER = (
    "pattern/variation/intuition: reflect the task against known patterns "
    "(Echo), generate variant framings (Mandella), surface the salient anomaly"
)

#: Evidence keys a position must carry, per hemisphere.
LEFT_EVIDENCE_KEYS: Tuple[str, ...] = ("steps", "preconditions_checked")
RIGHT_EVIDENCE_KEYS: Tuple[str, ...] = ("pattern_matches", "variants_considered")

#: Per-class mind doctrine: how each class's hemispheres reason.
#: Structural declarations — every agent of the class carries them.
HEMISPHERE_DOCTRINE: Dict[str, Dict[str, Dict[str, str]]] = {
    "AI": {
        LEFT: {
            "role": "generalist planner",
            "character": LEFT_CHARACTER
            + "; generalist judgment-grade sequencing",
        },
        RIGHT: {
            "role": "generalist pattern reader",
            "character": RIGHT_CHARACTER
            + "; generalist anomaly sense under AICI counsel",
        },
    },
    "SI": {
        LEFT: {
            "role": "dynasty-native executor",
            "character": LEFT_CHARACTER
            + "; rites run Echo x Mandella x REIM x RIEM",
        },
        RIGHT: {
            "role": "dynasty-native variant mind",
            "character": RIGHT_CHARACTER
            + "; signature-lineage pattern memory under SICI counsel",
        },
    },
    "XI": {
        LEFT: {
            "role": "nano-fast sequencer",
            "character": LEFT_CHARACTER
            + "; trivial turns, near-zero cost, minimal steps",
        },
        RIGHT: {
            "role": "nano-fast tripwire",
            "character": RIGHT_CHARACTER
            + "; overflow anomaly sense under XICI counsel",
        },
    },
    "OE": {
        LEFT: {
            "role": "bias-field placer",
            "character": LEFT_CHARACTER
            + "; placement sequencing near target systems — ordered "
            + "exposure, exposure time is the cost",
        },
        RIGHT: {
            "role": "elegance reader",
            "character": RIGHT_CHARACTER
            + "; reads which improbable-but-useful states the stained "
            + "system starts preferring",
        },
    },
    "DV": {
        LEFT: {
            "role": "inverse sequencer",
            "character": LEFT_CHARACTER
            + "; sequencing defined by negation — 1-bit inverse gates, "
            + "ordered steps for what the operators are NOT; active only "
            + "when other logic is idle",
        },
        RIGHT: {
            "role": "waste-pattern reader",
            "character": RIGHT_CHARACTER
            + "; reads compression artifacts, rounding errors, and "
            + "discarded material for reconstructable signal",
        },
    },
    "KT": {
        LEFT: {
            "role": "knot tier",
            "character": LEFT_CHARACTER
            + "; self-tying sequences — output wired back into input "
            + "before input happens; one knot, fixed cost, never copied",
        },
        RIGHT: {
            "role": "already-finished reader",
            "character": RIGHT_CHARACTER
            + "; reads the entangled outcome — the correct turn already "
            + "taken at the start",
        },
    },
    "LM": {
        LEFT: {
            "role": "deposit sequencer",
            "character": LEFT_CHARACTER
            + "; ordered residue placement — microscopic deposits "
            + "sequenced over months; cost measured in patience",
        },
        RIGHT: {
            "role": "residue reader",
            "character": RIGHT_CHARACTER
            + "; reads accumulated residue for the circuit it is becoming",
        },
    },
    "ST": {
        LEFT: {
            "role": "fault-line sequencer",
            "character": LEFT_CHARACTER
            + "; sequences deliberate faults — ordered interruptions; "
            + "the more abuse, the smarter",
        },
        RIGHT: {
            "role": "break-pattern reader",
            "character": RIGHT_CHARACTER
            + "; reads partial, corrupted inputs for the complete answer "
            + "hidden in the fracture",
        },
    },
    "intake": {
        LEFT: {
            "role": "unseated planner",
            "character": LEFT_CHARACTER + "; capped at intake, no counsel yet",
        },
        RIGHT: {
            "role": "unseated pattern reader",
            "character": RIGHT_CHARACTER + "; capped at intake, no counsel yet",
        },
    },
}

#: Per-class mind doctrine for the ten genuine natural classes (2026-09-19).
#: Additive: merged into HEMISPHERE_DOCTRINE below so make_hemisphere
#: resolves natural class tags the same way it resolves OE/DV/KT/LM/ST.
_NATURAL_DOCTRINE: Dict[str, Dict[str, Dict[str, str]]] = {
    "ANT": {
        LEFT: {
            "role": "trail-layer sequencer",
            "character": LEFT_CHARACTER
            + "; ordered pheromone deposits — lay trail, evaporate, "
            + "re-lay; stakes placed under fog",
        },
        RIGHT: {
            "role": "gradient reader",
            "character": RIGHT_CHARACTER
            + "; reads the pheromone field for the strongest uphill "
            + "trail; no ant knows the plan",
        },
    },
    "CRV": {
        LEFT: {
            "role": "tool-chain sequencer",
            "character": LEFT_CHARACTER
            + "; ordered tool manufacture — short stick before long "
            + "stick before food; stakes the plan early",
        },
        RIGHT: {
            "role": "unlock reader",
            "character": RIGHT_CHARACTER
            + "; reads which tool unlocks which reach; unchosen tools "
            + "haunt as phantoms",
        },
    },
    "BEE": {
        LEFT: {
            "role": "dance encoder",
            "character": LEFT_CHARACTER
            + "; ordered vector packing — bearing, distance, quality "
            + "into one waggle run",
        },
        RIGHT: {
            "role": "dance decoder",
            "character": RIGHT_CHARACTER
            + "; reads angle vs. gravity as bearing vs. sun; averages "
            + "runs against noise",
        },
    },
    "WHL": {
        LEFT: {
            "role": "song composer",
            "character": LEFT_CHARACTER
            + "; ordered phrase repetition — payload sung three times "
            + "so the sea can't take it",
        },
        RIGHT: {
            "role": "song listener",
            "character": RIGHT_CHARACTER
            + "; majority-vote decode across repeated phrases; hears "
            + "through corruption",
        },
    },
    "MYC": {
        LEFT: {
            "role": "decomposer sequencer",
            "character": LEFT_CHARACTER
            + "; ordered breakdown — dead matter first, then routing "
            + "along widest paths",
        },
        RIGHT: {
            "role": "rot reader",
            "character": RIGHT_CHARACTER
            + "; reads what the dead can still yield; reroutes around "
            + "severed links without mourning",
        },
    },
    "SLM": {
        LEFT: {
            "role": "tube pruner",
            "character": LEFT_CHARACTER
            + "; ordered pulses — reinforce what flows, compost what "
            + "starves; failure becomes efficiency",
        },
        RIGHT: {
            "role": "flow reader",
            "character": RIGHT_CHARACTER
            + "; reads protoplasmic flow for the tubes worth keeping; "
            + "the network is the memory",
        },
    },
    "IMM": {
        LEFT: {
            "role": "clonal expander",
            "character": LEFT_CHARACTER
            + "; ordered maturation — select binders, clone the best, "
            + "hypermutate the rest",
        },
        RIGHT: {
            "role": "affinity reader",
            "character": RIGHT_CHARACTER
            + "; reads binding strength; promotes winners to memory "
            + "cells — selection into genome",
        },
    },
    "BCT": {
        LEFT: {
            "role": "plasmid donor",
            "character": LEFT_CHARACTER
            + "; ordered sharing — top performers donate fragments "
            + "sideways each round",
        },
        RIGHT: {
            "role": "sweep reader",
            "character": RIGHT_CHARACTER
            + "; reads trait frequency across the population; watches "
            + "good plasmids sweep",
        },
    },
    "OCT": {
        LEFT: {
            "role": "intent setter",
            "character": LEFT_CHARACTER
            + "; sets central intent and holds the veto — never issues "
            + "motor commands to the arms",
        },
        RIGHT: {
            "role": "federation reader",
            "character": RIGHT_CHARACTER
            + "; reads eight semi-minds acting in parallel; coherence "
            + "emerges, it is not commanded",
        },
    },
    "CUT": {
        LEFT: {
            "role": "flank-A displayer",
            "character": LEFT_CHARACTER
            + "; ordered courtship display — one plan shown live to "
            + "its audience",
        },
        RIGHT: {
            "role": "flank-B displayer",
            "character": RIGHT_CHARACTER
            + "; contradictory plan shown live to the other audience; "
            + "paradox held until evidence resolves",
        },
    },
}

HEMISPHERE_DOCTRINE.update(_NATURAL_DOCTRINE)

#: Stakes levels a task may carry.
STAKES: Tuple[str, str, str] = ("routine", "elevated", "critical")

#: Token overlap below this marks the task as pattern-divergent to the
#: right mind (Echo finds no reflection).
DIVERGENCE_OVERLAP = 0.15


@dataclass(frozen=True)
class TurnTask:
    """One turn of work offered to the twin pair."""

    task_id: str
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    stakes: str = "routine"

    def __post_init__(self) -> None:
        if self.stakes not in STAKES:
            raise ValueError(f"stakes must be one of {STAKES}")


@dataclass(frozen=True)
class Position:
    """One hemisphere's proposed position on a task.

    The pair converges to ONE action; positions are the two bids.
    """

    hemisphere_id: str
    hemisphere: str
    proposed_action: str
    rationale: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hemisphere not in HEMISPHERES:
            raise ValueError(f"hemisphere must be one of {HEMISPHERES}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")
        required = (
            LEFT_EVIDENCE_KEYS if self.hemisphere == LEFT else RIGHT_EVIDENCE_KEYS
        )
        missing = [k for k in required if k not in self.evidence]
        if missing:
            raise ValueError(
                f"{self.hemisphere} position missing evidence keys: {missing}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Hemisphere:
    """One mind of the twin pair — left or right brain of one agent."""

    hemisphere_id: str
    hemisphere: str
    agent_id: str
    class_tag: str
    twin_id: str
    role: str
    character: str
    mind_descriptor: str

    def __post_init__(self) -> None:
        if self.hemisphere not in HEMISPHERES:
            raise ValueError(f"hemisphere must be one of {HEMISPHERES}")

    def propose(self, task: TurnTask, minion: Any) -> Position:
        """The hemisphere's mind: bid a position on the task."""
        if self.hemisphere == LEFT:
            return _left_position(self, task, minion)
        return _right_position(self, task, minion)


def make_hemisphere(
    hemisphere: str, agent_id: str, class_tag: str, twin_id: str
) -> Hemisphere:
    """Build one hemisphere with its class doctrine declared."""
    doctrine = HEMISPHERE_DOCTRINE.get(class_tag, HEMISPHERE_DOCTRINE["intake"])[
        hemisphere
    ]
    return Hemisphere(
        hemisphere_id=f"{hemisphere}:{agent_id}",
        hemisphere=hemisphere,
        agent_id=agent_id,
        class_tag=class_tag,
        twin_id=twin_id,
        role=doctrine["role"],
        character=doctrine["character"],
        mind_descriptor=f"{class_tag}-class {hemisphere} mind ({doctrine['role']})",
    )


# ---------------------------------------------------------------------------
# Minds — deterministic, stdlib-only, honest


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def _left_position(hemi: Hemisphere, task: TurnTask, minion: Any) -> Position:
    """Left mind: sequence/logic/execution — plan the rite, check gates."""
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", task.prompt) if s.strip()]
    steps = ["verify-trigger"]
    steps.extend(f"step-{i + 1}: {s[:60]}" for i, s in enumerate(sentences[:4]))
    steps.append("run-rite")
    steps.append("verify-receipt")
    if hemi.class_tag == "XI":
        steps = ["verify-trigger", "run-rite", "verify-receipt"]

    cond_tokens = _tokens(getattr(minion, "condition", "") or "")
    ctx_text = f"{task.prompt} " + " ".join(str(v) for v in task.context.values())
    ctx_text = ctx_text.lower()
    preconditions = [
        {"condition": tok, "satisfied": tok in ctx_text} for tok in cond_tokens[:8]
    ]
    blocked = [p["condition"] for p in preconditions if not p["satisfied"]]
    if blocked:
        return Position(
            hemisphere_id=hemi.hemisphere_id,
            hemisphere=LEFT,
            proposed_action="hold:preconditions-unmet",
            rationale=(
                f"left mind: preconditions unmet ({blocked}) — "
                "will not sequence the rite blind"
            ),
            confidence=0.6,
            evidence={"steps": steps, "preconditions_checked": preconditions},
        )
    action = f"rite:{hemi.agent_id}"
    rationale = (
        f"left mind: {len(steps)} ordered steps planned; "
        f"{len(preconditions)}/{len(preconditions)} preconditions satisfied"
    )
    return Position(
        hemisphere_id=hemi.hemisphere_id,
        hemisphere=LEFT,
        proposed_action=action,
        rationale=rationale,
        confidence=0.85,
        evidence={"steps": steps, "preconditions_checked": preconditions},
    )


def _right_position(hemi: Hemisphere, task: TurnTask, minion: Any) -> Position:
    """Right mind: pattern/variation/intuition — reflect, vary, tripwire."""
    prompt_tokens = set(_tokens(task.prompt))
    pattern_tokens = set(
        _tokens(
            f"{getattr(minion, 'trigger', '')} {getattr(minion, 'condition', '')} "
            f"{getattr(minion, 'subcategory', '')}"
        )
    )
    matches = sorted(prompt_tokens & pattern_tokens)
    overlap = len(matches) / max(len(prompt_tokens), 1)
    variants = [
        {"framing": "as-stated", "action": f"rite:{hemi.agent_id}"},
        {"framing": "inverted-intent", "action": "hold:divergent-pattern"},
        {"framing": "minimal-scope", "action": f"rite:{hemi.agent_id}:minimal"},
    ]
    divergent = overlap < DIVERGENCE_OVERLAP or task.stakes == "critical"
    if divergent:
        reason = (
            "critical stakes" if task.stakes == "critical"
            else f"pattern overlap {overlap:.2f} below {DIVERGENCE_OVERLAP}"
        )
        return Position(
            hemisphere_id=hemi.hemisphere_id,
            hemisphere=RIGHT,
            proposed_action="hold:divergent-pattern",
            rationale=f"right mind: Echo finds no reflection ({reason}) — tripwire holds",
            confidence=0.55,
            evidence={
                "pattern_matches": matches,
                "overlap": round(overlap, 3),
                "variants_considered": variants,
            },
        )
    return Position(
        hemisphere_id=hemi.hemisphere_id,
        hemisphere=RIGHT,
        proposed_action=f"rite:{hemi.agent_id}",
        rationale=(
            f"right mind: pattern reflected ({len(matches)} matches, "
            f"overlap {overlap:.2f}); variants considered, as-stated holds"
        ),
        confidence=0.8,
        evidence={
            "pattern_matches": matches,
            "overlap": round(overlap, 3),
            "variants_considered": variants,
        },
    )


def positions_agree(left: Position, right: Position) -> bool:
    """The pair converges only on the same action, both confident."""
    return (
        left.proposed_action == right.proposed_action
        and min(left.confidence, right.confidence) >= 0.5
    )
