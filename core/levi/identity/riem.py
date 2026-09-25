"""RIEM — controlled compression (identity variant engine).

Compresses REIM lessons into dense genome deltas. Compression, not
collapse: nothing is destroyed — every promoted entry retains the failure
signature and cause, so the genome stays auditable back to the lesson.
Promotion is deterministic: corroboration >= 2 or severity "high".
"""

from __future__ import annotations

from typing import Any, Dict, List

# Cause -> (genome trait, adjustment). Fixed map; adjustments are bounded
# and applied through GenomeStore clamping.
_CAUSE_TRAIT_DELTA = {
    "trait-conflict": ("caution", 0.05),
    "param-drift": ("stability", 0.05),
    "missing-signal": ("novelty", -0.03),
    "resource-exhaustion": ("caution", 0.08),
    "external": ("caution", 0.03),
    "unknown": ("novelty", -0.02),
    "none": ("stability", 0.02),
}


class RIEM:
    """Compress lessons into genome deltas (data only; never writes)."""

    def compress(
        self, lessons: List[Dict[str, Any]], genome: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(lessons, list):
            raise ValueError("compress: lessons must be a list")
        if not isinstance(genome, dict):
            raise ValueError("compress: genome must be a dict")
        known_sigs = genome.get("signatures", {})
        if not isinstance(known_sigs, dict):
            known_sigs = {}

        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for lesson in lessons:
            if not isinstance(lesson, dict):
                continue
            key = (lesson.get("cause", "unknown"), lesson.get("failure_signature", ""))
            groups.setdefault(key, []).append(lesson)

        promoted: List[Dict[str, Any]] = []
        trait_totals: Dict[str, float] = {}
        guards: List[str] = []
        dropped = 0
        for (cause, sig), items in sorted(groups.items()):
            corroboration = len(items) + int(known_sigs.get(sig, 0))
            severities = [i.get("severity", "low") for i in items]
            top = (
                "high"
                if "high" in severities
                else ("medium" if "medium" in severities else "low")
            )
            if corroboration >= 2 or top == "high":
                best = sorted(items, key=lambda i: str(i.get("lesson", "")))[0]
                promoted.append(
                    {
                        "failure_signature": sig,  # signal retained
                        "cause": cause,  # signal retained
                        "lesson": best.get("lesson", ""),
                        "severity": top,
                        "corroboration": corroboration,
                        "source_identity": best.get("source_identity", ""),
                    }
                )
                trait, delta = _CAUSE_TRAIT_DELTA.get(cause, ("novelty", -0.02))
                trait_totals[trait] = trait_totals.get(trait, 0.0) + delta
                guard = "guard: on %s (%s) — %s" % (
                    cause,
                    sig,
                    str(best.get("lesson", ""))[:80],
                )
                if guard not in guards:
                    guards.append(guard)
            else:
                dropped += len(items)

        return {
            "trait_adjustments": {
                k: round(v, 4) for k, v in sorted(trait_totals.items())
            },
            "new_guards": sorted(guards),
            "promoted": sorted(promoted, key=lambda p: p["failure_signature"]),
            "dropped": dropped,
            "promoted_count": len(promoted),
        }
