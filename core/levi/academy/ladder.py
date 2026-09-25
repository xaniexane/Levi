"""Build ladder — concrete readiness, not placeholders. LEVI-native recreation.

Idea studied: the keeper's earlier "build ladder" ran staged readiness
checks (kernel boot, opportunity scaffold, builder/ops scaffold, model
relay) and reported a pass/fail ladder plus a readiness percentage.

This is the LEVI-native version: a generic step registry any module can
hook into, hermetic check functions that never raise out of the ladder
(they report), a human-readable report, and a machine-readable JSON form
for automation gates.

A check is any callable returning ``(ok: bool, detail: str)``; exceptions
become a failed check with the error as the detail. Steps are ordered.

Stdlib-only.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Tuple

Check = Tuple[str, Callable[[], Tuple[bool, str]]]
ReportRow = Tuple[str, bool, str]


def _run_check(name: str, fn: Callable[[], Tuple[bool, str]]) -> ReportRow:
    try:
        ok, detail = fn()
        return name, bool(ok), str(detail)[:200]
    except Exception as e:  # noqa: BLE001 - ladder must never raise
        return name, False, f"{type(e).__name__}: {e}"[:200]


class BuildLadder:
    """Registered readiness steps with run/report/json output."""

    def __init__(self):
        self._steps: Dict[str, Dict[str, Any]] = {}

    def register_step(self, name: str, goal: str, checks: List[Check]) -> "BuildLadder":
        self._steps[name] = {"goal": goal, "checks": list(checks)}
        return self

    def step_names(self) -> List[str]:
        return list(self._steps)

    def run_step(self, name: str) -> Dict[str, Any]:
        if name not in self._steps:
            raise KeyError(f"unknown ladder step: {name}")
        spec = self._steps[name]
        rows = [_run_check(n, fn) for n, fn in spec["checks"]]
        passed = sum(1 for _, ok, _ in rows if ok)
        return {
            "step": name,
            "goal": spec["goal"],
            "passed": passed,
            "total": len(rows),
            "pass": passed == len(rows) and len(rows) > 0,
            "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in rows],
        }

    def run_all(self) -> List[Dict[str, Any]]:
        return [self.run_step(name) for name in self._steps]

    def readiness_pct(self) -> Dict[str, Any]:
        results = self.run_all()
        total = sum(r["total"] for r in results)
        passed = sum(r["passed"] for r in results)
        rate = passed / total if total else 0.0
        return {
            "pass_rate": round(rate, 3),
            "passed": passed,
            "total": total,
            "all_pass": all(r["pass"] for r in results) and bool(results),
        }

    def format_ladder(self) -> str:
        lines = ["=== LEVI Build Ladder ===", ""]
        for result in self.run_all():
            lines.append(
                f"{result['step']}  [{result['passed']}/{result['total']}]"
                f"  {'PASS' if result['pass'] else 'FAIL'}"
            )
            lines.append(f"  Goal: {result['goal']}")
            for c in result["checks"]:
                mark = "ok" if c["ok"] else "FAIL"
                lines.append(f"    [{mark}] {c['name']:28} {c['detail']}")
            lines.append("")
        r = self.readiness_pct()
        lines.append(
            f"Readiness: {r['passed']}/{r['total']} "
            f"({r['pass_rate'] * 100:.1f}%)"
            f" — {'READY' if r['all_pass'] else 'NOT READY'}"
        )
        return "\n".join(lines)

    def ladder_json(self) -> str:
        return json.dumps(
            {"steps": self.run_all(), "readiness": self.readiness_pct()},
            indent=2,
        )


def _kernel_boot_checks() -> List[Check]:
    def import_core():
        import levi.lwp  # noqa: F401
        import levi.cybrus  # noqa: F401
        import levi.academy  # noqa: F401
        import levi.founders  # noqa: F401

        return True, "levi.lwp, levi.cybrus, levi.academy, levi.founders import"

    def fusion_compose():
        from levi.lwp.fusion import compose

        plan = compose("calculate the quarterly budget")
        assert plan["genome"]["kind"] == "math"
        return True, "fusion kernel classifies + composes"

    def seal_roundtrip():
        import tempfile
        from pathlib import Path
        from levi.cybrus.seal import SealedEnvelope

        with tempfile.TemporaryDirectory() as td:
            s = SealedEnvelope("ladder-check", Path(td))
            s.seal_text("probe", "ping")
            assert s.open_text("probe") == "ping"
        return True, "sealed envelope roundtrip"

    return [
        ("core_imports", import_core),
        ("fusion_kernel", fusion_compose),
        ("seal_envelope", seal_roundtrip),
    ]


def default_ladder() -> BuildLadder:
    """The ladder LEVI itself climbs: kernel boot first."""
    ladder = BuildLadder()
    ladder.register_step(
        "kernel_boot",
        "LEVI kernel boots: core packages import, fusion composes, "
        "sealed envelopes round-trip.",
        _kernel_boot_checks(),
    )
    return ladder
