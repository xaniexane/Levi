"""Symbiotic Residue Ledger — LEVI-native recreation.

Idea studied: the keeper's "symbiosis protocol" sketched four couplings
between a brutalist machine engine and an adaptive organism — locked ROM
anchors, peer style-exchange, phantom memory of erased timelines, and
composting of failed drafts.

This is the LEVI-native engineering translation. No life, biology, or
consciousness claims — just four durable record types that make a long-
running system behave as if it remembers:

- LOCK (immutable anchor): decisions the keeper etched in stone. Append-
  only, versioned, never overwritten in place.
- PHANTOM (supersession memory): when a locked decision is revised, the
  old text is kept as a phantom so the new timeline carries its history.
- COMPOST (failure digestion): failed attempts are recorded with a short
  analysis so the same structural misstep is not repeated. Shape matches
  the growth loop's correction entries (kind, lesson, provenance).
- POLLEN (style fingerprints): offline exchange records of *stylistic*
  fingerprints (rhythm, diction hashes) — never manuscript content, never
  sent anywhere; a local ledger of what the keeper's other instances
  taught this one.

Storage: append-only JSONL. Default dir is ``~/.levi/lwp/``; the env var
``LEVI_SYMBIOSIS_DIR`` overrides (tests use tmp dirs).

Stdlib-only.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

LEDGER_FILE = "symbiosis.jsonl"

_RECORD_TYPES = ("lock", "phantom", "compost", "pollen")


def _default_dir() -> Path:
    override = os.environ.get("LEVI_SYMBIOSIS_DIR")
    if override:
        return Path(override)
    home = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return home / "lwp"


@dataclass
class ResidueRecord:
    id: str
    kind: str  # lock | phantom | compost | pollen
    key: str  # stable lookup key (e.g. decision name)
    version: int
    body: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    provenance: str = "keeper"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ResidueRecord":
        return cls(
            id=d["id"],
            kind=d["kind"],
            key=d["key"],
            version=d.get("version", 1),
            body=dict(d.get("body", {})),
            created_at=d.get("created_at", 0.0),
            provenance=d.get("provenance", "keeper"),
        )


class SymbioticLedger:
    """Append-only residue ledger. Raises, never silently deletes."""

    def __init__(self, directory: Optional[Path] = None):
        self.dir = Path(directory) if directory else _default_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / LEDGER_FILE

    # -- low-level ------------------------------------------------------
    def _append(self, record: ResidueRecord) -> ResidueRecord:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record

    def _read_all(self) -> List[ResidueRecord]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(ResidueRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue  # corrupt line: skip, keep the ledger readable
        return records

    def _make(
        self, kind: str, key: str, body: Dict[str, Any], version: int = 1
    ) -> ResidueRecord:
        if kind not in _RECORD_TYPES:
            raise ValueError(f"unknown record kind: {kind}")
        if not key or "/" in key or key.startswith("."):
            raise ValueError("unsafe record key")
        return ResidueRecord(
            id=uuid.uuid4().hex[:16],
            kind=kind,
            key=key,
            version=version,
            body=dict(body),
        )

    # -- the four couplings ---------------------------------------------
    def lock(
        self, key: str, decision: str, context: Optional[Dict[str, Any]] = None
    ) -> ResidueRecord:
        """Etch a decision in stone. The newest lock for a key wins reads,
        but older versions are never rewritten."""
        existing = [r for r in self._read_all() if r.kind == "lock" and r.key == key]
        version = max((r.version for r in existing), default=0) + 1
        return self._append(
            self._make(
                "lock",
                key,
                {"decision": decision, "context": dict(context or {})},
                version=version,
            )
        )

    def current(self, key: str) -> Optional[ResidueRecord]:
        """Newest lock for a key, or None."""
        locks = [r for r in self._read_all() if r.kind == "lock" and r.key == key]
        return max(locks, key=lambda r: r.version) if locks else None

    def supersede(self, key: str, new_decision: str, reason: str) -> ResidueRecord:
        """Revise a locked decision. The old text moves to a phantom record
        so the erased version stays queryable as history."""
        old = self.current(key)
        if old is None:
            raise KeyError(f"no locked decision for key: {key}")
        self._append(
            self._make(
                "phantom",
                key,
                {
                    "erased_decision": old.body.get("decision"),
                    "erased_version": old.version,
                    "reason": reason,
                },
                version=old.version,
            )
        )
        return self.lock(
            key, new_decision, {"supersedes": old.version, "reason": reason}
        )

    def phantoms(self, key: str) -> List[ResidueRecord]:
        return [r for r in self._read_all() if r.kind == "phantom" and r.key == key]

    def compost(
        self, key: str, failed_attempt: str, analysis: str, retry_hint: str = ""
    ) -> ResidueRecord:
        """Digest a failure into a correction the growth loop can consume.
        Never stores raw manuscript — analysis and lesson only."""
        return self._append(
            self._make(
                "compost",
                key,
                {
                    "failed_summary": failed_attempt[:500],
                    "analysis": analysis[:2000],
                    "retry_hint": retry_hint[:500],
                    "lesson_kind": "correction",
                },
            )
        )

    def pollen(
        self, key: str, style_fingerprint: Dict[str, Any], peer: str = "local"
    ) -> ResidueRecord:
        """Record a style-fingerprint exchange. Fingerprints are aggregate
        statistics (vocabulary rhythm, sentence-length profile) — numeric
        only, never manuscript text, never exfiltrated."""
        fp = {
            k: v
            for k, v in style_fingerprint.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        return self._append(
            self._make(
                "pollen",
                key,
                {"fingerprint": fp, "peer": peer},
            )
        )

    # -- queries ----------------------------------------------------------
    def history(self, key: str) -> List[ResidueRecord]:
        return [r for r in self._read_all() if r.key == key]

    def by_kind(self, kind: str) -> List[ResidueRecord]:
        if kind not in _RECORD_TYPES:
            raise ValueError(f"unknown record kind: {kind}")
        return [r for r in self._read_all() if r.kind == kind]

    def export_json(self) -> str:
        return json.dumps(
            [r.to_dict() for r in self._read_all()], indent=2, ensure_ascii=False
        )
