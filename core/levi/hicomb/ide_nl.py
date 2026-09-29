"""Hicomb IDE: NL→IR builder — natural language in, E3–E6 BuildJob out.

Shape follows Chauncey's original alphaEngine
(``workspace/your_files/alpha-cli-recovery/alpha_engine_fragment.py``):
natural-language routing -> route -> build. Here "route" resolves the
intent into an E3–E6 tiered build plan and "build" runs the
EmergencyBuilder under its tier gates. The E3–E6 plan (BuildJob) IS the
IR — the intermediate representation between NL and code. This module
wires through the KFX²'d core (``levi.alpha.build`` +
``levi.builder.emergency``) and never reinvents it.

LAWS (declared up front, machine-checked in tests/test_hicomb_ide_nl.py):
  N1 ORIGINAL-FORMS  parse honors the fragment's command forms
      ("build engine|module|service <name>", "build <x>").
  N2 IR-IS-JOB      The IR is the BuildJob dict — intent, kind, name,
      goal, tier, stage, plan steps. No second IR is invented here.
  N3 TIER-GATES     E5/E6 apply refuses without an approved HITL request
      (fail-closed, inherited from emergency.py). The refusal is proved.
  N4 NO-SILENT-COERCE  Empty intents and unknown tiers raise ValueError —
      never coerced, never guessed.
  N5 LEARN          Quetta Pan drives the loop's learning: IR misses
      (empty intent, unknown tier, refused apply, build exceptions) are
      absorbed as failure outcomes by the reim-compost stage; the
      riem-genome stage is consulted before the next plan and steers
      the route — a suppressed route is flagged in the receipt, never
      dropped silently. REIM/RIEM are stages inside Quetta Pan, not
      separate calls.
  N6 OFFLINE        stdlib only. No network imports, no model, no keys,
      no egress. Intent routing is deterministic rules and says so.

Snapshot-every-stage (Chauncey, 2026-09-23): plan_intent and apply_job
wrap their acting calls in pre/post snapshots from
``levi.hicomb.snapshots`` (S1–S5) — snapshot before the NL→IR plan
executes, snapshot before the apply executes.

The IDE store (default ``~/.levi/hicomb/ide/``): ``.ide_ir_compost.jsonl``
(IR misses), ``.ide_ir_genome.json`` (route steering), ``ide_receipts.jsonl``.
Tests pass an isolated store_dir and stay hermetic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.hicomb.qp_compat import (
    QuettaPanLoop,
    QuettaPanUnavailable,
    require_quetta_loop,
)
from levi.hicomb.snapshots import SnapshotStore, snapshotted

# ------------------------------------------------------------------ stores
DEFAULT_IDE_STORE = Path.home() / ".levi" / "hicomb" / "ide"


def _store(store_dir: Optional[Path | str]) -> Path:
    p = Path(store_dir) if store_dir else DEFAULT_IDE_STORE
    p.mkdir(parents=True, exist_ok=True)
    return p


def _snapshots(store_dir: Optional[Path | str]) -> SnapshotStore:
    """Per-stage snapshot store for the NL→IR arm (S1)."""
    return SnapshotStore(_store(store_dir) / ".snapshots")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------------ receipts
@dataclass
class IdeReceipt:
    ts: str
    action: str  # parse | plan | apply | ir_miss
    intent: str = ""
    detail: str = ""
    ok: bool = True
    job_id: str = ""
    genome: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "action": self.action,
            "intent": self.intent,
            "detail": self.detail,
            "ok": self.ok,
            "job_id": self.job_id,
            "genome": self.genome,
        }


class IdeJournal:
    """Append-only receipt log. Nothing silent, nothing rewritten."""

    def __init__(self, store_dir: Optional[Path | str] = None):
        self.store_dir = _store(store_dir)
        self.path = self.store_dir / "ide_receipts.jsonl"

    def log(self, receipt: IdeReceipt) -> IdeReceipt:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.as_dict(), ensure_ascii=False) + "\n")
        return receipt

    def read(self) -> List[Dict[str, Any]]:
        out = []
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        return out


# ------------------------------------------------------------------ NL→IR
def _ide_qp(store_dir: Optional[Path | str]) -> QuettaPanLoop:
    """Quetta Pan driving the IDE loop's learning. REIM/RIEM are stages
    inside it — nothing here touches them directly (Q1). Guarded: the
    sibling's quetta_loop may be absent on a fresh checkout."""
    return require_quetta_loop()(
        _store(store_dir),
        compost_name=".ide_ir_compost.jsonl",
        genome_name=".ide_ir_genome.json",
        receipts_name=".ide_ir_qp_receipts.jsonl",
    )


