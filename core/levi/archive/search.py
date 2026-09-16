"""Search and browse the Archive: text search, filters, museum wings.

Collections are curated groupings — the museum's wings. They are defined
by deterministic keyword rules over record text, so they stay explainable:
every wing lists the keywords that admitted each record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .record import ArchiveRecord
from .store import ArchiveStore, tokenize

import re

# (wing slug, display name, description, keywords)
_COLLECTIONS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    (
        "memory-arts",
        "Memory Arts",
        "Techniques for remembering: palaces, commonplaces, card systems.",
        (
            "memory palace",
            "method of loci",
            "mnemonic",
            "commonplace",
            "florilegia",
            "kardex",
            "edge-notched",
            "uniterm",
            "colon classification",
            "pinakes",
            "mundaneum",
            "tironian",
        ),
    ),
    (
        "hypertext",
        "Hypertext & Trails",
        "Linking and trails before and beyond the web.",
        (
            "xanadu",
            "hypertext",
            "linkbase",
            "memex",
            "trail",
            "transclusion",
            "zigzag",
            "microcosm",
            "hyper-g",
            "intermedia",
            "notecards",
            "augment",
        ),
    ),
    (
        "offline-first",
        "Offline-First",
        "Sync, replication, and namespaces that assume disconnection.",
        (
            "replication",
            "offline",
            "replica",
            "namespace",
            "9p",
            "plan 9",
            "inferno",
            "groove",
            "p2p",
            "peer-to-peer",
            "sync",
        ),
    ),
    (
        "ai-lineage",
        "AI Lineage",
        "The ancestors: expert systems, cognitive architectures, planners.",
        (
            "soar",
            "act-r",
            "expert system",
            "cyc",
            "eurisko",
            "goap",
            "blackboard",
            "hearsay",
            "ops5",
            "art ",
            "planner",
            "cognitive",
        ),
    ),
    (
        "analytical-craft",
        "Analytical Craft",
        "Ways of thinking: competing hypotheses, morphological boxes, grids.",
        (
            "competing hypotheses",
            "morphological",
            "repertory grid",
            "triz",
            "de bono",
            "ach ",
            "zwicky",
            "kelly",
        ),
    ),
    (
        "operating-systems",
        "Operating Systems",
        "Dead and sidelined OSes and their load-bearing ideas.",
        (
            "operating system",
            "microkernel",
            "beos",
            "amigaos",
            "qnx",
            "oberon",
            "lisp machine",
            "inferno",
            "eros",
            "keykos",
        ),
    ),
    (
        "dead-languages",
        "Dead Languages",
        "Programming languages and environments ahead of their time.",
        (
            "smalltalk",
            "hypertalk",
            "newtonscript",
            "interlisp",
            "limbo",
            "mumps",
            "self ",
            "arexx",
            "applescript",
            "language",
        ),
    ),
    (
        "productivity",
        "Productivity Systems",
        "Dead ways of organizing work and attention.",
        (
            "tickler",
            "ivy lee",
            "franklin",
            "agenda",
            "ecco",
            "improv",
            "canon cat",
            "data detectors",
            "productivity",
        ),
    ),
    (
        "communication",
        "Communication Protocols",
        "Codes, prowords, and compression before the internet.",
        (
            "q-code",
            "proword",
            "telegraph",
            "codebook",
            "chappe",
            "quipu",
            "pneumatic",
            "radiotelephony",
        ),
    ),
    (
        "verification",
        "Verification Discipline",
        "How the careful got things right: duplex checks, pipelines.",
        (
            "duplex",
            "verification",
            "t-5",
            "therblig",
            "pipeline",
            "double-check",
            "almanac",
        ),
    ),
)


@dataclass
class Wing:
    slug: str
    name: str
    description: str
    record_ids: List[str]
    matched_keywords: Dict[str, List[str]]  # record id -> keywords that admitted it


def _record_text(rec: ArchiveRecord) -> str:
    return " ".join(
        [
            rec.title,
            rec.era,
            rec.summary,
            rec.mechanism,
            rec.decline,
            rec.revival_recipe,
            rec.levi_application,
        ]
    ).lower()


def _wing_patterns(keywords: Tuple[str, ...]) -> List[Tuple[str, "re.Pattern"]]:
    # word-boundary matching: "ach" must not match "each", "art" must not
    # match "part". Keywords are matched case-insensitively on lowercased text.
    return [(kw, re.compile(r"\b" + re.escape(kw.strip()) + r"\b")) for kw in keywords]


def build_collections(records: List[ArchiveRecord]) -> Dict[str, Wing]:
    wings: Dict[str, Wing] = {}
    for slug, name, desc, keywords in _COLLECTIONS:
        patterns = _wing_patterns(keywords)
        ids: List[str] = []
        matched: Dict[str, List[str]] = {}
        for rec in records:
            text = _record_text(rec)
            hits = [kw.strip() for kw, pat in patterns if pat.search(text)]
            if hits:
                ids.append(rec.id)
                matched[rec.id] = hits
        wings[slug] = Wing(
            slug=slug,
            name=name,
            description=desc,
            record_ids=ids,
            matched_keywords=matched,
        )
    return wings


def collection_slugs() -> List[str]:
    return [c[0] for c in _COLLECTIONS]


@dataclass
class Hit:
    record: ArchiveRecord
    score: float
    why: str


def search(
    store: ArchiveStore,
    query: str = "",
    kind: Optional[str] = None,
    rating: Optional[str] = None,
    status: Optional[str] = None,
    era: Optional[str] = None,
    limit: int = 20,
) -> List[Hit]:
    """Ranked search with filters. Deny-closed on bad filter values."""
    from .record import KINDS, RATINGS, STATUSES

    if kind is not None and kind not in KINDS:
        raise ValueError("bad kind filter: %r" % kind)
    if rating is not None and rating not in RATINGS:
        raise ValueError("bad rating filter: %r" % rating)
    if status is not None and status not in STATUSES:
        raise ValueError("bad status filter: %r" % status)

    tokens = tokenize(query)
    hits: List[Hit] = []
    for rec in store.all():
        if kind and rec.kind != kind:
            continue
        if rating and rec.rating != rating:
            continue
        if status and rec.status != status:
            continue
        if era and era.lower() not in rec.era.lower():
            continue
        if not tokens:
            hits.append(Hit(rec, 1.0, "browse"))
            continue
        title_t = set(tokenize(rec.title))
        mech_t = set(tokenize(rec.mechanism))
        rest_t = set(
            tokenize(
                " ".join(
                    [rec.summary, rec.decline, rec.revival_recipe, rec.levi_application]
                )
            )
        )
        score = 0.0
        why_bits = []
        for tok in tokens:
            if tok in title_t:
                score += 3.0
                why_bits.append("title:%s" % tok)
            elif tok in mech_t:
                score += 2.0
                why_bits.append("mechanism:%s" % tok)
            elif tok in rest_t:
                score += 1.0
                why_bits.append("text:%s" % tok)
            else:
                # prefix fallback: "replic" matches "replication"
                for cand, w, tag in (
                    (title_t, 1.5, "title~"),
                    (mech_t, 1.0, "mechanism~"),
                    (rest_t, 0.5, "text~"),
                ):
                    if any(t.startswith(tok) for t in cand):
                        score += w
                        why_bits.append("%s%s" % (tag, tok))
                        break
        if score > 0:
            hits.append(Hit(rec, score, ",".join(why_bits)))
    hits.sort(key=lambda h: (-h.score, h.record.title))
    return hits[:limit]


def stats(store: ArchiveStore) -> Dict[str, object]:
    by_kind: Dict[str, int] = {}
    by_rating: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for rec in store.all():
        by_kind[rec.kind] = by_kind.get(rec.kind, 0) + 1
        by_rating[rec.rating] = by_rating.get(rec.rating, 0) + 1
        by_status[rec.status] = by_status.get(rec.status, 0) + 1
    wings = build_collections(store.all())
    return {
        "records": store.count(),
        "by_kind": by_kind,
        "by_rating": by_rating,
        "by_status": by_status,
        "wings": {slug: len(w.record_ids) for slug, w in wings.items()},
    }
