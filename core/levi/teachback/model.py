"""Teach-back goal-model engine.

A goal-model statement is:

    {
      "id": str,
      "statement": str,          # what LEVI currently believes
      "confidence": float,       # 0.0 .. 1.0, honestly moved only
      "evidence_count": int,     # corroborations via note_evidence
      "corrections": int,        # times the user corrected it
      "created_at": ISO, "updated_at": ISO,
      "history": [               # append-only, never rewritten
        {"ts": ISO, "kind": "add|correct|affirm|evidence",
         "old": ..., "new": ..., "note": ...},
      ],
    }

Confidence law (honest, mechanical):
* ``correct()`` replaces the statement text and *lowers* confidence
  (0.15 step, floor 0.05) — being corrected means the old model was
  wrong; the corrected text starts with humbler confidence.
* ``affirm()`` *raises* confidence (0.10 step, cap 1.0) — the user
  confirmed the model is right.
* ``note_evidence()`` raises confidence (0.05 step, cap 0.95) and
  increments the corroboration counter — confidence never jumps to
  certainty from evidence alone.
* Nothing else moves confidence. No vibes.

Home resolved at call time from ``LEVI_HOME`` or ``~/.levi``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ENC = "utf-8"
_CORRECT_STEP = 0.15
_AFFIRM_STEP = 0.10
_EVIDENCE_STEP = 0.05
_FLOOR = 0.05


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


class TeachbackModel:
    """Local JSON goal-model with logged corrections."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.home = _resolve_home(home)
        self.root = self.home / "teachback"
        self.root.mkdir(parents=True, exist_ok=True)
        self._path = self.root / "goal_model.json"

    # -- persistence ------------------------------------------------------

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding=ENC))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, statements: Dict[str, Dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(statements, indent=2, sort_keys=True) + "\n", encoding=ENC
        )

    @staticmethod
    def _hist(statement: Dict[str, Any], kind: str, **fields: Any) -> None:
        entry = {"ts": _now_iso(), "kind": kind}
        entry.update(fields)
        statement.setdefault("history", []).append(entry)
        statement["updated_at"] = entry["ts"]

    # -- API --------------------------------------------------------------

    def add_statement(
        self, statement_id: str, statement: str, confidence: float = 0.5
    ) -> Dict[str, Any]:
        """Add a new goal-model statement (used when LEVI forms a belief)."""
        if not statement_id or not statement_id.strip():
            raise ValueError("statement_id must not be empty")
        statements = self._load()
        if statement_id in statements:
            raise ValueError(f"statement {statement_id!r} already exists")
        conf = max(0.0, min(1.0, float(confidence)))
        doc = {
            "id": statement_id,
            "statement": statement,
            "confidence": conf,
            "evidence_count": 0,
            "corrections": 0,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "history": [],
        }
        self._hist(doc, "add", new=statement, confidence=conf)
        statements[statement_id] = doc
        self._save(statements)
        return doc

    def model(self) -> List[Dict[str, Any]]:
        """Current goal-model statements with confidence (honest empty list)."""
        return sorted(self._load().values(), key=lambda d: d["id"])

    def render_brief(self) -> str:
        """Plain-language brief: here is what I believe your goals are."""
        statements = self.model()
        if not statements:
            return (
                "I don't have a model of your goals yet. Tell me one — "
                "what are you actually working toward? — and I'll remember "
                "it here so you can correct me later."
            )
        lines = [
            "Here's what I believe your goals are. Correct me where I'm wrong:",
            "",
        ]
        for s in statements:
            conf = s["confidence"]
            if conf >= 0.8:
                feel = "high"
            elif conf >= 0.5:
                feel = "medium"
            else:
                feel = "low"
            lines.append(f"- [{s['id']}] {s['statement']}")
            lines.append(
                f"  confidence: {feel} ({conf:.2f}) · "
                f"evidence: {s['evidence_count']} · corrections: {s['corrections']}"
            )
        lines.append("")
        lines.append(
            "Reply with what to change and I'll update this — "
            "no judgment, the model just gets better."
        )
        return "\n".join(lines)

    def _get(self, statement_id: str) -> Dict[str, Any]:
        statements = self._load()
        if statement_id not in statements:
            raise KeyError(f"no statement {statement_id!r}")
        return statements, statements[statement_id]

    def correct(self, statement_id: str, correction: str) -> Dict[str, Any]:
        """Apply the user's correction; confidence drops honestly."""
        statements, doc = self._get(statement_id)
        old_stmt = doc["statement"]
        old_conf = doc["confidence"]
        doc["statement"] = correction
        doc["confidence"] = max(_FLOOR, round(old_conf - _CORRECT_STEP, 3))
        doc["corrections"] += 1
        self._hist(
            doc,
            "correct",
            old=old_stmt,
            new=correction,
            note=f"confidence {old_conf:.2f} -> {doc['confidence']:.2f}",
        )
        self._save(statements)
        return doc

    def affirm(self, statement_id: str) -> Dict[str, Any]:
        """User confirms the statement; confidence rises honestly."""
        statements, doc = self._get(statement_id)
        old_conf = doc["confidence"]
        doc["confidence"] = min(1.0, round(old_conf + _AFFIRM_STEP, 3))
        self._hist(
            doc,
            "affirm",
            note=f"confidence {old_conf:.2f} -> {doc['confidence']:.2f}",
        )
        self._save(statements)
        return doc

    def note_evidence(self, statement_id: str, evidence: str) -> Dict[str, Any]:
        """Log corroborating evidence; bumps the counter and confidence a notch."""
        statements, doc = self._get(statement_id)
        old_conf = doc["confidence"]
        doc["evidence_count"] += 1
        doc["confidence"] = min(0.95, round(old_conf + _EVIDENCE_STEP, 3))
        self._hist(
            doc,
            "evidence",
            note=evidence,
            evidence_count=doc["evidence_count"],
            confidence=f"{old_conf:.2f} -> {doc['confidence']:.2f}",
        )
        self._save(statements)
        return doc

    def history(self, statement_id: str) -> List[Dict[str, Any]]:
        """Append-only history of a statement (corrections preserved)."""
        _, doc = self._get(statement_id)
        return list(doc.get("history", []))


# -- module-level convenience wrappers (home resolved at call time) --------


def add_statement(
    statement_id: str, statement: str, confidence: float = 0.5
) -> Dict[str, Any]:
    return TeachbackModel().add_statement(statement_id, statement, confidence)


def model() -> List[Dict[str, Any]]:
    return TeachbackModel().model()


def render_brief() -> str:
    return TeachbackModel().render_brief()


def correct(statement_id: str, correction: str) -> Dict[str, Any]:
    return TeachbackModel().correct(statement_id, correction)


def affirm(statement_id: str) -> Dict[str, Any]:
    return TeachbackModel().affirm(statement_id)


def note_evidence(statement_id: str, evidence: str) -> Dict[str, Any]:
    return TeachbackModel().note_evidence(statement_id, evidence)
