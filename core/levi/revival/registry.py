"""revival/registry.py — the unified manifest of LEVI's twenty revivals.

A registry of capability SHAPE only: each entry names the revival module,
its LEVI-native display name (Flair Lens: NOT a faithful recreation label —
the capability is studied, the expression is 100% LEVI), a short title, and
a one-line flair description in LEVI's own voice.

Deliberately LAZY: importing this module imports NONE of the twenty
revival modules. A module object is resolved only through :func:`load` —
explicit, by name, never bulk-imported at registry import time.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RevivalEntry:
    """One revival on the shelf."""

    module: str  # dotted path, e.g. "levi.revival.telescript"
    levi_name: str  # LEVI-native display name (flair lens)
    title: str  # short plain title of the revived capability
    flair: str  # one-line description in LEVI's voice
    origin: str  # "levi-revival/<name>"
    status: str = "active"


_ENTRIES: tuple = (
    RevivalEntry(
        module="levi.revival.agenda",
        levi_name="Glasscockpit",
        title="Explainable auto-filing",
        flair="Files every memory with its reasons on the dashboard — nothing is ever filed silently.",
        origin="levi-revival/agenda",
    ),
    RevivalEntry(
        module="levi.revival.arexx",
        levi_name="Portcaller",
        title="Named command ports",
        flair="Speak to any module by name and it answers or refuses with a typed reason — never silence.",
        origin="levi-revival/arexx",
    ),
    RevivalEntry(
        module="levi.revival.bfs",
        levi_name="Livenets",
        title="Reactive live queries",
        flair="Subscribe once and LEVI pings you the moment matching memory lands — the store watches itself.",
        origin="levi-revival/bfs",
    ),
    RevivalEntry(
        module="levi.revival.blackboard",
        levi_name="Warroom",
        title="Shared hypothesis surface",
        flair="Every specialist mind bids for the floor; hypotheses coexist until the best one wins.",
        origin="levi-revival/blackboard",
    ),
    RevivalEntry(
        module="levi.revival.ecco",
        levi_name="Ledgerleaf",
        title="Outline-and-columns memory",
        flair="Freeform capture with typed views — one memory is a leaf on every branch at once.",
        origin="levi-revival/ecco",
    ),
    RevivalEntry(
        module="levi.revival.eros",
        levi_name="Keywright",
        title="Least-privilege delegation",
        flair="Sub-agents carry keys that open exactly the doors you chose — and no door you didn't.",
        origin="levi-revival/eros",
    ),
    RevivalEntry(
        module="levi.revival.eurisko",
        levi_name="Breedwright",
        title="Self-breeding heuristics",
        flair="Heuristics compete, earn credit, and breed better ones — discoveries are scored, never trusted on arrival.",
        origin="levi-revival/eurisko",
    ),
    RevivalEntry(
        module="levi.revival.goap",
        levi_name="Wayfinder",
        title="Goal-oriented planning",
        flair="Hand me the destination; I plan backward from it and replan the moment the world moves.",
        origin="levi-revival/goap",
    ),
    RevivalEntry(
        module="levi.revival.groove",
        levi_name="Twindesk",
        title="Pairwise workspace sync",
        flair="Two workspaces, no server — offline edits merge honestly, and conflicts go to a human, never auto-merged.",
        origin="levi-revival/groove",
    ),
    RevivalEntry(
        module="levi.revival.inferno",
        levi_name="Chamberlain",
        title="Skill-confinement namespaces",
        flair="Every skill gets its own private chamber of names — it can name nothing it was not granted.",
        origin="levi-revival/inferno",
    ),
    RevivalEntry(
        module="levi.revival.interlisp",
        levi_name="Mirrorwise",
        title="Self-instrumentation",
        flair="LEVI reads its own code to answer who-depends-on-what, and forgives your typos out loud.",
        origin="levi-revival/interlisp",
    ),
    RevivalEntry(
        module="levi.revival.linkbase",
        levi_name="Trellis",
        title="Bidirectional link layer",
        flair="Links live apart from documents, hold in both directions, and heal themselves on rename.",
        origin="levi-revival/linkbase",
    ),
    RevivalEntry(
        module="levi.revival.mumps",
        levi_name="Bedrock",
        title="Persistent global substrate",
        flair="Memory that lives on disk like variables live in memory — one datatype, journaled, honest.",
        origin="levi-revival/mumps",
    ),
    RevivalEntry(
        module="levi.revival.notes",
        levi_name="Fieldnotes",
        title="Offline-first replica sync",
        flair="Work fully offline, sync both ways on connect — conflicts surfaced, never silently merged.",
        origin="levi-revival/notes",
    ),
    RevivalEntry(
        module="levi.revival.otp",
        levi_name="Crashkeeper",
        title="Supervision trees",
        flair="Let it crash — a supervisor is already watching, and it will raise the fallen back up.",
        origin="levi-revival/otp",
    ),
    RevivalEntry(
        module="levi.revival.plan9",
        levi_name="Cellblock",
        title="Per-task namespaces + local IPC",
        flair="Every task gets its own scrubbed room and a private pipe to talk through.",
        origin="levi-revival/plan9",
    ),
    RevivalEntry(
        module="levi.revival.soar",
        levi_name="Chunkwright",
        title="Impasse-to-chunk learning",
        flair="Stuck? Deliberate your way out, then compact the whole struggle into a rule that fires instantly next time.",
        origin="levi-revival/soar",
    ),
    RevivalEntry(
        module="levi.revival.soups",
        levi_name="Soupbowl",
        title="Application-independent object stores",
        flair="Data that outlives its apps — named stores with schemas, quarantined the moment they corrupt.",
        origin="levi-revival/soups",
    ),
    RevivalEntry(
        module="levi.revival.telescript",
        levi_name="Sealtender",
        title="Capability-bounded execution",
        flair="Agents carry signed permits; anything unpermitted is refused at the door — fail closed.",
        origin="levi-revival/telescript",
    ),
    RevivalEntry(
        module="levi.revival.xanadu",
        levi_name="Trailwright",
        title="Transclusion + associative trails",
        flair="Never copy — transclude. Every quote is a live pointer home; every trail a path worth walking.",
        origin="levi-revival/xanadu",
    ),
)


def list_entries() -> List[RevivalEntry]:
    """All twenty revival entries, in manifest order."""
    return list(_ENTRIES)


def _index() -> tuple:
    by_module = {e.module: e for e in _ENTRIES}
    by_levi = {e.levi_name.lower(): e for e in _ENTRIES}
    return by_module, by_levi


def get(name_or_module: str) -> RevivalEntry:
    """Resolve an entry by levi_name, title keyword, or dotted module path.

    Accepts the LEVI display name (case-insensitive), the full module path
    (e.g. ``levi.revival.telescript`` or just ``telescript``), or a title
    keyword. Raises ``KeyError`` when nothing matches, ``ValueError`` when
    the query is ambiguous.
    """
    if not isinstance(name_or_module, str) or not name_or_module.strip():
        raise KeyError(name_or_module)
    q = name_or_module.strip()
    ql = q.lower()

    by_module, by_levi = _index()

    # Exact module path.
    if q in by_module:
        return by_module[q]

    # Bare module tail ("telescript").
    for entry in _ENTRIES:
        if entry.module.rsplit(".", 1)[-1] == ql:
            return entry

    # Exact levi_name.
    if ql in by_levi:
        return by_levi[ql]

    # Title keyword match.
    title_hits = [e for e in _ENTRIES if ql in e.title.lower()]
    if len(title_hits) == 1:
        return title_hits[0]
    if len(title_hits) > 1:
        names = ", ".join(e.levi_name for e in title_hits)
        raise ValueError(f"ambiguous: {q!r} matches {names}")

    # Partial levi_name match (still unambiguous or bust).
    name_hits = [e for e in _ENTRIES if ql in e.levi_name.lower()]
    if len(name_hits) == 1:
        return name_hits[0]
    if len(name_hits) > 1:
        names = ", ".join(e.levi_name for e in name_hits)
        raise ValueError(f"ambiguous: {q!r} matches {names}")

    raise KeyError(name_or_module)


def search(keyword: str) -> List[RevivalEntry]:
    """Find entries whose levi_name, title, or flair matches the keyword."""
    if not isinstance(keyword, str) or not keyword.strip():
        return []
    kw = keyword.strip().lower()
    return [
        e
        for e in _ENTRIES
        if kw in e.levi_name.lower() or kw in e.title.lower() or kw in e.flair.lower()
    ]


def load(entry: RevivalEntry) -> object:
    """Import and return the revival module for ``entry``.

    This is the ONLY place the registry touches the real modules: import
    of ``registry`` itself must never pull in any of the twenty.
    """
    return importlib.import_module(entry.module)
