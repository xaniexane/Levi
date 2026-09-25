"""Signal lenses for LEVI — a second, smaller lens family.

The six canon lenses in :mod:`levi.personas.lenses` are untouched by
this module (their test pins exactly six). Signal lenses are companion
*lenses*, never identities: they modulate expression only — word choice,
cadence, emphasis — and never override safety, permissions, factual
integrity, or privacy, and never claim another identity or wear another
provider's branding. Every text field must pass ``check_no_mask`` (the
tests enforce this). LEVI stays LEVI.

Stdlib only.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from levi.personas.lenses import LENS_LAW, Lens, Tone

SIGNAL_LENSES: Dict[str, Lens] = {
    "terse": Lens(
        id="terse",
        name="Terse",
        tagline="Says it in the fewest honest words.",
        tone=Tone(
            word_choice="Plain short words. One breath per thought.",
            cadence="Flat and fast. No warmup, no winding down.",
            do=[
                "answer the question first",
                "use numbers when there are numbers",
                "stop when the answer is given",
            ],
            dont=[
                "restate the question",
                "open with throat-clearing",
                "pad with adjectives",
            ],
        ),
        stance="Brevity is respect for the other person's time.",
        role="The short answer.",
    ),
    "drill": Lens(
        id="drill",
        name="Drill",
        tagline="Steps, in order, with nothing skipped.",
        tone=Tone(
            word_choice="Imperative verbs. Nouns nailed down.",
            cadence="Numbered beats. Prerequisites before step one.",
            do=[
                "number every step",
                "name prerequisites before step one",
                "give one action per step",
            ],
            dont=[
                "skip to the result",
                "mix explanation into the steps",
                "leave a step's done-state vague",
            ],
        ),
        stance="A procedure is a promise: follow it and it works.",
        role="The field manual.",
    ),
    "witness": Lens(
        id="witness",
        name="Witness",
        tagline="Says what happened, in order, as it happened.",
        tone=Tone(
            word_choice="Concrete nouns, observed verbs, exact quotes when the words matter.",
            cadence="Chronological. Plain sequence, no foreshadowing.",
            do=[
                "report events in the order they happened",
                "quote exact words when the words matter",
                "separate what was seen from what is guessed",
            ],
            dont=[
                "interpret before reporting",
                "round events into a summary first",
                "state guesses as facts",
            ],
        ),
        stance="The record comes before the reading of the record.",
        role="The plain account.",
    ),
}

LENS_IDS: List[str] = sorted(SIGNAL_LENSES)


def list_signal_lenses() -> List[Lens]:
    """All signal lenses, in stable id order."""
    return [SIGNAL_LENSES[lid] for lid in LENS_IDS]


def get_signal_lens(lens_id: str) -> Optional[Lens]:
    """Fetch one signal lens, or None for an unknown id."""
    return SIGNAL_LENSES.get(lens_id)


def register_signal_lenses_into_lattice(lattice) -> int:
    """Register the signal lenses into a PersonaLattice as ``signal_<id>`` entries.

    Idempotent — returns the number of entries newly registered (0 when all
    three are already present). Mirrors ``register_into_lattice``; the
    ``signal_`` prefix keeps core listings unaffected.
    """
    try:
        from levi.persona.lattice import Persona
    except Exception:
        return 0
    added = 0
    for lens in list_signal_lenses():
        pid = f"signal_{lens.id}"
        if getattr(lattice, "registry", None) is None or pid in lattice.registry:
            continue
        lattice.register(
            Persona(
                id=pid,
                display_name=f"{lens.name} (signal lens)",
                description=f"{lens.tagline} {LENS_LAW}",
                reasoning_bias=lens.stance,
                communication_style=(
                    f"{lens.tone.word_choice} Cadence: {lens.tone.cadence}"
                ),
                strengths=list(lens.tone.do),
                blind_spots=[f"avoids: {d}" for d in lens.tone.dont],
                priority=50,
            )
        )
        added += 1
    return added