def record_ir_miss(
    intent: str, reason: str, store_dir: Optional[Path | str] = None
) -> Dict[str, Any]:
    """Compost an IR miss as a Quetta Pan failure outcome (N5, Q3).
    Never drops silently.

    Best-effort by design: it runs on exception paths whose primary
    contract (e.g. ValueError on empty intent, N4) must hold with or
    without the sibling's loop. If the loop is absent, the miss is
    journaled instead of composted — still never silent.
    """
    try:
        qp = _ide_qp(store_dir)
    except QuettaPanUnavailable:
        return IdeJournal(store_dir).log(
            IdeReceipt(ts=_now(), action="ir_miss",
                       intent=str(intent)[:120],
                       detail=f"{reason[:200]} (loop unavailable — journaled)",
                       ok=False)
        ).as_dict()
    return qp.absorb_outcome(
        "failure",
        rule_id="nl_intent",
        context="nl",
        file="ide_nl",
        tried_what=f"parse/plan intent: {str(intent)[:120]}",
        failed_why=reason,
    )


def parse_intent(
    text: str, store_dir: Optional[Path | str] = None
) -> Dict[str, str]:
    """Parse NL build intent into a routing dict (N1, N4).

    Empty intent raises ValueError — and the miss is composted (N5).
    """
    from levi.alpha.build import parse_build_intent

    try:
        parsed = parse_build_intent(text)
    except ValueError as exc:
        record_ir_miss(text, f"empty intent: {exc}", store_dir)
        raise
    IdeJournal(store_dir).log(
        IdeReceipt(
            ts=_now(), action="parse", intent=str(text)[:120],
            detail=f"kind={parsed['kind']} name={parsed['name'] or '—'}",
        )
    )
    return parsed


def steer_route(
    kind: str, tier: str, store_dir: Optional[Path | str] = None
) -> Dict[str, str]:
    """Consult Quetta Pan's genome stage before planning (N5, Q1).

    Returns {"verdict", "reason"}. A "suppress" verdict flags the route
    in the plan receipt — the plan is still produced (plan-first), but
    the builder sees the warning.
    """
    qp = _ide_qp(store_dir)
    rule_id = f"nl_route:{kind}:{tier}"
    steered = qp.steer(rule_id, "nl")
    return {"rule_id": rule_id, "verdict": steered["verdict"],
            "reason": steered["reason"]}


