"""
×100 upgrade rail — aggressive improvement surface for LEVI SI.

Operator-facing status: what is strong, what is next, what is law.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        return default if default is not None else str(e)


def snapshot() -> dict:
    personas = _safe(
        lambda: len(
            __import__("levi.persona.lattice", fromlist=["PersonaLattice"])
            .PersonaLattice()
            .keys()
        ),
        0,
    )
    kai = _safe(
        lambda: len(
            __import__("levi.persona.kai9000", fromlist=["all_variants"]).all_variants()
        ),
        0,
    )
    premium = _safe(
        lambda: len(
            __import__("levi.premium.features", fromlist=["FEATURES"]).FEATURES
        ),
        0,
    )
    unique = _safe(
        lambda: len(__import__("levi.premium.unique", fromlist=["UNIQUES"]).UNIQUES), 0
    )
    score = _safe(
        lambda: __import__("levi.cloud.scorecard", fromlist=["evaluate"]).evaluate()[1],
        0.0,
    )
    ent = _safe(
        lambda: __import__(
            "levi.ops.enterprise", fromlist=["run_enterprise_checklist"]
        ).run_enterprise_checklist(),
        [],
    )
    ent_ok = (
        sum(1 for r in ent if getattr(r, "ok", False)) if isinstance(ent, list) else 0
    )
    ent_n = len(ent) if isinstance(ent, list) else 0
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "personas": personas,
        "kai_variants": kai,
        "premium_features": premium,
        "unique_organs": unique,
        "scorecard": round(float(score or 0), 2),
        "enterprise": f"{ent_ok}/{ent_n}",
        "phase": "A",
        "si": "synthetic_intelligence",
    }


def next_slices() -> List[str]:
    return [
        "Install argon2-cffi for production CMK (replace demo HMAC)",
        "Phase B transport: encrypted sync dry-run → real blob sync",
        "Wire live Ollama stream into premium console WebSocket (optional)",
        "Deepen story_prose banks per genre (sensory + supporting cast)",
        "Corpus: domain packs (medicine literacy caution, law literacy caution)",
        "Plugin manifest hardening + signed skill allowlist",
        "Voice hooks (local STT/TTS) behind HITL",
        "Eval harness: golden transcripts for KAI registers",
    ]


def laws() -> List[str]:
    return [
        "Local-complete core — cloud is optional wing",
        "HITL — silence ≠ approve",
        "CMK never owned by server",
        "Export/exit always available",
        "Crisis path works offline",
        "Wit muted under distress",
        "SI does not claim personhood",
        "Scar law — no cheap narrative resets",
    ]


def format_x100() -> str:
    s = snapshot()
    lines = [
        "══ LEVI ×100 UPGRADE RAIL ══",
        f"at {s['at']}",
        "",
        "STATUS",
        f"  personas          {s['personas']}",
        f"  KAI-9000 variants {s['kai_variants']}",
        f"  premium features  {s['premium_features']}",
        f"  unique organs     {s['unique_organs']}",
        f"  scorecard         {s['scorecard']}/10",
        f"  enterprise        {s['enterprise']}",
        f"  phase             {s['phase']}",
        f"  SI                {s['si']}",
        "",
        "LAW (non-negotiable)",
    ]
    for law in laws():
        lines.append(f"  · {law}")
    lines.append("")
    lines.append("NEXT SLICES")
    for i, n in enumerate(next_slices(), 1):
        lines.append(f"  {i}. {n}")
    lines.append("")
    lines.append(
        "Commands: levi kai · levi unique · levi premium · levi scorecard · levi enterprise · levi go"
    )
    return "\n".join(lines)
