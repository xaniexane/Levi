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

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "Finding":
        return cls(
            **{k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        )


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
            for f in raw.get("findings") or []:
                try:
                    finding = Finding.from_dict(f)
                    self.findings[finding.id] = finding
                except Exception:
                    continue
            self.runs = raw.get("runs") or []
        except Exception:
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
        """Add or refresh a finding. Returns (finding, is_new)."""
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
            id=fid, target=target, scope=scope, kind=kind,
            detail=detail, evidence=evidence,
        )
        self.findings[fid] = finding
        self._persist()
        return finding, True

    # -- runs / change detection -------------------------------------------
    def record_run(
        self, domain: str, started_at: str, finding_ids: List[str]
    ) -> Dict[str, object]:
        run = {
            "id": hashlib.sha256(
                f"{domain}{started_at}".encode()
            ).hexdigest()[:8],
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
            return sorted(
                self.findings.values(), key=lambda f: f.first_seen
            )
        latest_started = self.runs[-1]["started_at"]
        return sorted(
            (f for f in self.findings.values() if f.first_seen >= latest_started),
            key=lambda f: f.first_seen,
        )

    def list(self, kind: Optional[str] = None) -> List[Finding]:
        items = list(self.findings.values())
        if kind:
            items = [f for f in items if f.kind == kind]
        return sorted(items, key=lambda f: (f.target, f.kind, f.detail))
