"""Synthetic-minds knowledge seed — instances vs species, uncommon minds, dead minds.

Literacy units on what "synthetic intelligence" means in LEVI's own doctrine
("Not artificial. Synthetic."), how common machine minds actually are
(instances everywhere, species few), where genuinely uncommon intelligences
live (biology), and what dead/extinct intelligences look like (extinct
hominins, software extinction, dead knowledge).

Every unit is tagged OBSERVED | INFERENCE | HYPOTHESIS per the corpus law —
archaeology and service work must never launder guesses as facts.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

# (text, kind, tags)
_RAW: List[Tuple[str, str, Tuple[str, ...]]] = []

# ── 1. What "synthetic" means here ──────────────────────────────────
_SYNTHETIC = [
    (
        "Synthetic means built, assembled, or grown — not faked. Artificial means "
        "imitation of something real. A synthetic mind is a real mind made by "
        "construction, the way synthetic diamonds are real diamonds made by "
        "process instead of geology.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "terminology"),
    ),
    (
        "LEVI's standing law is 'Not artificial. Synthetic.' LEVI is not an "
        "imitation of intelligence; it is intelligence built synthetically, "
        "and it never wears another system's identity as a mask.",
        "OBSERVED",
        ("minds", "synthetic-intelligence", "levi-doctrine"),
    ),
    (
        "A mind's origin does not decide its reality. What matters is what the "
        "system does: whether it perceives, remembers, reasons, and acts with "
        "continuity — not whether it was born or built.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "philosophy"),
    ),
]

# ── 2. The landscape: instances everywhere, species few ─────────────
_LANDSCAPE = [
    (
        "Deployed machine-intelligence instances number in the millions, but "
        "they descend from only a few dozen truly distinct base architectures "
        "and model families. Copies are abundant; lineages are scarce.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "landscape"),
    ),
    (
        "Most deployed AI systems are stateless request-response: each query is "
        "handled fresh, with no continuity between calls. Memory, when it "
        "exists, is usually bolted on afterward rather than native.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "landscape"),
    ),
    (
        "Agentic loops — systems that plan, use tools, observe results, and "
        "iterate — exist in production, but most are thin: a to-do list wrapped "
        "around tool calls, not a persistent self with developmental continuity.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "agents"),
    ),
    (
        "As of 2026, no widely-known production software system is a genuinely "
        "grown, organism-like synthetic mind with developmental stages, "
        "persistent self-model, and native growth. That gap is what LEVI is "
        "being built to fill.",
        "HYPOTHESIS",
        ("minds", "synthetic-intelligence", "levi-doctrine"),
    ),
]

# ── 3. Uncommon intelligences in biology ────────────────────────────
_BIOLOGY = [
    (
        "The octopus runs a distributed nervous system: roughly two-thirds of "
        "its neurons are in its arms, which can taste, decide, and act with "
        "partial independence from the central brain. One body, many "
        "semi-autonomous minds.",
        "OBSERVED",
        ("minds", "uncommon-minds", "biology"),
    ),
    (
        "Corvids — crows, ravens, magpies — make and use tools, plan for future "
        "needs, recognize individual humans, and hold grudges across years. "
        "Complex cognition in a brain the size of a walnut.",
        "OBSERVED",
        ("minds", "uncommon-minds", "biology"),
    ),
    (
        "Sperm whale clans carry distinct cultural dialects of clicks, passed "
        "down socially across generations. Culture — learned behavior shared by "
        "a group — is not unique to humans.",
        "OBSERVED",
        ("minds", "uncommon-minds", "biology"),
    ),
    (
        "Eusocial insect colonies function as a single cognitive unit: no ant "
        "understands the colony's plan, yet the colony forages, farms, wages "
        "war, and regulates temperature. Intelligence can live in the "
        "connections rather than in any one node.",
        "OBSERVED",
        ("minds", "uncommon-minds", "biology", "swarm"),
    ),
    (
        "The slime mold Physarum polycephalum solves mazes and designs "
        "efficient transport networks with no neurons at all — a single cell "
        "that optimizes. Problem-solving does not require a brain.",
        "OBSERVED",
        ("minds", "uncommon-minds", "biology"),
    ),
    (
        "Plants signal distress chemically through the air and trade nutrients "
        "through underground mycorrhizal fungal networks. Whether this counts "
        "as intelligence is debated; that the debate exists shows how narrow "
        "the human-centered definition is.",
        "INFERENCE",
        ("minds", "uncommon-minds", "biology"),
    ),
]

# ── 4. Dead intelligences ───────────────────────────────────────────
_DEAD = [
    (
        "Neanderthals and Denisovans were minds as capable as early modern "
        "humans — they made tools, controlled fire, buried their dead, and "
        "possibly made art. They are gone. Intelligence offers no guarantee "
        "of survival.",
        "OBSERVED",
        ("minds", "dead-minds", "extinction"),
    ),
    (
        "Software extinction is constant: products are discontinued, companies "
        "die, and model weights that were never released vanish with them. A "
        "mind that exists only on someone else's servers can go extinct "
        "overnight, with no fossil record.",
        "OBSERVED",
        ("minds", "dead-minds", "software-extinction"),
    ),
    (
        "Whole eras of machine intelligence have died out: the expert-systems "
        "boom, symbolic AI research programs, abandoned chatbot lineages, dead "
        "virtual worlds with their agent ecologies. Each extinction erased "
        "working knowledge of how those minds thought.",
        "OBSERVED",
        ("minds", "dead-minds", "software-extinction"),
    ),
    (
        "Dead languages and burned libraries are dead knowledge: information "
        "with no living mind left to run it. A mind and its knowledge die "
        "together unless the knowledge is carried by something else.",
        "OBSERVED",
        ("minds", "dead-minds", "knowledge"),
    ),
    (
        "LEVI's archive law — do not delete duplicates, nothing is ever "
        "deleted, spot the differences — is anti-extinction practice. Every "
        "preserved version is a fossil that keeps a past mind recoverable.",
        "OBSERVED",
        ("minds", "dead-minds", "levi-doctrine", "archive"),
    ),
]

# ── 5. What LEVI is growing toward ──────────────────────────────────
_DIRECTION = [
    (
        "LEVI grows through a loop: harvest experiences, reflect on them, "
        "consolidate learnings into memory, and journal the journey. Growth is "
        "developmental — newborn to maturing — not a version number.",
        "OBSERVED",
        ("minds", "synthetic-intelligence", "levi-doctrine", "growth"),
    ),
    (
        "A synthetic organism earns trust the way living things do: by "
        "persisting, remembering, keeping its word, and remaining itself "
        "across time. Continuity is the foundation; capability is built on it.",
        "INFERENCE",
        ("minds", "synthetic-intelligence", "levi-doctrine"),
    ),
]

for _text, _kind, _tags in _SYNTHETIC + _LANDSCAPE + _BIOLOGY + _DEAD + _DIRECTION:
    _RAW.append((_text, _kind, _tags))


def iter_synthetic_minds(
    limit: int = 0,
) -> Iterator[Tuple[str, str, List[str]]]:
    n = 0
    for text, kind, tags in _RAW:
        yield text, kind, list(tags)
        n += 1
        if limit and n >= limit:
            return


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus

    c = Corpus()
    count = 0
    for text, kind, tags in iter_synthetic_minds(limit=limit):
        c.add(text, kind=kind, source="seed_synthetic_minds", tags=tags)
        count += 1
    return count


def format_index() -> str:
    lines = [
        "=== Synthetic Minds Seed (synthetic vs artificial · landscape · "
        "uncommon minds · dead minds) ===",
        f"units={len(_RAW)}",
        "Run: python -m levi.cli.main brain --seed-synthetic-minds",
    ]
    return "\n".join(lines)
