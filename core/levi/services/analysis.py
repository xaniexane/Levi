"""AI analysis step of the service-offering standard.

An analysis reports what was found — findings with evidence,
severity, and recommendations — and never fabricates. Every finding
carries its evidence; an empty report states honestly that nothing
was recorded, never that nothing exists.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

SEVERITIES = ("info", "low", "medium", "high", "critical")


class AnalysisError(ValueError):
    """Raised when an analysis report violates the no-fabrication rules."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _analysis_dir(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Finding:
    """One thing the analysis found. Evidence is mandatory."""

    finding: str
    severity: str = "info"
    evidence: str = ""
    recommendation: str = ""

    def __post_init__(self) -> None:
        if not self.finding or not self.finding.strip():
            raise AnalysisError("finding text must be non-empty")
        if self.severity not in SEVERITIES:
            raise AnalysisError(
                f"severity must be one of {SEVERITIES}, got {self.severity!r}"
            )
        if not self.evidence or not self.evidence.strip():
            raise AnalysisError(
                "every finding requires evidence — "
                "analysis reports what was found, never invents it"
            )


@dataclass
class AnalysisReport:
    """A structured AI analysis of a service subject.

    findings: what was examined and what turned up (with evidence).
    summary: the honest read. confidence: 0..1 honest self-grade.
    An empty findings list means nothing was recorded, not nothing
    exists — the summary must say so.
    """

    report_id: str
    subject: str
    provider: str
    service_type: str
    summary: str = ""
    findings: List[Finding] = field(default_factory=list)
    confidence: Optional[float] = None
    analyzed_at: str = field(default_factory=_utcnow)
    sensed_from: str = ""  # DemandPulse opportunity id, if sensed

    def __post_init__(self) -> None:
        if not self.subject or not self.subject.strip():
            raise AnalysisError("analysis subject must be non-empty")
        if not self.provider or not self.provider.strip():
            raise AnalysisError("provider must be non-empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise AnalysisError(
                f"confidence must be 0..1, got {self.confidence!r}"
            )
        for f in self.findings:
            if not isinstance(f, Finding):
                raise AnalysisError("findings must be Finding objects")

    def to_dict(self) -> Dict[str, Any]:
        raw = asdict(self)
        raw["findings"] = [asdict(f) for f in self.findings]
        return raw

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AnalysisReport":
        data = dict(raw)
        data["findings"] = [Finding(**f) for f in raw.get("findings", [])]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class AnalysisStore:
    """Owner-only store of analysis reports, one JSONL line per report."""

    def __init__(self, home: Optional[Path] = None):
        self.path = _analysis_dir(home) / "reports.jsonl"
        if not self.path.exists():
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(fd)
        else:
            os.chmod(self.path, 0o600)

    def save(self, report: AnalysisReport) -> AnalysisReport:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report.to_dict()) + "\n")
        return report

    def get(self, report_id: str) -> Optional[AnalysisReport]:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except Exception:
                continue
            if raw.get("report_id") == report_id:
                return AnalysisReport.from_dict(raw)
        return None

    def list(self) -> List[AnalysisReport]:
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(AnalysisReport.from_dict(json.loads(line)))
            except Exception:
                continue
        return out


def analyze_service(
    *,
    subject: str,
    provider: str,
    service_type: str,
    summary: str,
    findings: List[Mapping[str, str]],
    confidence: Optional[float] = None,
    sensed_from: str = "",
    home: Optional[Path] = None,
) -> AnalysisReport:
    """Record an AI analysis of a service subject.

    The analysis is a report of what was examined and found — it
    never fabricates. Every finding needs evidence; confidence is
    an honest self-grade, never a guarantee.
    """
    import uuid

    report = AnalysisReport(
        report_id="anl_" + uuid.uuid4().hex[:10],
        subject=subject,
        provider=provider,
        service_type=service_type,
        summary=summary,
        findings=[Finding(**f) for f in findings],
        confidence=confidence,
        sensed_from=sensed_from,
    )
    return AnalysisStore(home=home).save(report)


def record_analysis(report: AnalysisReport, *, home: Optional[Path] = None) -> AnalysisReport:
    """Persist a pre-built analysis report."""
    return AnalysisStore(home=home).save(report)
