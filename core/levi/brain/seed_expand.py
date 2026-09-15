"""
Mass offline corpus expander — combinatorial knowledge generation.

Produces large volumes of distinct principle-units from axis templates
without shipping tens of thousands of hand lines. Unique LEVI design.
Not medical/legal advice.
"""
from __future__ import annotations

from typing import List, Tuple, Iterator
import itertools
import hashlib

# Axes for combinatorial expansion
DOMAINS = [
    "health", "finance", "learning", "relationships", "security", "work",
    "creativity", "systems", "ethics", "communication", "leadership", "ops",
    "parenting", "nutrition", "exercise", "sleep", "attention", "decision",
    "neuroscience", "plasticity", "memory", "emotion", "habit", "product",
    "writing", "design", "career", "community", "privacy", "planning",
]

LENSES = [
    "first_principles", "systems", "opportunity_cost", "reversibility",
    "evidence", "second_order", "margin_of_safety", "feedback",
    "constraint", "habit_design", "ethical_boundary", "local_first",
]

ACTIONS = [
    "define the real goal",
    "shrink the next step to ten minutes",
    "write what would change your mind",
    "check who is harmed if you are wrong",
    "prefer reversible experiments",
    "instrument one metric you will act on",
    "remove one friction from the environment",
    "schedule recovery as infrastructure",
    "separate OBSERVED from HYPOTHESIS",
    "ask what the bottleneck is",
    "document the decision and owner",
    "test the scary assumption cheapest first",
]

NEURO_FOCUS = [
    "hippocampal encoding", "prefrontal control", "amygdala salience",
    "basal ganglia habits", "cerebellar timing", "dopamine prediction error",
    "sleep consolidation", "synaptic LTP/LTD", "myelin timing",
    "attention networks", "interoceptive insula", "default mode rumination",
]

REGION_NOTES = [
    ("hippocampus", "binds relational episodes and supports flexible navigation of space and ideas"),
    ("prefrontal cortex", "maintains goals, inhibits impulses, and supports reappraisal"),
    ("amygdala", "tags emotional significance and speeds threat learning"),
    ("striatum", "updates action values and stabilizes habits with repetition"),
    ("cerebellum", "predicts sensory consequences and refines timing"),
    ("insula", "maps body states that color decisions and urges"),
    ("anterior cingulate", "monitors conflict and motivates control adjustments"),
    ("parietal cortex", "integrates spatial attention and body schema"),
    ("temporal cortex", "supports auditory hierarchies and object meaning"),
    ("occipital cortex", "builds visual features into usable percepts"),
    ("thalamus", "gates and relays signals that attention can prioritize"),
    ("hypothalamus", "defends homeostasis and circadian drives"),
]


def _uid(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode()).hexdigest()[:10]
    return h


def iter_hyperdrive_units(limit: int = 0):
    try:
        from levi.brain.seed_hyperdrive import iter_hyperdrive
        yield from iter_hyperdrive(limit=limit)
    except Exception:
        return

def iter_expanded(limit: int = 25000) -> Iterator[Tuple[str, List[str]]]:
    """Yield unique (text, tags) units up to limit."""
    n = 0
    # Base cross products
    for domain, lens, action in itertools.product(DOMAINS, LENSES, ACTIONS):
        text = (
            f"[{domain}/{lens}] When working on {domain}, apply {lens.replace('_', ' ')}: "
            f"{action}. LEVI offline principle — verify in your context."
        )
        tags = [domain, lens, "expand", "offline_brain", "principle"]
        yield text, tags
        n += 1
        if n >= limit:
            return

    for region, note in REGION_NOTES:
        for lens in LENSES:
            for domain in ("learning", "health", "decision", "emotion", "habit"):
                text = (
                    f"Brain region note — {region}: {note}. "
                    f"In {domain} under a {lens.replace('_', ' ')} lens, respect biology; "
                    f"this is literacy not diagnosis."
                )
                tags = [region.replace(" ", "_"), "neuroscience", domain, lens, "expand"]
                yield text, tags
                n += 1
                if n >= limit:
                    return

    for focus in NEURO_FOCUS:
        for action in ACTIONS:
            text = (
                f"Neuroplasticity framing — {focus}: pair practice with recovery; "
                f"next move: {action}."
            )
            tags = ["neuroplasticity", "expand", focus.split()[0], "learning"]
            yield text, tags
            n += 1
            if n >= limit:
                return

    # Numbered durability tips
    for _i, domain in enumerate(DOMAINS):
        for j in range(1, 40):
            text = (
                f"Durability card {domain}-{j}: protect sleep, reduce open loops, "
                f"and run one reversible experiment in {domain} this week."
            )
            tags = [domain, "durability", "expand", "offline_brain"]
            yield text, tags
            n += 1
            if n >= limit:
                return


def expand_corpus(limit: int = 25000, source: str = "seed_expand") -> str:
    from levi.brain.corpus import Corpus
    c = Corpus()
    n = 0
    # Hyperdrive operational units first (high signal)
    try:
        from levi.brain.seed_hyperdrive import seed as seed_hd
        n += seed_hd()
    except Exception:
        pass
    try:
        from levi.brain.seed_knowledge import seed as seed_k
        n += seed_k()
    except Exception:
        pass
    remaining = max(0, limit - n)
    for text, tags in iter_expanded(limit=remaining):
        c.add(text, kind="INFERENCE", source=source, tags=list(tags))
        n += 1
    return f"Expanded corpus by {n} units (source={source}, cap={limit}, includes hyperdrive)."


def format_expand_info(limit: int = 25000) -> str:
    # theoretical size
    base = len(DOMAINS) * len(LENSES) * len(ACTIONS)
    return (
        f"=== Corpus Mass Expander ===\n"
        f"Combinatorial axes: domains={len(DOMAINS)} lenses={len(LENSES)} actions={len(ACTIONS)}\n"
        f"Base cross-product ≥ {base} principle units (+ neuro region cards)\n"
        f"Default cap: {limit}\n"
        f"Run: python -m levi.cli.main brain --seed-expand\n"
        f"Unique LEVI generator — not a scraped dataset dump.\n"
    )
