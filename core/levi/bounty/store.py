"""Findings persistence — attack-surface inventory with change detection.

Stored at ~/.levi/bounty/findings.json:
  findings: [{id, target, scope, kind, detail, evidence,
              first_seen, last_seen}]
  runs:     [{id, domain, started_at, finished_at, finding_ids}]

Dedup key: sha256(target | kind | detail). A repeat sighting refreshes
last_seen; first_seen never moves — that is what powers "new since last
run". Every finding records the scope entry that authorized it.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_PATH = Path.home() / ".levi" / "bounty" / "findings.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def finding_id(target: str, kind: str, detail: str) -> str:
    return hashlib.sha256(f"{target}|{kind}|{detail}".encode()).hexdigest()[:12]


@dataclass
class Finding:
    id: str
    target: str
    scope: str  # enrolled scope entry that authorized this finding
    kind: str  # subdomain | open_port | http_service | tls_cert |
    # archived_url | js_endpoint | possible_exposure
    detail: str
    evidence: str = ""
    first_seen: str = field(default_factory=_now)
    last_seen: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in ("id", "target", "scope", "kind", "detail"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Finding.{name} must be a non-empty string, got {value!r}"
                )
        if not isinstance(self.evidence, str):
            raise ValueError(
                f"Finding.evidence must be a string, got {self.evidence!r}"
            )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "Finding":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class FindingStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.findings: Dict[str, Finding] = {}
        self.runs: List[Dict[str, object]] = []
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            findings = raw.get("findings") or []
            if not isinstance(findings, list):
                raise ValueError("'findings' must be a list")
            for f in findings:
                try:
                    finding = Finding.from_dict(f)
                    self.findings[finding.id] = finding
                except Exception:
                    continue  # one corrupt entry must not kill the history
            runs = raw.get("runs") or []
            if not isinstance(runs, list):
                raise ValueError("'runs' must be a list")
            self.runs = [r for r in runs if isinstance(r, dict)]
        except Exception as exc:
            # Corrupt findings file: warn loudly, start empty rather
            # than crash mid-run. Finding history is recoverable by
            # re-running recon; silently dropping it would not be.
            warnings.warn(
                f"bounty findings file {self.path} is unreadable "
                f"({type(exc).__name__}); starting with an empty history. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=3,
            )
            self.findings = {}
            self.runs = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "findings": [f.to_dict() for f in self.findings.values()],
            "runs": self.runs[-50:],
            "updated_at": _now(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # -- findings ----------------------------------------------------------
    def add(
        self,
        target: str,
        scope: str,
        kind: str,
        detail: str,
        evidence: str = "",
    ) -> Tuple[Finding, bool]:
        """Add or refresh a finding. Returns (finding, is_new).

        Raises ValueError when a required field is missing/blank —
        findings are the recon product and silent garbage rows are
        worse than a clear rejection.
        """
        for name, value in (
            ("target", target),
            ("scope", scope),
            ("kind", kind),
            ("detail", detail),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"finding {name} must be a non-empty string, got {value!r}"
                )
        if not isinstance(evidence, str):
            raise ValueError(f"finding evidence must be a string, got {evidence!r}")
        fid = finding_id(target, kind, detail)
        now = _now()
        existing = self.findings.get(fid)
        if existing:
            existing.last_seen = now
            if evidence and not existing.evidence:
                existing.evidence = evidence
            self._persist()
            return existing, False
        finding = Finding(
            id=fid,
            target=target,
            scope=scope,
            kind=kind,
            detail=detail,
            evidence=evidence,
        )
        self.findings[fid] = finding
        self._persist()
        return finding, True

    # -- runs / change detection -------------------------------------------
    def record_run(
        self, domain: str, started_at: str, finding_ids: List[str]
    ) -> Dict[str, object]:
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError(f"domain must be a non-empty string, got {domain!r}")
        if not isinstance(started_at, str) or not started_at.strip():
            raise ValueError(
                f"started_at must be a non-empty string, got {started_at!r}"
            )
        if not isinstance(finding_ids, list) or not all(
            isinstance(fid, str) for fid in finding_ids
        ):
            raise ValueError("finding_ids must be a list of strings")
        run = {
            "id": hashlib.sha256(f"{domain}{started_at}".encode()).hexdigest()[:8],
            "domain": domain,
            "started_at": started_at,
            "finished_at": _now(),
            "finding_ids": finding_ids,
        }
        self.runs.append(run)
        self._persist()
        return run

    def new_since_last_run(self) -> List[Finding]:
        """Findings first seen during the most recent run.

        A finding is 'new' when its first_seen is at/after the latest
        run's started_at. With no runs recorded, everything is new.
        """
        if not self.runs:
            return sorted(self.findings.values(), key=lambda f: f.first_seen)
        latest_started = self.runs[-1]["started_at"]
        return sorted(
            (f for f in self.findings.values() if f.first_seen >= latest_started),
            key=lambda f: f.first_seen,
        )

    def list(self, kind: Optional[str] = None) -> List[Finding]:
        if kind is not None and not isinstance(kind, str):
            raise ValueError(
                f"kind must be a string or None, got {type(kind).__name__}"
            )
        items = list(self.findings.values())
        if kind:
            items = [f for f in items if f.kind == kind]
        return sorted(items, key=lambda f: (f.target, f.kind, f.detail))
