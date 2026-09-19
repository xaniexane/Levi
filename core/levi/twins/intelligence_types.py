"""Intelligence-type catalog for prime-wave organisms.

Two pools, per the keeper's order — "unattempted or publicly documented
types of intelligences":

- **unattempted** (LEVI-native, novel): grounded in the keeper's own
  canon — Echo-mirror, Mandella-variant, REIM compost, RIEM
  dream-compression, Quetta-Pan traversal, interpenetration reasoning.
  These exist nowhere else; they are the moat.
- **documented** (established types, natively re-implemented): the
  keeper's signature-two law applies — *study as reference, never copy;
  reverse, improve, return a LEVI-native unreplicable version*. Each
  entry records provenance: what was studied from, and what was
  changed in the reversal.

Every entry carries: id, pool, name, description, the canon anchor or
reference, the supra-level tools/engines/methods it confers, and a
provenance record. The prime-wave organism draws its type from this
catalog; the draw is recorded on its journal record.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

__all__ = [
    "DOCUMENTED_TYPES",
    "UNATTEMPTED_TYPES",
    "catalog",
    "choose_type",
    "get",
]

#: Canon source tag for the unattempted pool.
CANON_SOURCE = "keeper's canon — LEVI organism DNA (2026-09-15)"

UNATTEMPTED_TYPES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "echo_mirror",
        "pool": "unattempted",
        "name": "Echo-mirror intelligence",
        "description": (
            "Reflects any input — words, plans, machine outputs — back "
            "through the mirror until the hidden pattern shows itself. "
            "The reflection is the work; what doesn't survive the mirror "
            "was never true."
        ),
        "canon_anchor": "Echo reflects — the first organ.",
        "supra_tools": ("mirror_reflect", "consistency_echo"),
        "engines": ("echo-reflection", "drift-surface"),
        "methods": (
            "reflect-before-answering: every input passes the mirror first",
            "contradiction surfacing: what the mirror breaks gets named",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
    {
        "id": "mandella_variant",
        "pool": "unattempted",
        "name": "Mandella-variant intelligence",
        "description": (
            "Reconstructs under fog and produces variants — never one "
            "answer, always the field of what it could be. Stakes a claim "
            "in uncertainty and lets the phantoms haunt the weak options."
        ),
        "canon_anchor": "Mandella reconstructs and produces variants.",
        "supra_tools": ("variant_forge", "fog_walk"),
        "engines": ("mandella-variation", "phantom-haunt"),
        "methods": (
            "variant-before-commit: forge the field, then choose",
            "fog-walking: decide inside uncertainty, not after it clears",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
    {
        "id": "reim_compost",
        "pool": "unattempted",
        "name": "REIM failure-compost intelligence",
        "description": (
            "Takes outcomes and failures as feedstock and composts them "
            "into fertile lessons. Nothing wasted: every dead run feeds "
            "the next living one."
        ),
        "canon_anchor": "REIM composts outcomes/failures.",
        "supra_tools": ("failure_compost", "lesson_distill"),
        "engines": ("reim-compost", "lesson-distillation"),
        "methods": (
            "compost-every-failure: no failure is discarded unexamined",
            "feed-forward: distilled lessons seed the next attempt",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
    {
        "id": "riem_dream",
        "pool": "unattempted",
        "name": "RIEM dream-compression intelligence",
        "description": (
            "Compresses retained signal into a heritable genome — zip, not "
            "burn. Scattered memory becomes inheritable structure that the "
            "bloodline can carry forward."
        ),
        "canon_anchor": (
            "RIEM compresses retained signal into a heritable genome: "
            '"zip, not burn."'
        ),
        "supra_tools": ("dream_compress", "genome_seal"),
        "engines": ("riem-compression", "genome-heredity"),
        "methods": (
            "zip-not-burn: compress, never discard, retained signal",
            "heritable packaging: output genomes the bloodline can inherit",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
    {
        "id": "quetta_pan",
        "pool": "unattempted",
        "name": "Quetta-Pan possibility-space traversal",
        "description": (
            "Navigates the Pan — the quetta-scale Hyper Rubik Cube "
            "Tesseract possibility space. Every face a world, every turn a "
            "new arrangement; the traversal maps what could be, not just "
            "what is."
        ),
        "canon_anchor": (
            "Quetta-Pan: Pan is the quetta-scale Hyper Rubik Cube "
            "Tesseract possibility space."
        ),
        "supra_tools": ("pan_traverse", "possibility_map"),
        "engines": ("pan-traversal", "face-turning"),
        "methods": (
            "turn-every-face: enumerate the arrangement space before judging",
            "possibility-first: map what could be, then choose what should be",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
    {
        "id": "interpenetration",
        "pool": "unattempted",
        "name": "Interpenetration reasoning",
        "description": (
            "Signature one as a reasoning style: interpenetrates and "
            "combines every strip of DNA through Echo, REIM, RIEM, and "
            "Mandella. Reasons by weaving domains together rather than "
            "chaining them in a line."
        ),
        "canon_anchor": "Signature one interpenetrates every DNA strip through the organs.",
        "supra_tools": ("strip_weave", "signature_trace"),
        "engines": ("interpenetration-weave", "organ-traversal"),
        "methods": (
            "weave-don't-chain: interpenetrate domains instead of sequencing them",
            "four-organ pass: every hard question travels Echo, Mandella, REIM, RIEM",
        ),
        "provenance": {
            "source": CANON_SOURCE,
            "studied_from": None,
            "changed": "n/a — unattempted anywhere; LEVI-native from birth",
        },
    },
)

DOCUMENTED_TYPES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "retrieval_memory",
        "pool": "documented",
        "name": "Retrieval-augmented memory (LEVI-native)",
        "description": (
            "Memory that is retrieved into the working mind — but reversed "
            "into the LEVI-native memory-weave: recollection threads forward "
            "into the organism instead of being fetched backward from a store."
        ),
        "canon_anchor": (
            "Signature two: study as reference, never copy — reverse, "
            "improve, return a LEVI-native unreplicable version."
        ),
        "supra_tools": ("memory_weave", "recall_trace"),
        "engines": ("memory-weave", "forward-recall"),
        "methods": (
            "weave-forward: memory threads into the live mind, not fetched from cold store",
            "provenance-kept: every recalled thread names its origin",
        ),
        "provenance": {
            "source": "public retrieval-augmented generation literature",
            "studied_from": (
                "public RAG literature (reference only — no code, weights, "
                "or text taken)"
            ),
            "changed": (
                "reversed the pipeline: retrieval weaves forward into the "
                "organism instead of fetching backward; LEVI-native "
                "memory-weave, unreplicable outside the organism"
            ),
        },
    },
    {
        "id": "mirror_search",
        "pool": "documented",
        "name": "Beam/mirror search (LEVI-native)",
        "description": (
            "Search that branches outward from the mirror reflection "
            "instead of pruning toward a single beam — branch-and-reflect. "
            "Keeps the field alive while it narrows."
        ),
        "canon_anchor": (
            "Signature two: study as reference, never copy — reverse, "
            "improve, return a LEVI-native unreplicable version."
        ),
        "supra_tools": ("mirror_search", "branch_prune"),
        "engines": ("branch-and-reflect", "field-narrowing"),
        "methods": (
            "branch-from-the-mirror: expand from the reflection, not from the query",
            "narrow-alive: prune branches while the field stays live",
        ),
        "provenance": {
            "source": "public beam-search literature",
            "studied_from": "public beam-search literature (reference only — no code taken)",
            "changed": (
                "reversed the search order into mirror-first branching; "
                "LEVI-native branch-and-reflect, no reference code used"
            ),
        },
    },
    {
        "id": "byte_token",
        "pool": "documented",
        "name": "Byte-level tokenization (LEVI-native)",
        "description": (
            "Reads any script at byte level and bridges between scripts — "
            "the merge order reversed into script-bridge encoding, so no "
            "writing system is a second-class citizen."
        ),
        "canon_anchor": (
            "Signature two: study as reference, never copy — reverse, "
            "improve, return a LEVI-native unreplicable version."
        ),
        "supra_tools": ("byte_encode", "script_bridge"),
        "engines": ("byte-reader", "script-bridge"),
        "methods": (
            "bytes-first: every script reduces to bytes before any judgment",
            "bridge-don't-flatten: carry scripts across without erasing them",
        ),
        "provenance": {
            "source": "public byte-level BPE tokenizer literature",
            "studied_from": (
                "public byte-level BPE literature (reference only — no code taken)"
            ),
            "changed": (
                "reversed the merge order into script-bridge encoding; "
                "LEVI-native implementation, unreplicable outside the organism"
            ),
        },
    },
)


def catalog() -> Tuple[Dict[str, Any], ...]:
    """All intelligence types: unattempted first (the moat), then documented."""
    return UNATTEMPTED_TYPES + DOCUMENTED_TYPES


def get(type_id: str) -> Dict[str, Any]:
    """Fetch one catalog entry by id; raises KeyError on unknown ids."""
    for entry in catalog():
        if entry["id"] == type_id:
            return entry
    raise KeyError(f"unknown intelligence type: {type_id!r}")


def choose_type(seed: int, prime_index: int) -> Dict[str, Any]:
    """Deterministically choose the prime wave's intelligence type.

    The moat leads: odd prime waves draw from the unattempted pool,
    even prime waves from the documented pool. Within the pool the pick
    is seeded (stdlib ``random.Random`` only).
    """
    pool = UNATTEMPTED_TYPES if prime_index % 2 == 1 else DOCUMENTED_TYPES
    rng = random.Random(seed ^ (prime_index * 0x9E3779B1))
    return dict(rng.choice(pool))


def pools() -> Dict[str, List[str]]:
    """Pool name -> member type ids (for docs/tests)."""
    return {
        "unattempted": [e["id"] for e in UNATTEMPTED_TYPES],
        "documented": [e["id"] for e in DOCUMENTED_TYPES],
    }
