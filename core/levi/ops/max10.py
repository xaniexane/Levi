"""MAX ×10 rail — combined densest posture."""

from __future__ import annotations
from datetime import datetime, timezone


def format_max10() -> str:
    from levi.brain.seed_knowledge_max import _RAW as MAX
    from levi.brain.seed_knowledge_x10 import _RAW as X10
    from levi.premium.features import FEATURES
    from levi.premium.unique import UNIQUES
    from levi.persona.kai9000 import all_variants
    from levi.persona.lattice import PersonaLattice
    from levi.ops.x100 import laws

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
    total = len(MAX) + len(X10)
    lines = [
        "══ LEVI MAX ×10 ══",
        f"at {datetime.now(timezone.utc).isoformat()}",
        "",
        "COUNTS",
        f"  MAX units           {len(MAX)}",
        f"  ×10 expansion       {len(X10)}",
        f"  combined (if both)  {total}",
        f"  premium features    {len(FEATURES)}",
        f"  unique organs       {len(UNIQUES)}",
        f"  KAI-9000 variants   {len(all_variants())}",
        f"  personas            {len(PersonaLattice().keys())}",
        f"  scorecard           {score:.2f}/10",
        f"  enterprise          {ent}",
        "",
        "KAI NOTE",
        "  Original LEVI registers — reverse-engineered concept, heavily modified;",
        "  not third-party source code.",
        "",
        "LAW",
    ]
    for law in laws():
        lines.append(f"  · {law}")
    lines.append("")
    lines.append("SEED")
    lines.append("  levi brain --seed-max")
    lines.append("  levi brain --seed-x10")
    lines.append("  levi brain --seed-expand2")
    lines.append("  levi interpenetrate --smoke")
    return "\n".join(lines)
