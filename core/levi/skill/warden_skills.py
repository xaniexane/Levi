"""Warden skills — executable run-skills for the warden engines.

Two LEVI-native engines keep the house honest:

- ``attest`` — hash-chain receipt attestation (integrity warden)
- ``redline`` — the spend-budget guard (money warden)

Each skill wraps its engine the way the compressed run-skills do: the
engine module is imported lazily inside the handler (it self-registers
on import), the registry runs it, and the verdict comes back as plain
text with the full trace. Engines compute; they never act — so both
skills are risk INFO, no permissions, no confirmation.

``WARDEN_SKILLS`` is the public list. ``expected_ids()`` names every
skill id — used by the test suite.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk


def _run_engine_skill(
    engine_id: str,
    module_path: str,
    headline: Callable[[str, dict, float], str],
) -> Callable[[Optional[Dict[str, object]]], str]:
    """Build the handler: lazy engine import, registry run, text render."""

    def _run(args: Optional[Dict[str, object]] = None) -> str:
        import importlib

        importlib.import_module(module_path)  # self-registers on import
        from levi.engines import registry as eng_registry

        try:
            result = eng_registry.run(engine_id, dict(args or {}))
        except (KeyError, ValueError) as exc:
            return f"engine '{engine_id}' refused: {exc}"
        lines = [headline(engine_id, result.verdict, result.confidence)]
        lines.extend(f"  {t}" for t in result.trace)
        return "\n".join(lines)

    return _run


def _attest_headline(engine_id: str, verdict: dict, confidence: float) -> str:
    status = verdict.get("status")
    if status == "intact":
        head = (
            f"[{engine_id}] INTACT — {verdict.get('receipt_count')} receipts, "
            "every link recomputed and matched"
        )
    elif status == "broken":
        head = (
            f"[{engine_id}] BROKEN at index {verdict.get('break_index')} "
            f"({verdict.get('reason')}) — expected "
            f"{verdict.get('expected')!r}, got {verdict.get('actual')!r}"
        )
    else:
        head = f"[{engine_id}] EMPTY — nothing to attest"
    return f"{head}\nconfidence: {confidence}"


def _redline_headline(engine_id: str, verdict: dict, confidence: float) -> str:
    status = verdict.get("status")
    label = f" [{verdict['label']}]" if verdict.get("label") else ""
    if status == "over":
        head = (
            f"[{engine_id}]{label} OVER — spent {verdict.get('spent')} "
            f"exceeds cap {verdict.get('cap')} by {verdict.get('overshoot')}"
        )
    elif status == "would-breach":
        head = (
            f"[{engine_id}]{label} WOULD-BREACH — pending "
            f"{verdict.get('pending')} crosses the cap by "
            f"{verdict.get('overshoot')} (remaining {verdict.get('remaining')})"
        )
    elif status == "at-risk":
        head = (
            f"[{engine_id}]{label} AT-RISK — remaining "
            f"{verdict.get('remaining')} inside a warn band of cap "
            f"{verdict.get('cap')}"
        )
    else:
        head = (
            f"[{engine_id}]{label} CLEAR — remaining "
            f"{verdict.get('remaining')} of cap {verdict.get('cap')}"
        )
    return f"{head}\nconfidence: {confidence}"


def _attest_skill() -> Skill:
    return Skill(
        id="warden.run-attest",
        name="Run Attest Engine",
        description=(
            "Attest a hash-chained receipt log: recomputes every link "
            "against the genesis anchor and reports intact, broken (exact "
            "index and values), or empty. Trusts nothing it was told."
        ),
        category="warden",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["engines", "integrity", "receipts", "attestation", "run"],
        version="1.0.0",
        handler=_run_engine_skill("attest", "levi.engines.attest", _attest_headline),
    )


def _redline_skill() -> Skill:
    return Skill(
        id="warden.run-redline",
        name="Run Redline Engine",
        description=(
            "Judge a proposed spend against the hard cap: over, "
            "would-breach (exact overshoot), at-risk (warn band), or "
            "clear. The machine form of the no-spending law."
        ),
        category="warden",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["engines", "budget", "spending", "guard", "run"],
        version="1.0.0",
        handler=_run_engine_skill("redline", "levi.engines.redline", _redline_headline),
    )


WARDEN_SKILLS: List[Skill] = [
    _attest_skill(),
    _redline_skill(),
]


def expected_ids() -> List[str]:
    """Every warden skill id — used by the test suite."""
    return [skill.id for skill in WARDEN_SKILLS]
