"""Hicomb IDE: the forge arm — Pollen -> Elite Surgeon -> Quetta Pan learn.

The refine/repair/learn loop over generated and edited code:
Pollen formats (refine), the Elite Surgeon diagnoses and repairs
(multi-pass, syntax-gated), Quetta Pan's advisory refine pass surfaces
suggestions, and Quetta Pan drives the learning: every failure is
absorbed by the reim-compost stage while every outcome folds into the
riem-genome stage — the genome steers the next fix.

LAWS (declared up front, machine-checked in tests/test_hicomb_forge.py):
  F1 POLLEN-FIRST   Repair never runs on unformatted text. A formatter
      failure aborts the whole forge and the input text is returned
      unchanged (in-memory byte-identical).
  F2 ROLLBACK       A surgeon pass that breaks parsing is rolled back;
      the pass is composted as a parse-class failure, never kept.
  F3 GENOME-STEERS  The genome is consulted before each fix bundle; a
      bundle containing a suppressed rule is withheld with its reason,
      never applied.
  F4 NO-SILENT      Every fix, withheld bundle, refusal, suggestion, and
      learning outcome is receipted. Nothing dropped silently.
  F5 OFFLINE        stdlib only. No network imports, no model, no egress.

Snapshot-every-stage (Chauncey, 2026-09-23): forge_text runs its acting
stages — pollen-format and surgeon-edit — under pre/post snapshots from
``levi.hicomb.snapshots`` (S1–S5). A repair pass applied without its
pre-snapshot raises StageViolation, build-breaking (S4).

Stores (default ``~/.levi/hicomb/ide/``): ``.forge_compost.jsonl``,
``.forge_genome.json`` — the same REIM/RIEM mechanism as the rest of the
IDE, scoped to the forge. Tests pass an isolated store_dir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.hicomb.ide_nl import DEFAULT_IDE_STORE
from levi.hicomb.pollen import FormatterError, format_text
from levi.hicomb.quetta_loop import QuettaPanLoop
from levi.hicomb.snapshots import SnapshotStore, StageGuard, snapshotted
from levi.quetta_pan.riem import context_key_for
from levi.surgeon.elite import cleanup_pass, syntax_error
from levi.uniforge.surgeon import quick_cleanup

# ------------------------------------------------------------------ fix rules
# Fix descriptions (elite) / fix counters (uniforge) -> stable rule ids
# the genome learns per rule, per context.
RULE_WS = "FORGE_WS"
RULE_TABS = "FORGE_TABS"
RULE_BLANKS = "FORGE_BLANKS"
RULE_NONE_CMP = "FORGE_NONE_CMP"
RULE_AUG_ASSIGN = "FORGE_AUG_ASSIGN"
RULE_MISSING_COLON = "FORGE_MISSING_COLON"

_UNIFORGE_RULE = {
    "trailing_whitespace": RULE_WS,
    "tabs": RULE_TABS,
    "blank_lines": RULE_BLANKS,
    "eq_none": RULE_NONE_CMP,
    "ne_none": RULE_NONE_CMP,
}


def _elite_fix_rule_ids(fix_descriptions: List[str]) -> List[str]:
    """Map elite's free-text fix descriptions to stable rule ids."""
    ids: List[str] = []
    for desc in fix_descriptions:
        if desc == "whitespace normalization":
            ids.append(RULE_WS)
        elif desc == "tabs -> 4 spaces":
            ids.append(RULE_TABS)
        elif desc == "collapsed excessive blank lines":
            ids.append(RULE_BLANKS)
        elif desc == "None comparison style":
            ids.append(RULE_NONE_CMP)
        elif desc == "augmented assignment":
            ids.append(RULE_AUG_ASSIGN)
        elif desc.startswith("added colon:"):
            ids.append(RULE_MISSING_COLON)
        # Unknown descriptions are receipted but not genome-tracked.
    seen = list(dict.fromkeys(ids))
    return seen


