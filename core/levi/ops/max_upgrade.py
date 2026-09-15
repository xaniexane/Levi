"""MAX upgrade surface — densest operator view of LEVI SI."""

from __future__ import annotations

from datetime import datetime, timezone


def format_max() -> str:
    from levi.persona.lattice import PersonaLattice
    from levi.persona.kai9000 import all_variants
    from levi.premium.features import FEATURES
    from levi.premium.unique import UNIQUES
    from levi.brain.seed_knowledge_max import _RAW as MAX_RAW
    from levi.ops.x100 import laws, next_slices

    try:
        from levi.cloud.scorecard import evaluate

        score = evaluate()[1]
    except Exception:
        score = 0.0
    try:
        from levi.ops.enterprise import run_enterprise_checklist

        rows = run_enterprise_checklist()
        ent = f"{sum(1 for r in rows if r.ok)}/{len(rows)}"
    except Exception:
        ent = "?"

    personas = len(PersonaLattice().keys())
    lines = [
        "══ LEVI MAX UPGRADE ══",
        f"at {datetime.now(timezone.utc).isoformat()}",
        "",
        "COUNTS",
        f"  personas           {personas}",
        f"  KAI-9000 variants  {len(all_variants())}",
        f"  premium features   {len(FEATURES)}",
        f"  unique organs      {len(UNIQUES)}",
        f"  MAX knowledge units {len(MAX_RAW)}",
        f"  scorecard          {score:.2f}/10",
        f"  enterprise         {ent}",
        "",
        "LAW",
    ]
    for law in laws():
        lines.append(f"  · {law}")
    lines.append("")
    lines.append("NEXT")
    for i, n in enumerate(next_slices(), 1):
        lines.append(f"  {i}. {n}")
    lines.append("")
    lines.append("SEED MAX CORPUS")
    lines.append("  python -m levi.cli.main brain --seed-max")
    lines.append("  (writes MAX units into ~/.levi corpus)")
    return "\n".join(lines)
