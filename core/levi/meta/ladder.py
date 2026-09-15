"""
Build ladder — step 1 and up. Concrete readiness, not placeholders.

Step 1 = kernel boots, main organs import, tests green, offline ask works.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _check(name: str, fn) -> Tuple[str, bool, str]:
    try:
        ok, detail = fn()
        return name, bool(ok), detail
    except Exception as e:
        return name, False, str(e)[:120]


def step1_kernel_boot() -> List[Tuple[str, bool, str]]:
    def imports():
        mods = [
            "levi.daemon.unified",
            "levi.daemon.control",
            "levi.lwp.mirror_cascade",
            "levi.lwp.opportunity_rail",
            "levi.brain.corpus",
            "levi.factory.pipeline",
            "levi.builder.emergency",
            "levi.graph.organism",
            "levi.ei.offline_companion",
            "levi.project.hitl",
        ]
        for m in mods:
            __import__(m)
        return True, f"{len(mods)} core modules"

    def offline_ask():
        from levi.ei.offline_companion import synthesize

        t = synthesize("I'm stuck and don't know how", system="")
        return bool(t) and len(t) > 40, f"reply_len={len(t)}"

    def mirror():
        from levi.lwp.mirror_cascade import MirrorCascade

        r = MirrorCascade().run("test seed")
        return bool(r.synthesis), f"fp={r.fingerprint}"

    def rail_plan():
        from levi.lwp.opportunity_rail import OpportunityRail
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            rail = OpportunityRail(path=Path(td) / "r.json")
            car = rail.start("step1 signal")
            return car.gate in ("mirror", "signal"), f"gate={car.gate}"

    def hitl():
        from levi.project.hitl import HITLGate
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            g = HITLGate(path=Path(td) / "h.json")
            r = g.propose("test", "why", "changes", risk="LOW", domain="general")
            return bool(r.id), f"id={r.id}"

    def organism():
        from levi.graph.organism import ORGANS, BLOODSTREAM

        return len(ORGANS) >= 20 and len(BLOODSTREAM) >= 15, f"organs={len(ORGANS)}"

    def control_crisis():
        from levi.daemon.control import select_core_emphasis

        e = select_core_emphasis("I'm panicking and falling apart")
        return e == ["alchemy"], f"emphasis={e}"

    checks = [
        ("core_imports", imports),
        ("offline_companion", offline_ask),
        ("mirror_cascade", mirror),
        ("opportunity_rail", rail_plan),
        ("hitl_gate", hitl),
        ("organism_map", organism),
        ("crisis_core_logic", control_crisis),
    ]
    return [_check(n, f) for n, f in checks]


def format_ladder() -> str:
    rows = step1_kernel_boot()
    ok_n = sum(1 for _, ok, _ in rows if ok)
    lines = [
        "=== LEVI Build Ladder ===",
        "",
        f"STEP 1 — Kernel boot & main path  [{ok_n}/{len(rows)}]",
        "  Goal: importable organism, offline ask, mirror, rail start, HITL, crisis soft path",
        "",
    ]
    for name, ok, detail in rows:
        mark = "✓" if ok else "✗"
        lines.append(f"  {mark} {name:22} {detail}")
    lines.append("")
    if ok_n == len(rows):
        lines.append("STEP 1: PASS — main features usable offline/local.")
    else:
        lines.append("STEP 1: FAIL — fix ✗ items before climbing.")
    lines.append("")
    rows2 = step2_opportunity_smoke()
    ok2 = sum(1 for _, ok, _ in rows2 if ok)
    lines.append(f"STEP 2 — Opportunity scaffold  [{ok2}/{len(rows2)}]")
    for name, ok, detail in rows2:
        mark = "✓" if ok else "✗"
        lines.append(f"  {mark} {name:22} {detail}")
    lines.append("")
    lines.append("STEP 2+ — Vertical (rail end-to-end operator practice)  [operator]")
    rows3 = step3_builder_smoke()
    ok3 = sum(1 for _, ok, _ in rows3 if ok)
    lines.append(f"STEP 3 — Builder / ops scaffold  [{ok3}/{len(rows3)}]")
    for name, ok, detail in rows3:
        mark = "✓" if ok else "✗"
        lines.append(f"  {mark} {name:22} {detail}")
    lines.append("")
    lines.append("STEP 3+ — Builder E5 apply + sandbox daily  [operator]")
    rows4 = step4_relay_smoke()
    ok4 = sum(1 for _, ok, _ in rows4 if ok)
    lines.append(f"STEP 4 — Model relay  [{ok4}/{len(rows4)}]")
    for name, ok, detail in rows4:
        mark = "✓" if ok else "✗"
        lines.append(f"  {mark} {name:22} {detail}")
    lines.append("")
    lines.append("STEP 4+ — Ollama when present (optional)")
    lines.append("STEP 5 — Thin UI organs  [defer for complete-non-enterprise]")
    lines.append("")
    lines.append("Usable main services now (if Step 1 pass):")
    lines.append(
        "  ask · organism · charter · mirror · rail · unified · demand · income"
    )
    lines.append(
        "  brain · project · builder(E4) · echo · mandella · pulse · symbiosis · factory"
    )
    return "\n".join(lines)


def step4_relay_smoke() -> list:
    def relay_test():
        from levi.model.relay import ModelRelay

        out = ModelRelay().test()
        return "PASS" in out and "Offline" in out, "relay --test offline"

    return [_check("relay_offline", relay_test)]


def step3_builder_smoke() -> list:
    def e5_meta():
        from levi.builder.emergency import TIER_META, BuildTier

        return BuildTier.E5 in TIER_META and TIER_META[BuildTier.E5][
            "hitl_default"
        ] is True, "E5 HITL default"

    def ops_layer():
        from levi.ops.layer import OperationalLayer

        s = OperationalLayer().snapshot()
        return s.cycle >= 0, "ops snapshot"

    return [_check("builder_e5_hitl", e5_meta), _check("ops_layer", ops_layer)]


def step2_opportunity_smoke() -> list:
    """Light Step 2 checks — opportunity vertical."""

    def rail_demand_field():
        from levi.lwp.opportunity_rail import RailCar

        f = getattr(RailCar, "__dataclass_fields__", {})
        return "demand_signal_id" in f, "demand_signal_id field"

    def install_script():
        from pathlib import Path

        p = Path(__file__).resolve().parents[3] / "scripts" / "install_local.sh"
        if not p.exists():
            p = (
                Path(__file__).resolve().parents[2].parent
                / "scripts"
                / "install_local.sh"
            )
        return p.exists(), str(p)

    return [
        _check("rail_demand_link", rail_demand_field),
        _check("install_script", install_script),
    ]


def readiness_pct() -> Dict[str, Any]:
    rows = step1_kernel_boot()
    s1 = sum(1 for _, ok, _ in rows if ok) / max(1, len(rows))
    # rough overall toward "fully complete below enterprise"
    # step1 ~40% of that target; remaining steps conceptual until automated
    overall = 0.35 + 0.25 * s1  # ~60% when step1 full if we count built surface
    return {
        "step1_pass_rate": round(s1, 2),
        "step1_ok": all(ok for _, ok, _ in rows),
        "approx_complete_non_enterprise": round(min(0.55, overall + 0.1), 2),
        "main_features_usable": all(ok for _, ok, _ in rows),
    }