@dataclass
class ForgeResult:
    ok: bool
    text: str  # forged text (== input when not ok)
    language: str
    formatted: bool = False  # pollen changed the text
    repaired: bool = False  # surgeon changed the text
    fixes_applied: List[str] = field(default_factory=list)
    withheld: List[Dict[str, str]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    composted: int = 0
    aborted: str = ""
    receipts: List[Dict[str, Any]] = field(default_factory=list)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ForgeArm:
    """Pollen -> Elite Surgeon -> Quetta Pan learn, in memory."""

    def __init__(self, store_dir: Optional[Path | str] = None):
        self.store_dir = (
            Path(store_dir) if store_dir else DEFAULT_IDE_STORE
        )
        self.store_dir.mkdir(parents=True, exist_ok=True)
        # Quetta Pan drives the forge's learning; REIM/RIEM are stages
        # inside it — nothing here touches them directly (Q1).
        self.qp = QuettaPanLoop(
            self.store_dir,
            compost_name=".forge_compost.jsonl",
            genome_name=".forge_genome.json",
            receipts_name=".forge_qp_receipts.jsonl",
        )
        # Snapshot-every-stage (S1): every acting stage in forge_text
        # runs under pre/post snapshots from this store.
        self._snapshots = SnapshotStore(self.store_dir / ".snapshots")
        self._guard = StageGuard(self._snapshots)

    # ---- learning ----------------------------------------------------
    def _compost_failure(
        self,
        rule_id: str,
        path_hint: str,
        context: str,
        tried_what: str,
        failed_why: str,
    ) -> Dict[str, Any]:
        return self.qp.absorb_outcome(
            "failure", rule_id=rule_id, context=context, file=path_hint,
            tried_what=tried_what, failed_why=failed_why,
        )

    def _learn(self, rule_ids: List[str], context: str, success: bool,
               note: str) -> None:
        for rid in dict.fromkeys(rule_ids):
            self.qp.learn(rid, context, success, note)

    # ---- the forge ----------------------------------------------------
    def forge_text(
        self,
        text: str,
        language: str,
        path_hint: str = "buffer",
        max_passes: int = 25,
    ) -> ForgeResult:
        """Run the forge arm over in-memory text. Never writes to disk."""
        receipts: List[Dict[str, Any]] = []

        def note(action: str, detail: str, ok: bool = True) -> None:
            receipts.append(
                {"ts": _now(), "action": action, "detail": detail, "ok": ok}
            )

        composted = 0
        context = context_key_for(path_hint)

        # F1/S1: Pollen first, under snapshot. The pre-snapshot holds the
        # raw input; a formatter refusal aborts and the input is
        # returned unchanged — the pre-snapshot stays as the audit point.
        try:
            formatted, _pre, _post = snapshotted(
                self._snapshots, "pollen-format",
                {"language": language, "path_hint": path_hint,
                 "before": text},
                format_text, language, text,
                post=lambda r: {"after": r, "changed": r != text},
            )
        except FormatterError as exc:
            self._compost_failure(
                "POLLEN_FORMAT", path_hint, context,
                "pollen format before repair", f"formatter refused: {exc}",
            )
            composted += 1
            note("pollen", f"refused: {exc}", ok=False)
            return ForgeResult(
                ok=False, text=text, language=language,
                aborted=f"pollen refused: {exc}", composted=composted,
                receipts=receipts,
            )
        pollen_changed = formatted != text
        note("pollen", "formatted" if pollen_changed else "already clean")
        src = formatted

        # S1: Surgeon repair runs as one guarded stage. The pre-snapshot
        # holds the pollen-formatted text; every applied pass goes
        # through run.act() — a pass applied without the pre-snapshot
        # is a build-breaking StageViolation (S4).
        run = self._guard.begin(
            "surgeon-edit",
            {"language": language, "path_hint": path_hint,
             "before": src},
        )
        fixes_applied: List[str] = []
        withheld: List[Dict[str, str]] = []
        repaired = False

        if language == "python":
            for _ in range(max_passes):
                new_src, fixes = cleanup_pass(src)
                if not fixes:
                    break
                rule_ids = _elite_fix_rule_ids(fixes)
                bundle = "+".join(rule_ids) if rule_ids else "NO_RULE"
                # F3: genome consulted before the bundle.
                steered = {rid: self.qp.steer(rid, context)
                           for rid in rule_ids}
                suppressed = [rid for rid, s in steered.items()
                              if s["verdict"] == "suppress"]
                if suppressed:
                    reason = steered[suppressed[0]]["reason"]
                    withheld.append(
                        {"bundle": bundle, "rules": ",".join(suppressed),
                         "reason": reason})
                    note("surgeon", f"withheld bundle {bundle}: {reason}",
                         ok=False)
                    break
                if syntax_error(new_src, path_hint) is not None:
                    # F2: the pass broke parsing — roll back, compost, stop.
                    self._compost_failure(
                        bundle, path_hint, context,
                        f"elite pass ({'; '.join(fixes)})",
                        f"parse: pass broke syntax: "
                        f"{syntax_error(new_src, path_hint)}",
                    )
                    composted += 1
                    self._learn(rule_ids, context, False,
                                f"forge: pass broke parsing on {path_hint}")
                    note("surgeon",
                         f"pass broke parsing — rolled back ({bundle})",
                         ok=False)
                    break
                run.act()  # S4: the pass applies only under the pre-snapshot
                src = new_src
                repaired = True
                fixes_applied.extend(
                    r for r in rule_ids if r not in fixes_applied)
                self._learn(rule_ids, context, True,
                            f"forge: elite pass clean on {path_hint}")
                note("surgeon", f"pass ok: {bundle}")
        else:
            cleaned, counts = quick_cleanup(src)
            rule_ids = list(dict.fromkeys(
                _UNIFORGE_RULE[k] for k, v in counts.items() if v))
            if rule_ids:
                bundle = "+".join(rule_ids)
                steered = {rid: self.qp.steer(rid, context)
                           for rid in rule_ids}
                suppressed = [rid for rid, s in steered.items()
                              if s["verdict"] == "suppress"]
                if suppressed:
                    reason = steered[suppressed[0]]["reason"]
                    withheld.append(
                        {"bundle": bundle, "rules": ",".join(suppressed),
                         "reason": reason})
                    note("surgeon", f"withheld bundle {bundle}: {reason}",
                         ok=False)
                else:
                    run.act()  # S4: applies only under the pre-snapshot
                    src = cleaned
                    repaired = True
                    fixes_applied.extend(rule_ids)
                    self._learn(rule_ids, context, True,
                                f"forge: quick cleanup on {path_hint}")
                    note("surgeon", f"quick cleanup ok: {bundle}")
            else:
                note("surgeon", "nothing to repair")

        run.end({"after": src, "fixes_applied": fixes_applied,
                 "withheld": withheld, "repaired": repaired,
                 "composted": composted})

        # Quetta Pan advisory refine — suggestions surface, never auto-apply.
        suggestions: List[Dict[str, Any]] = []
        try:
            from levi.hicomb.quetta_refine import QuettaRefiner

            refiner = QuettaRefiner(store_dir=self.store_dir / "quetta")
            report = refiner.review(src, language, path_hint)
            suggestions = [
                {"id": s["id"], "title": s["title"],
                 "severity": s["severity"],
                 "genome": s.get("genome", "unknown")}
                for s in report.suggestions
            ]
            for s in report.suppressed:
                suggestions.append(
                    {"id": s["id"], "title": s["title"],
                     "severity": s["severity"], "genome": "suppressed",
                     "reason": s.get("suppressed_reason", "")})
            note("quetta",
                 f"advisory: {len(report.suggestions)} suggestion(s), "
                 f"{len(report.suppressed)} suppressed-by-genome")
        except Exception as exc:  # advisory must never break the forge
            note("quetta", f"advisory pass skipped: {exc}", ok=False)

        # F4: every receipt rides along.
        return ForgeResult(
            ok=True, text=src, language=language,
            formatted=pollen_changed, repaired=repaired,
            fixes_applied=fixes_applied, withheld=withheld,
            suggestions=suggestions, composted=composted,
            receipts=receipts,
        )


__all__ = [
    "ForgeArm",
    "ForgeResult",
    "RULE_AUG_ASSIGN",
    "RULE_BLANKS",
    "RULE_MISSING_COLON",
    "RULE_NONE_CMP",
    "RULE_TABS",
    "RULE_WS",
]
