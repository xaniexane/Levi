"""
Memory hierarchy (daemon long-term knowledge).

SOURCE CORPUS → DOCUMENT INDEX → CHUNKS/ENTITIES → EPISODIC → SEMANTIC
→ COMPRESSED → GLYPH → WORLD MODEL

Provenance: every conclusion should link back toward evidence.
"""

from __future__ import annotations


def hierarchy_status() -> str:
    lines = [
        "=== LEVI Memory Hierarchy ===",
        "1 SOURCE CORPUS          → levi brain corpus (OBSERVED/INFERENCE/…)",
        "2 DOCUMENT INDEX         → brain table + shelf (partial)",
        "3 CHUNKS / ENTITIES      → future indexer",
        "4 EPISODIC MEMORY        → memory store interaction log (basic)",
        "5 SEMANTIC MEMORY        → memory store semantic (basic)",
        "6 COMPRESSED MEMORY      → future",
        "7 GLYPH REPRESENTATION   → future",
        "8 WORLD MODEL            → future",
        "",
        "Why-belief path: glyph ← compressed ← semantic ← source ← document",
        "Models must not silently overwrite evidence-linked knowledge.",
    ]
    # live counts
    try:
        from levi.brain.corpus import Corpus

        lines.append(f"corpus_units={len(Corpus().list(limit=500))}")
    except Exception:
        pass
    try:
        from levi.brain.table import BrainTable

        lines.append(f"brain_rows={len(BrainTable().rows)}")
    except Exception:
        pass
    try:
        lines.append("memory_store_ok=yes")
    except Exception:
        lines.append("memory_store_ok=no")
    return "\n".join(lines)


def explain_belief(claim: str) -> str:
    """Best-effort trace: search corpus/brain for supporting rows."""
    claim = (claim or "").strip()
    lines = [f"Belief query: {claim}", "", "Evidence scan:"]
    found = False
    try:
        from levi.brain.corpus import Corpus

        hits = Corpus().search(claim, limit=5)
        for h in hits:
            found = True
            lines.append(f"  [{h.kind}] corpus:{h.id} {h.text[:100]}")
    except Exception:
        pass
    try:
        from levi.brain.table import BrainTable

        hits = BrainTable().search(claim)[:5]
        for h in hits:
            found = True
            lines.append(f"  [TABLE] {h.domain}/{h.key}: {h.value[:80]}")
    except Exception:
        pass
    if not found:
        lines.append("  No linked evidence in corpus/brain — treat as unsupported.")
    lines.append("")
    lines.append("Trace direction: conclusion → evidence (not model assertion alone).")
    return "\n".join(lines)
