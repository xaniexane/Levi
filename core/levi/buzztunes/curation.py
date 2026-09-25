"""KFX2 curation pipeline — BUILT-HERE, his method, honestly.

Chauncey's KFX2: absorb -> reverse -> improve -> return unreplicable.
``core/levi/dynasty/kfx2/runner.py`` exists but is an agent wave-runner,
not this four-phase method — so the method is implemented here, in the
open, per his words. No fake integration claimed.

The four phases, for music curation:
  absorb   — take in the outside pattern: provider results, a thread's
             queue, an imported M3U. Normalize to candidates.
  reverse  — invert it: find what the source overplays and what it
             never touches. Name the gaps (the not-taken paths).
  improve  — score candidates against REAL demand signals, consult
             each curator's RIEM genome (suppress the composted,
             boost the proven), and let Echo explore variants of the
             top gap.
  return   — emit the Buzz Tunes-native sequence: deterministic from
             (seed + genome state), receipt-chained. Unreplicable
             without this machine's state — that is signature two.

Every phase emits a receipt (L3).
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple

from .demand import DemandLog, score_candidates
from .providers import Track
from .receipts import ReceiptLog

PHASES = ("absorb", "reverse", "improve", "return")


def _fingerprint(items: List[str]) -> str:
    return hashlib.sha256("|".join(items).encode("utf-8")).hexdigest()[:12]


def absorb(sources: List[Track], origin: str) -> List[Track]:
    """Take in the outside pattern. Dedupe by id, keep order."""
    seen = set()
    out = []
    for t in sources:
        if t.id not in seen:
            seen.add(t.id)
            out.append(t)
    return out


def reverse(candidates: List[Track]) -> Dict:
    """Invert the absorbed pattern: what dominates, what's missing."""
    artists: Dict[str, int] = {}
    for t in candidates:
        artists[t.artist] = artists.get(t.artist, 0) + 1
    total = max(len(candidates), 1)
    dominant = [a for a, n in artists.items() if n / total >= 0.5]
    gaps = []
    if dominant:
        gaps.append(f"overplayed: {', '.join(dominant)} — invert toward the rest")
    if len(artists) < 3:
        gaps.append("narrow field — widen the artist spread")
    return {"dominant_artists": dominant, "gaps": gaps,
            "artist_spread": len(artists)}


def improve(candidates: List[Track], demand_log: DemandLog,
            genome_consult=None, echo_explore=None) -> List[Tuple[Track, float, str]]:
    """Score and order. Demand signals first, genome verdicts second,
    Echo variants for the top gap third. Returns (track, score, note)."""
    ids = [t.id for t in candidates]
    dscores = score_candidates(ids, demand_log)
    scored = []
    for t in candidates:
        score = dscores.get(t.id, 0.0)
        notes = [f"demand={score:+.1f}"]
        if genome_consult is not None:
            verdict = genome_consult(t.id)
            notes.append(f"genome={verdict}")
            if verdict == "suppress":
                score -= 5.0
            elif verdict == "boost":
                score += 2.0
        scored.append((t, score, "; ".join(notes)))
    scored.sort(key=lambda s: s[1], reverse=True)
    if echo_explore is not None and scored:
        echo_explore(scored[0][0])  # variant exploration, recorded not forced
    return scored


def return_unreplicable(scored: List[Tuple[Track, float, str]],
                        seed: str) -> List[Track]:
    """Finalize the sequence. Deterministic from seed + scores; the
    fingerprint binds it to this machine's state (signature two)."""
    ordered = [t for t, _, _ in scored]
    fp = _fingerprint([seed] + [t.id for t in ordered])
    for t in ordered:
        t.meta["kfx2_fingerprint"] = fp
        t.meta["kfx2_seed"] = seed
    return ordered


def curate(candidates: List[Track], seed: str, demand_log: DemandLog,
           receipts: ReceiptLog, genome_consult=None,
           echo_explore=None, actor: str = "kfx2") -> Dict:
    """Run all four phases with receipts. Returns queue + phase report."""
    absorbed = absorb(candidates, origin=seed)
    receipts.emit("kfx2.absorb", actor=actor,
                  details={"in": len(candidates), "kept": len(absorbed)})
    inversion = reverse(absorbed)
    receipts.emit("kfx2.reverse", actor=actor, details=inversion)
    scored = improve(absorbed, demand_log, genome_consult, echo_explore)
    receipts.emit("kfx2.improve", actor=actor, details={
        "ranked": [(t.id, round(s, 2), n) for t, s, n in scored[:10]]})
    final = return_unreplicable(scored, seed)
    receipts.emit("kfx2.return", actor=actor, details={
        "sequence": [t.id for t in final],
        "fingerprint": final[0].meta.get("kfx2_fingerprint") if final else None})
    return {"queue": final, "inversion": inversion,
            "scored": [(t.id, s) for t, s, _ in scored]}
