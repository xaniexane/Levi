"""metaphor — legibility through metaphor discipline.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 20).

Load-bearing idea: unfamiliar capabilities become legible when described
through a familiar metaphor's vocabulary — the metaphor's verbs and nouns
(channel, tune, monitor, squelch) are mapped onto the new medium, and the
mapping is *disciplined*: every target concept gets exactly one metaphor
term, and the metaphor never leaks invented capabilities.

LEVI's take: a ``Metaphor`` is a named source domain with a strict
vocabulary map (metaphor term -> target concept) plus a renderer that
talks about target capabilities *only* in the metaphor's words. This
module ships one worked mapping — tuning "channels" over LEVI's own
capability list — and ``define_metaphor`` as the template for new ones.
A legibility tool, LEVI-voiced: it explains what LEVI can do without
asking anyone to learn new jargon first.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/metaphor"


class MetaphorError(Exception):
    """The metaphor discipline was broken."""


# ---------------------------------------------------------------------------
# LEVI's own capability list — the target domain for the worked mapping.
# ---------------------------------------------------------------------------

LEVI_CAPABILITIES: Dict[str, str] = {
    "harvest": "gather experiences from sessions, runs, and logs",
    "reflect": "distill experiences into candidate learnings",
    "consolidate": "fold learnings into durable memory with provenance",
    "journal": "append growth milestones to the baby book",
    "ask": "answer a question from memory and corpus",
    "search": "find things across the local corpus",
    "plan": "break a goal into ordered steps",
    "remember": "store a fact, preference, or correction",
    "forget": "remove a memory on parental instruction",
    "schedule": "set work to run on a clock or an event",
}


# ---------------------------------------------------------------------------
# Metaphor
# ---------------------------------------------------------------------------


@dataclass
class Metaphor:
    """A disciplined source-domain vocabulary mapped onto target concepts.

    ``vocabulary``: metaphor term -> (target concept, gloss in the
    metaphor's own words). Discipline: a term maps to exactly one
    concept; unmapped target concepts are reported, never invented.
    """

    name: str
    source_domain: str
    vocabulary: Dict[str, str]  # metaphor term -> target concept key
    glosses: Dict[str, str] = field(
        default_factory=dict
    )  # term -> metaphor-voiced gloss

    def __post_init__(self) -> None:
        targets = list(self.vocabulary.values())
        dupes = {t for t in targets if targets.count(t) > 1}
        if dupes:
            raise MetaphorError(
                f"terms must map 1:1; concepts mapped twice: {sorted(dupes)}"
            )

    def covers(self, concept: str) -> Optional[str]:
        """The metaphor term for a target concept, if the mapping has one."""
        for term, target in self.vocabulary.items():
            if target == concept:
                return term
        return None

    def uncovered(self, concepts: List[str]) -> List[str]:
        """Target concepts with no metaphor term — honest gaps, not inventions."""
        return [c for c in concepts if self.covers(c) is None]

    def speak(self, concept: str) -> str:
        """Describe a target concept purely in the metaphor's vocabulary."""
        term = self.covers(concept)
        if term is None:
            raise MetaphorError(
                f"{concept!r} has no term in the {self.name!r} metaphor"
            )
        gloss = self.glosses.get(term, "")
        return f"{term} — {gloss}" if gloss else term


def define_metaphor(
    name: str,
    source_domain: str,
    vocabulary: Dict[str, str],
    glosses: Optional[Dict[str, str]] = None,
) -> Metaphor:
    """Template for defining a new metaphor. Vocabulary maps 1:1 or it raises."""
    return Metaphor(
        name=name,
        source_domain=source_domain,
        vocabulary=dict(vocabulary),
        glosses=dict(glosses or {}),
    )


# ---------------------------------------------------------------------------
# Worked mapping: tuning "channels" over LEVI's own capability list.
# ---------------------------------------------------------------------------


def channels_metaphor() -> Metaphor:
    """The shipped worked example: LEVI's capabilities as radio channels.

    Tune to a channel to work a capability; monitor to watch its output;
    squelch to silence one; mind the signal strength before you trust it.
    """
    return define_metaphor(
        name="channels",
        source_domain="citizens-band radio: channels you tune, monitor, and squelch",
        vocabulary={
            "tune": "plan",  # tune to the planning channel
            "monitor": "journal",  # monitor the growth channel
            "squelch": "forget",  # squelch a noisy memory
            "channel 1": "ask",
            "channel 2": "search",
            "channel 3": "reflect",
            "channel 4": "consolidate",
            "channel 5": "harvest",
            "channel 6": "remember",
            "channel 7": "schedule",
        },
        glosses={
            "tune": "dial the set to the planning channel and work it",
            "monitor": "keep the receiver open on the growth log; don't transmit",
            "squelch": "cut the noise — drop the memory at the owner's word",
            "channel 1": "the question channel: ask, and the set answers",
            "channel 2": "the search channel: sweep the local corpus",
            "channel 3": "the reflection channel: distill the day's traffic",
            "channel 4": "the consolidation channel: file learnings with provenance",
            "channel 5": "the harvest channel: pull experiences off the air",
            "channel 6": "the memory channel: store a fact for later",
            "channel 7": "the schedule channel: set the set to wake on time",
        },
    )


def explain(
    metaphor: Metaphor, capabilities: Optional[Dict[str, str]] = None
) -> List[str]:
    """Render each capability in the metaphor's voice; name the gaps.

    Returns one line per capability, all in metaphor vocabulary, plus a
    final honest line for any capability the metaphor doesn't cover.
    """
    caps = capabilities if capabilities is not None else LEVI_CAPABILITIES
    lines = []
    for concept, plain in caps.items():
        term = metaphor.covers(concept)
        if term is not None:
            lines.append(f"{metaphor.speak(concept)}  ({plain})")
        else:
            lines.append(f"[no {metaphor.name} term] {concept}: {plain}")
    return lines


METAPHOR_TEMPLATE = """\
# New metaphor template
#
# 1. Pick a source domain everyone already feels in their hands
#    (radio, kitchen, garden, workshop...).
# 2. List its verbs/nouns — the ONLY words your mapping may use.
# 3. Map each term to exactly one target concept (1:1, enforced).
# 4. Write each gloss in the metaphor's voice, never the target's jargon.
# 5. Ship `uncovered()` gaps openly — the metaphor must not invent.

from levi.revival.metaphor import define_metaphor, explain, LEVI_CAPABILITIES

garden = define_metaphor(
    name="garden",
    source_domain="a kitchen garden: sow, water, weed, harvest",
    vocabulary={
        "sow": "remember",
        "water": "reflect",
        "weed": "forget",
        "harvest": "harvest",
    },
    glosses={
        "sow": "press a fact into the soil for later",
        "water": "turn the day's growth over in the light",
        "weed": "pull what the owner says doesn't belong",
        "harvest": "gather what's ripe from the rows",
    },
)

for line in explain(garden):
    print(line)
"""
