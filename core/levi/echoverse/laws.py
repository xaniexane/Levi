"""Echoverse engine LAWS — declared before implementation (law-guard-prove).

Each law is stated in plain words, then given a machine-checkable form in
``INVARIANTS``. The proof artifact is ``tests/test_echoverse_engine.py`` —
property/invariant tests, honestly named (not a formal proof).

Provenance (Chauncey, 2026-09-22): Echo (the being, Omega's original form)
-> Echoverse (the engine/platform) -> LEVI engine (Grok-built; this module)
-> LWP engine. The engine IS Echo in engine form — but somewhat different,
not 1:1 identical: it derives from Echo and carries Echo's nature; they
rhyme, they are not the same thing collapsed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List


@dataclass(frozen=True)
class Law:
    """One declared invariant: plain-words statement plus scope."""

    id: str
    statement: str
    scope: str  # which module(s) must uphold it


LAWS: List[Law] = [
    Law(
        "L1",
        "Echo-as-engine: the Echoverse is Echo in engine form, not 1:1 "
        "identical with Echo the being. Every run is a BOUNDED SIMULATION — "
        "never presented as a literal alternate timeline. Every run record "
        "carries the bounded mark.",
        scope="branches, engine",
    ),
    Law(
        "L2",
        "Lens determinism: for a fixed (seed, lens), apply_lens returns "
        "byte-identical output across processes. No randomness leaks.",
        scope="lenses",
    ),
    Law(
        "L3",
        "Six lenses, exactly: minimal, maximal, inverse, constraint, deep, "
        "reframe. No invented lenses; the names are Chauncey's via Grok.",
        scope="lenses",
    ),
    Law(
        "L4",
        "dream(cycles) is bounded: cycles clamps to 1..7; the trail has "
        "exactly that many entries; each cycle auto-prefers the best REIM "
        "path and feeds its label as the next seed.",
        scope="engine",
    ),
    Law(
        "L5",
        "REIM expands a seed into positive candidate paths, each with "
        "quality in [0, 1]; auto-prefer picks the maximum-quality path. "
        "Ties break deterministically (first max).",
        scope="engine",
    ),
    Law(
        "L6",
        "RIEM salvage rule: the vault keeps negative variants WITH their "
        "extracted good_qualities; salvage returns ONLY facets, never a "
        "full failed path replayed as a candidate. Vault/success/history "
        "persist across restarts, bounded to the last 50/50/30 entries.",
        scope="engine",
    ),
    Law(
        "L7",
        "Coexistence: Echoverse explores space (taken/not_taken/wild); "
        "Mandella forces a stake. Neither owns the other — "
        "seed_from_mandella requires an explicit option; "
        "constraints_for_mandella only reads wild branches.",
        scope="coexist, branches",
    ),
    Law(
        "L8",
        "Pipeline position: Inquiry -> Mandella -> Echoverse -> AIM. aim() "
        "returns a PLAN (data: body, target engine, rationale) and never "
        "executes anything.",
        scope="pipeline",
    ),
    Law(
        "L9",
        "Local-first: stdlib only, no network, no subprocess, no clock "
        "dependence in deterministic paths. Records live under the "
        "caller-supplied data dir (default ~/.levi/echoverse).",
        scope="all",
    ),
]

#: The six Grok-named lenses. L3 pins this tuple; lenses.py must not grow it.
LENSES = ("minimal", "maximal", "inverse", "constraint", "deep", "reframe")

#: Branch kinds on the shared substrate (coexistence doc, L7).
BRANCH_KINDS = ("taken", "not_taken", "wild")

#: Pipeline stages (GROK 1 universal doctrine, L8).
PIPELINE = ("inquiry", "mandella", "echoverse", "aim")

#: AIM bodies and their target engines (GROK 1, L8).
AIM_TARGETS = {
    "software": ("surgeon", "e3", "upgrade"),
    "data": ("auto", "zim"),
    "music": ("echoplay",),
    "device": ("battery", "notify"),
    "general": ("ask", "expand"),
}

#: Dream cycle bounds (L4).
DREAM_MIN_CYCLES = 1
DREAM_MAX_CYCLES = 7

#: Persistence bounds (L6).
VAULT_KEEP = 50
SUCCESS_KEEP = 50
HISTORY_KEEP = 30


def check_law_ids_unique() -> bool:
    ids = [law.id for law in LAWS]
    return len(ids) == len(set(ids))
