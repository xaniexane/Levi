"""LEVI Surgeon sandbox gate — propose → analyze → HITL → apply.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

The gate NEVER executes code. ``analyze`` inspects proposed text and
produces a report; ``apply`` writes the proposed text to a target path
only when the report is clean AND the caller passes an explicit human
confirmation (``confirmed=True``). There is no auto-confirm path.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Patterns that unconditionally fail analysis. The gate does not run code,
# so this list guards what LEVI is willing to *write*, not what it runs.
_BLOCKED = [
    (re.compile(r"\beval\s*\("), "eval("),
    (re.compile(r"\bFunction\s*\("), "Function("),
    (re.compile(r"\bchild_process\b"), "child_process"),
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\bos\.system\b"), "os.system"),
    (re.compile(r"\bos\.popen\b"), "os.popen"),
    (re.compile(r"\bpickle\.loads?\b"), "pickle.load(s)"),
    (re.compile(r"\bmarshal\.loads?\b"), "marshal.load(s)"),
    (re.compile(r"\brm\s+-rf\s+/"), "rm -rf /"),
    (re.compile(r"\bDROP\s+TABLE\b", re.I), "DROP TABLE"),
    (re.compile(r":\(\)\{\s*:\|\:&\s*\};:"), "fork bomb"),
]

_BRACKET_PAIRS = [("{", "}"), ("(", ")"), ("[", "]")]

_TODO_RE = re.compile(r"\bTODO\b|\bFIXME\b", re.I)

_MAX_HISTORY = 50


@dataclass
class SandboxReport:
    id: str
    ts: float
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
        }


class SandboxGate:
    """Analyze-then-apply gate for code surgery. No execution, ever."""

    def __init__(self) -> None:
        self.history: List[SandboxReport] = []

    def analyze(
        self, original: str, proposed: str, meta: Optional[Dict[str, Any]] = None
    ) -> SandboxReport:
        """Inspect ``proposed`` against ``original``; return a report.

        Pure analysis — no I/O, no execution. Reports are kept in a
        bounded in-memory history.
        """
        original = str(original or "")
        proposed = str(proposed or "")
        report = SandboxReport(
            id=f"sb_{int(time.time() * 1000):x}",
            ts=time.time(),
            ok=True,
            metrics={
                "orig_len": len(original),
                "prop_len": len(proposed),
                "delta": len(proposed) - len(original),
            },
        )
        try:
            if not proposed.strip():
                report.ok = False
                report.errors.append("proposed code is empty")
            for a, b in _BRACKET_PAIRS:
                if proposed.count(a) != proposed.count(b):
                    report.warnings.append(
                        f"unbalanced {a}{b} "
                        f"({proposed.count(a)} vs {proposed.count(b)})"
                    )
            for rx, label in _BLOCKED:
                if rx.search(proposed):
                    report.ok = False
                    report.errors.append(f"dangerous pattern blocked: {label}")
            if _TODO_RE.search(proposed):
                report.warnings.append("contains TODO/FIXME markers")
            if report.errors:
                report.ok = False
        except Exception as exc:  # never let analysis itself crash the gate
            report.ok = False
            report.errors.append(f"analysis error: {exc}")
        self.history.append(report)
        self.history = self.history[-_MAX_HISTORY:]
        return report

    def apply(
        self,
        proposed: str,
        report: Optional[SandboxReport],
        target: Path,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Write ``proposed`` to ``target``.

        Requires ALL of: a clean report (``report.ok``), the report's id to
        match the analysis just performed is the caller's responsibility,
        and ``confirmed=True`` — an explicit human confirmation. There is
        no other path to ``True``.
        """
        if report is None or not report.ok:
            return {"ok": False, "reason": "analysis failed or missing"}
        if not confirmed:
            return {"ok": False, "reason": "HITL confirmation required"}
        target = Path(target)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(proposed), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "reason": f"write failed: {exc}"}
        return {"ok": True, "report_id": report.id, "path": str(target)}


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    _GATE = SandboxGate()

    def _skill_sandbox_analyze(args):
        args = args or {}
        rep = _GATE.analyze(
            str(args.get("original") or ""), str(args.get("proposed") or "")
        )
        d = rep.to_dict()
        return f"ok={d['ok']} errors={d['errors']} warnings={d['warnings']}"

    SANDBOX_SKILLS = [
        Skill(
            id="surgeon_sandbox_analyze",
            name="Sandbox Analyze",
            description="Analyze proposed code before apply (no execution, no writes)",
            category="factory",
            risk_level=SkillRisk.INFO,
            handler=_skill_sandbox_analyze,
            tags=["surgeon", "sandbox", "analyze"],
        ),
        Skill(
            id="surgeon_sandbox_apply",
            name="Sandbox Apply",
            description="Apply analyzed code to a path — clean report AND explicit human confirmation required",
            category="factory",
            risk_level=SkillRisk.MODERATE,
            permissions=["surgeon.apply"],
            requires_confirmation=True,
            handler=None,
            tags=["surgeon", "sandbox", "apply"],
        ),
    ]
except ImportError:  # pragma: no cover
    SANDBOX_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
