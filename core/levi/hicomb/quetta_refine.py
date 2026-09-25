"""Quetta-Pan refinement pass for Pollen's save pipeline.

Pipeline shape: format -> refine -> re-validate -> write-or-abort.

LAWS (declared up front, machine-checked in tests/test_hicomb_quetta_refine.py):
  Q1 GATE-STANDS   The Pollen abort gate (I1 POLLEN-ABORT) covers the refine
                   pass too: any failure in the refine stage aborts the
                   write and the target file stays byte-identical.
  Q2 ADVISORY      Refine suggestions are advisory. They apply only when
                   the builder's confirm callback says yes; without a
                   callback they are receipted and dropped. Nothing is ever
                   silently rewritten (extends I3 SAFE-ONLY).
  Q3 DETERMINISTIC Same text + same genome state = same report. Two
                   review() calls are identical modulo timestamps; proved
                   in tests with isolated stores.
  Q4 OFFLINE       No network calls in the refine path — quetta_pan is
                   stdlib-only; a grep-gate test bans network library
                   imports in this module and its quetta_pan dependencies.
  Q5 NO-SILENT-DELETE Agent-refined text re-runs Pollen's safety gates
                   (format_text + idempotency) before the write. Anything
                   the gates reject aborts the save like a pollen refusal.

WIRING (honest, verified 2026-09-23):
  WIRED: QuettaPanEngine.suggest_upgrades() — the real heuristic rules
      (PY_*/TS_*), the real safe fixes, the RIEM genome consulted BEFORE
      generation, and suppressed rules withheld with stated reasons
      (REIM compost failures folded into the genome via learn()).
  WIRED: RiemGenome.learn/consult — refine outcomes (confirmed/declined)
      are learned per rule+context, so the loop improves with editor use.
  BUILT-HERE: in-memory review staging — QuettaPanEngine works on files,
      so this module stages buffer text into a temp file inside an
      isolated project dir (genome/compost/history persist in the
      configured store dir), runs suggest_upgrades(), and reads
      new_content back. No engine internals were copied or reimplemented.
  MISSING: none for this build. The refine pass needs no network
      providers and no model backend.

Stdlib only. Deterministic modulo genome state (documented in Q3).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from levi.quetta_pan import (
    QuettaPanEngine,
    RiemGenome,
    context_key_for,
)

# Quetta-Pan's heuristics only cover these suffixes; every other Pollen
# language gets an honest "unsupported-language" receipt, never a fake pass.
SUFFIX_BY_LANGUAGE = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
}

DEFAULT_STORE_DIR = Path.home() / ".levi" / "hicomb" / "quetta_store"
DEFAULT_LOG_PATH = Path.home() / ".levi" / "hicomb" / "quetta_refine.jsonl"

INSTANCE_ID = "quetta-pan/pollen-refiner"

DECISIONS = ("confirmed", "declined", "advisory", "no-changes", "unsupported-language")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RefineReceipt:
    """One receipt per rule per pass. Append-only; nothing silent."""

    ts: str
    instance: str  # INSTANCE_ID — which refiner ran this pass
    language: str
    path: str
    rule_id: str
    title: str
    severity: str
    decision: str  # one of DECISIONS
    applied: bool
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "instance": self.instance,
            "language": self.language,
            "path": self.path,
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "decision": self.decision,
            "applied": self.applied,
            "note": self.note,
        }


@dataclass
class RefineReport:
    """What review() found. new_content is a proposal until decide()."""

    language: str
    path: str
    has_changes: bool
    suggestions: list = field(default_factory=list)  # engine suggestion dicts
    suppressed: list = field(default_factory=list)  # genome-withheld, with reasons
    fix_ids: list = field(default_factory=list)
    new_content: str | None = None  # proposed refined text (None until decided)
    receipts: list = field(default_factory=list)  # RefineReceipt, advisory until decide()


class QuettaRefiner:
    """Advisory Quetta-Pan refine pass over Pollen-formatted text."""

    def __init__(
        self,
        store_dir: str | Path | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        self.store_dir = Path(store_dir) if store_dir else DEFAULT_STORE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        self.genome = RiemGenome(self.store_dir / ".quetta_genome.json")

    # ---- review ------------------------------------------------------

    def review(
        self, text: str, language: str, path_hint: str = "buffer"
    ) -> RefineReport:
        """Run the real Quetta-Pan suggestion pass over in-memory text.

        Advisory: the report proposes; decide() disposes. Deterministic
        modulo genome state (Q3) — same text + same store = same report.
        """
        suffix = SUFFIX_BY_LANGUAGE.get(language)
        if suffix is None:
            receipt = RefineReceipt(
                ts=_utcnow(),
                instance=INSTANCE_ID,
                language=language,
                path=path_hint,
                rule_id="NO_RULE",
                title="no quetta-pan rules for this language",
                severity="info",
                decision="unsupported-language",
                applied=False,
                note=f"engine covers {sorted(SUFFIX_BY_LANGUAGE)} only",
            )
            return RefineReport(
                language=language,
                path=path_hint,
                has_changes=False,
                receipts=[receipt],
            )

        # Stage the buffer text as a real file so the engine's file-based
        # suggestion path runs unmodified (BUILT-HERE staging, WIRED engine).
        with tempfile.TemporaryDirectory(prefix="pollen-refine-") as tmp:
            staged = Path(tmp) / f"refine{suffix}"
            staged.write_text(text, encoding="utf-8")
            engine = QuettaPanEngine(project_root=tmp, store_dir=self.store_dir)
            suggestion = engine.suggest_upgrades(staged)

        receipts: list[RefineReceipt] = []
        for s in suggestion["suggestions"]:
            receipts.append(
                RefineReceipt(
                    ts=_utcnow(),
                    instance=INSTANCE_ID,
                    language=language,
                    path=path_hint,
                    rule_id=s["id"],
                    title=s["title"],
                    severity=s["severity"],
                    decision="advisory",
                    applied=False,
                    note=f"genome: {s.get('genome', 'unknown')}",
                )
            )
        for s in suggestion["suppressed_by_genome"]:
            receipts.append(
                RefineReceipt(
                    ts=_utcnow(),
                    instance=INSTANCE_ID,
                    language=language,
                    path=path_hint,
                    rule_id=s["id"],
                    title=s["title"],
                    severity=s["severity"],
                    decision="advisory",
                    applied=False,
                    note=s.get("suppressed_reason", "withheld by genome"),
                )
            )

        has_changes = bool(suggestion.get("has_changes"))
        return RefineReport(
            language=language,
            path=path_hint,
            has_changes=has_changes,
            suggestions=suggestion["suggestions"],
            suppressed=suggestion["suppressed_by_genome"],
            fix_ids=suggestion.get("fix_ids", []),
            new_content=suggestion["new_content"] if has_changes else None,
            receipts=receipts,
        )

    # ---- decide ------------------------------------------------------

    def decide(
        self, report: RefineReport, decision: str
    ) -> tuple[str | None, list[RefineReceipt]]:
        """Apply the builder's verdict. Returns (final_text_or_None, receipts).

        - "confirmed": learn success per rule, mark applied, return the
          proposed text.
        - "declined": learn failure per rule (the loop improves), keep the
          original text.
        - "advisory": no learning (silence is not a verdict), keep text.
        Q2: only "confirmed" ever changes the text.
        """
        if decision not in ("confirmed", "declined", "advisory"):
            raise ValueError(f"bad refine decision: {decision!r}")
        suffix = SUFFIX_BY_LANGUAGE.get(report.language, "")
        context = context_key_for(f"refine{suffix}" if suffix else "refine")

        if decision == "confirmed" and report.has_changes:
            for s in report.suggestions:
                self.genome.learn(
                    s["id"],
                    context,
                    True,
                    f"pollen-refine confirmed on {report.path}",
                )
            suggested_ids = {s["id"] for s in report.suggestions}
            receipts = [
                RefineReceipt(
                    ts=r.ts,
                    instance=r.instance,
                    language=r.language,
                    path=r.path,
                    rule_id=r.rule_id,
                    title=r.title,
                    severity=r.severity,
                    decision="confirmed" if r.rule_id in suggested_ids else r.decision,
                    applied=r.rule_id in suggested_ids,
                    note=r.note,
                )
                for r in report.receipts
            ]
            return report.new_content, receipts

        if decision == "declined":
            for s in report.suggestions:
                self.genome.learn(
                    s["id"],
                    context,
                    False,
                    f"pollen-refine declined in editor on {report.path}",
                )
        receipts = [
            RefineReceipt(
                ts=r.ts,
                instance=r.instance,
                language=r.language,
                path=r.path,
                rule_id=r.rule_id,
                title=r.title,
                severity=r.severity,
                decision=decision if r.decision == "advisory" else r.decision,
                applied=False,
                note=r.note,
            )
            for r in report.receipts
        ]
        return None, receipts  # None = keep the pre-refine text

    # ---- receipts ----------------------------------------------------

    def log_receipts(self, receipts: list[RefineReceipt]) -> None:
        """Append-only receipt log. Nothing silent, nothing rewritten."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            for r in receipts:
                fh.write(json.dumps(r.as_dict(), ensure_ascii=False) + "\n")


ConfirmFn = Callable[[RefineReport], bool]
