"""LEVI WriteBuild — analyze → format → fix → scaffold → sandbox fusion pipeline.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

The Acode editor APIs of the source are replaced with plain file
operations: the pipeline reads a file, transforms text through ordered
steps, and returns a report. Writing the result back requires explicit
human confirmation, routed through the surgeon sandbox gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.surgeon.sandbox import SandboxGate

STEP_ORDER = ("analyze", "format", "fix", "scaffold", "sandbox")

_WS_EOL = re.compile(r"[ \t]+$", re.M)
_BLANK_RUN = re.compile(r"\n{4,}")
_EQ_NONE = re.compile(r"(\b\w+)\s*==\s*None\b")
_NEQ_NONE = re.compile(r"(\b\w+)\s*!=\s*None\b")
_TODO_RE = re.compile(r"\bTODO\b|\bFIXME\b", re.I)


def analyze_text(text: str) -> Dict[str, Any]:
    """Static facts about ``text``. Pure function."""
    lines = text.split("\n")
    non_empty = [ln for ln in lines if ln.strip()]
    return {
        "lines": len(lines),
        "non_empty": len(non_empty),
        "chars": len(text),
        "looks_python": bool(re.search(r"def\s+\w+\(|import\s+\w+|print\(", text)),
        "looks_js": bool(re.search(r"function\s*\(|=>|const\s+|let\s+", text)),
        "todo_count": len(_TODO_RE.findall(text)),
    }


def format_pass(text: str) -> str:
    """Whitespace normalization only: trailing space, blank-line runs."""
    out = _WS_EOL.sub("", text)
    out = _BLANK_RUN.sub("\n\n\n", out)
    return out


def fix_pass(text: str) -> str:
    """Safe mechanical fixes: tabs → spaces, ``== None`` → ``is None``."""
    out = text.replace("\t", "  ")
    out = _EQ_NONE.sub(r"\1 is None", out)
    out = _NEQ_NONE.sub(r"\1 is not None", out)
    return out


def scaffold_module(goal: str, module_name: str = "levi_module") -> str:
    """Generate a minimal LEVI-style module scaffold from a goal string."""
    safe_goal = re.sub(r"[^a-zA-Z0-9 _-]", "", (goal or "untitled"))[:80] or "untitled"
    safe_mod = re.sub(r"\W", "_", module_name) or "levi_module"
    return (
        f'"""{safe_mod} — {safe_goal}.\n\nGenerated scaffold; fill in the implementation.\n"""\n\n'
        "from __future__ import annotations\n\n\n"
        "def main() -> int:\n"
        f'    """Entry point for {safe_goal}."""\n'
        '    raise NotImplementedError("scaffold: implement me")\n\n\n'
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )


@dataclass
class WriteBuildReport:
    path: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    output: str = ""
    sandbox: Optional[Dict[str, Any]] = None
    applied: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "steps": self.steps,
            "output_len": len(self.output),
            "sandbox": self.sandbox,
            "applied": self.applied,
            "error": self.error,
        }


class WriteBuildPipeline:
    """Fusion pipeline over plain files: analyze → format → fix → scaffold → sandbox."""

    def __init__(self, gate: Optional[SandboxGate] = None) -> None:
        self.gate = gate or SandboxGate()
        self.last_report: Optional[WriteBuildReport] = None

    def run(
        self,
        path: Path,
        steps: tuple = ("analyze", "format", "fix"),
        goal: str = "",
        apply: bool = False,
        confirmed: bool = False,
    ) -> WriteBuildReport:
        """Run the pipeline on ``path``.

        Never writes unless ``apply=True`` **and** ``confirmed=True``
        (explicit human confirmation). The sandbox step analyzes the
        would-be output even when nothing is applied.
        """
        path = Path(path)
        report = WriteBuildReport(path=str(path))
        try:
            src = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.error = f"cannot read {path}: {exc}"
            self.last_report = report
            return report
        if not src.strip():
            report.error = "empty file — nothing to build"
            self.last_report = report
            return report

        text = src
        for name in steps:
            if name not in STEP_ORDER:
                report.steps.append(
                    {"name": name, "ok": False, "error": "unknown step"}
                )
                continue
            if name == "analyze":
                report.steps.append(
                    {"name": "analyze", "ok": True, "detail": analyze_text(text)}
                )
            elif name == "format":
                nxt = format_pass(text)
                report.steps.append(
                    {"name": "format", "ok": True, "delta": len(nxt) - len(text)}
                )
                text = nxt
            elif name == "fix":
                nxt = fix_pass(text)
                report.steps.append(
                    {"name": "fix", "ok": True, "delta": len(nxt) - len(text)}
                )
                text = nxt
            elif name == "scaffold":
                report.steps.append(
                    {
                        "name": "scaffold",
                        "ok": True,
                        "module": scaffold_module(goal or text[:120]),
                    }
                )
            elif name == "sandbox":
                rep = self.gate.analyze(src, text)
                report.sandbox = rep.to_dict()
                report.steps.append({"name": "sandbox", "ok": rep.ok})

        report.output = text
        if apply and text != src:
            res = self.gate.apply(
                text, self._report_for(text, src), path, confirmed=confirmed
            )
            report.applied = bool(res.get("ok"))
            if not report.applied:
                report.steps.append(
                    {"name": "apply", "ok": False, "reason": res.get("reason")}
                )
        self.last_report = report
        return report

    def _report_for(self, text: str, src: str):
        # Analyze the final diff right before a gated apply.
        return self.gate.analyze(src, text)

    def format_report(self, report: Optional[WriteBuildReport] = None) -> str:
        report = report or self.last_report
        if report is None:
            return "No WriteBuild report yet."
        if report.error:
            return f"WriteBuild: {report.error}"
        lines = [
            "## WriteBuild Fusion",
            f"File: `{report.path}` · {len(report.output)} chars",
            "",
        ]
        for s in report.steps:
            status = "ok" if s.get("ok") else "FAIL"
            extra = f" — {s['error']}" if s.get("error") else ""
            extra = f" — {s['reason']}" if s.get("reason") else extra
            lines.append(f"- **{s['name']}**: {status}{extra}")
        if report.applied:
            lines += ["", "_Applied to file (human-confirmed)._"]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    _PIPELINE = WriteBuildPipeline()

    def _skill_writebuild(args):
        args = args or {}
        path = args.get("path")
        if not path:
            return "writebuild needs a file path"
        steps = tuple(args.get("steps") or ("analyze", "format", "fix"))
        rep = _PIPELINE.run(Path(path), steps=steps)
        return _PIPELINE.format_report(rep)

    WRITEBUILD_SKILLS = [
        Skill(
            id="factory_writebuild",
            name="WriteBuild Fusion",
            description="Analyze→format→fix→scaffold→sandbox pipeline over a file (report only unless human-confirmed)",
            category="factory",
            risk_level=SkillRisk.MODERATE,
            permissions=["factory.writebuild"],
            requires_confirmation=True,
            handler=_skill_writebuild,
            tags=["factory", "writebuild", "pipeline"],
        ),
    ]
except ImportError:  # pragma: no cover
    WRITEBUILD_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