def plan_intent(
    text: str,
    tier: str = "E4",
    target: str = "independent",
    name: Optional[str] = None,
    workspace: Optional[Path] = None,
    store_dir: Optional[Path | str] = None,
):
    """NL text → E3–E6 plan. Returns the BuildJob (N2).

    Unknown tier raises (N4) and the miss is composted (N5).
    """
    from levi.alpha.build import plan_build

    parsed = parse_intent(text, store_dir)
    steer = steer_route(parsed["kind"], tier.strip().upper(), store_dir)
    # S1: snapshot before the NL→IR plan executes — the plan can roll
    # back to this pre-snapshot on failure.
    snaps = _snapshots(store_dir)
    pre_payload = {
        "intent": str(text)[:500], "kind": parsed.get("kind"),
        "tier": tier, "target": target, "name": name,
        "steer": steer.get("reason", ""),
    }
    try:
        job, _pre, _post = snapshotted(
            snaps, "nlir-plan", pre_payload,
            plan_build,
            text, tier=tier, target=target, name=name, workspace=workspace,
            post=lambda j: {"job_id": j.id, "tier": j.tier,
                            "status": j.status,
                            "steps": len(j.plan_steps)},
        )
    except ValueError as exc:
        record_ir_miss(text, f"plan failed: {exc}", store_dir)
        raise
    IdeJournal(store_dir).log(
        IdeReceipt(
            ts=_now(), action="plan", intent=str(text)[:120],
            detail=f"job={job.id} tier={job.tier} status={job.status}",
            job_id=job.id, genome=f"{steer['rule_id']}={steer['verdict']}",
        )
    )
    # Attach the genome steer to the job object for the receipt surface.
    job.plan_steps = list(job.plan_steps) + [f"IDE steer: {steer['reason']}"]
    return job


def ir_of(job: Any) -> Dict[str, Any]:
    """The IR as a JSON-able dict (N2)."""
    return job.to_dict()


def apply_job(
    job_id: str,
    workspace: Optional[Path] = None,
    force: bool = False,
    store_dir: Optional[Path | str] = None,
) -> str:
    """Apply a planned job under the E3–E6 tier gates (N3).

    A refused apply (HITL not approved) is composted as an IR miss (N5);
    a successful apply folds a success into the genome per tier.
    Returns the human-readable report.
    """
    from levi.alpha.build import apply_build

    # S1: snapshot before the apply executes — the pre-snapshot is the
    # rollback point if the apply half-finishes or is refused.
    snaps = _snapshots(store_dir)
    pre_payload = {"job_id": job_id, "force": force,
                   "workspace": str(workspace) if workspace else ""}
    report, _pre, _post = snapshotted(
        snaps, "nlir-apply", pre_payload,
        apply_build, job_id, workspace=workspace, force=force,
        post=lambda r: {"report_head": str(r)[:200]},
    )
    journal = IdeJournal(store_dir)
    qp = _ide_qp(store_dir)
    refused = any(
        sig in report
        for sig in (
            "HITL not approved",
            "refusing to apply",
            "HITL still pending",
            "HITL check failed",
        )
    )
    if refused:
        record_ir_miss(job_id, f"apply refused: {report[:120]}", store_dir)
        journal.log(
            IdeReceipt(ts=_now(), action="apply", intent=job_id,
                       detail=f"refused: {report[:120]}", ok=False,
                       job_id=job_id)
        )
    elif report.startswith("No job"):
        journal.log(
            IdeReceipt(ts=_now(), action="apply", intent=job_id,
                       detail=report[:120], ok=False, job_id=job_id)
        )
    else:
        tier = "E4"
        for t in ("E3", "E4", "E5", "E6"):
            if f"({t})" in report:
                tier = t
                break
        qp.learn(f"apply:{tier}", "plan", True,
                 f"ide applied job {job_id}")
        journal.log(
            IdeReceipt(ts=_now(), action="apply", intent=job_id,
                       detail="applied", job_id=job_id,
                       genome=f"apply:{tier}=boost")
        )
    return report


def intent_source() -> Dict[str, str]:
    """Honest-source label for the NL surface (N6).

    Intent routing is deterministic rules — there is no model to seat
    here, and this says so plainly.
    """
    return {
        "source": "rules",
        "note": "NL intent routing is deterministic rules "
                "(alphaEngine command forms); no model seated, none needed.",
    }


__all__ = [
    "DEFAULT_IDE_STORE",
    "IdeJournal",
    "IdeReceipt",
    "apply_job",
    "intent_source",
    "ir_of",
    "parse_intent",
    "plan_intent",
    "record_ir_miss",
    "steer_route",
]
