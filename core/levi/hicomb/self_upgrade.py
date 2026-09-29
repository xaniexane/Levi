"""Hicomb IDE: self-upgrade loop — projections, per-path HITL, denied-path store.

Quetta Pan drives the loop: its forward-projection stage generates
projected upgrade paths for the IDE itself, each carrying its projected
outcome. Chauncey approves or denies each path independently; nothing
projected applies without an explicit approval. The reim-compost stage
absorbs every approval and denial as an outcome; the riem-genome stage
steers the next projection. Denied paths are never deleted — they live
in the denied-path store as remixable material, and every recombination
of two denied paths records its remix lineage (a parts library with
provenance, not a blacklist).

Naming note (standing): this mechanism reads as a REIM/RIEM-variant —
same family, refined, a different angle (recombination of denied paths
rather than composting failures). The name is Chauncey's to birth, so
identifiers stay neutral here: denied-path store, remix lineage,
projection recombination.

LAWS (declared up front, machine-checked in tests/test_hicomb_self_upgrade.py):
  U1 NO-PROJECTION-APPLIES  no projection applies without an explicit
      approved decision. Proposed, denied, or undecided all refuse.
  U2 RECEIPTED              every decision (approve/deny) gets a
      timestamped receipt that includes the projected outcome.
  U3 DENIALS-PERSIST        denials keep id, denied time, reason,
      projected outcome, and their remix descendants. Nothing rejected
      is deleted.
  U4 REMIX-LINEAGE          every recombination records the parent
      denied-path ids in remix_lineage, and registers the child on
      each parent's descendants.
  U5 PROJECTED-OUTCOMES     every projection surfaces its projected
      outcome; nothing lands silently.
  U6 OFFLINE                stdlib only. No network imports, no egress.
  U7 SANDBOX-TESTED         every projected path is executed + tested in
      the sandbox before the checkpoint; the tested outcome is shown
      next to the simulated one. Approvals require sandbox_ok=True —
      untested or failed paths are not approvable. Failed paths are
      reported failed; deny routes them to the remix store.

Snapshot-every-stage (Chauncey, 2026-09-23): propose, decide, remix,
and apply each run under pre/post snapshots from
``levi.hicomb.snapshots`` (S1–S5). Any of them acting without its
pre-snapshot raises StageViolation, build-breaking (S4).

Store (default ``~/.levi/hicomb/ide/``): ``.self_upgrade/`` with
``proposals.json``, ``denied_paths.json`` and ``receipts.jsonl``.
Tests pass an isolated store_dir.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.hicomb.ide_nl import DEFAULT_IDE_STORE
from levi.hicomb.qp_compat import require_quetta_loop
from levi.hicomb.sandbox_test import test_projection, tested_outcome_text
from levi.hicomb.snapshots import SnapshotStore, StageGuard

PROPOSED = "proposed"
APPROVED = "approved"
DENIED = "denied"

SOURCE_RIEM = "riem"
SOURCE_DENIED_REMIX = "denied-remix"
SOURCE_OPERATOR = "operator"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pid() -> str:
    return uuid.uuid4().hex[:8]


# ------------------------------------------------------------------ projections
@dataclass
class UpgradeProjection:
    id: str
    title: str
    change: Dict[str, Any]  # what this path would do
    projected_outcome: str  # the projected outcome, surfaced up front (U5)
    source: str  # riem | denied-remix | operator
    remix_lineage: List[str] = field(default_factory=list)  # U4
    status: str = PROPOSED
    created_ts: str = ""
    decided_ts: str = ""
    riem_advice: str = "unknown"  # genome consultation recorded at proposal
    tested_outcome: str = ""  # sandbox-tested outcome (U7); "" = not run
    sandbox_ok: Optional[bool] = None  # None = not run yet

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "change": self.change,
            "projected_outcome": self.projected_outcome,
            "source": self.source, "remix_lineage": self.remix_lineage,
            "status": self.status, "created_ts": self.created_ts,
            "decided_ts": self.decided_ts, "riem_advice": self.riem_advice,
            "tested_outcome": self.tested_outcome,
            "sandbox_ok": self.sandbox_ok,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UpgradeProjection":
        return cls(
            id=d["id"], title=d["title"], change=d.get("change", {}),
            projected_outcome=d.get("projected_outcome", ""),
            source=d.get("source", SOURCE_OPERATOR),
            remix_lineage=list(d.get("remix_lineage", [])),
            status=d.get("status", PROPOSED),
            created_ts=d.get("created_ts", ""),
            decided_ts=d.get("decided_ts", ""),
            riem_advice=d.get("riem_advice", "unknown"),
            tested_outcome=d.get("tested_outcome", ""),
            sandbox_ok=d.get("sandbox_ok"),
        )


# ------------------------------------------------------------------ denied paths
@dataclass
class DeniedPath:
    id: str
    title: str
    denied_ts: str
    reason: str
    projected_outcome: str  # the outcome it projected, kept with the record
    change_summary: str
    remix_lineage: List[str] = field(default_factory=list)
    remix_descendants: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "denied_ts": self.denied_ts,
            "reason": self.reason,
            "projected_outcome": self.projected_outcome,
            "change_summary": self.change_summary,
            "remix_lineage": self.remix_lineage,
            "remix_descendants": self.remix_descendants,
        }


class DeniedPathStore:
    """The denied-path store: every rejection persists, retrievable, remixable."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.denied: Dict[str, DeniedPath] = {
                d["id"]: DeniedPath(
                    id=d["id"], title=d["title"], denied_ts=d["denied_ts"],
                    reason=d["reason"],
                    projected_outcome=d["projected_outcome"],
                    change_summary=d.get("change_summary", ""),
                    remix_lineage=list(d.get("remix_lineage", [])),
                    remix_descendants=list(
                        d.get("remix_descendants", [])),
                )
                for d in json.loads(
                    self.path.read_text(encoding="utf-8")).values()
            }
        else:
            self.denied = {}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps({k: v.as_dict() for k, v in self.denied.items()},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def record(self, projection: UpgradeProjection, reason: str) -> DeniedPath:
        denied = DeniedPath(
            id=projection.id, title=projection.title, denied_ts=_now(),
            reason=reason, projected_outcome=projection.projected_outcome,
            change_summary=json.dumps(projection.change,
                                      ensure_ascii=False)[:500],
            remix_lineage=list(projection.remix_lineage),
        )
        self.denied[denied.id] = denied  # U3: nothing rejected is deleted
        self._save()
        return denied

    def get(self, pid: str) -> Optional[DeniedPath]:
        return self.denied.get(pid)

    def list(self) -> List[DeniedPath]:
        return list(self.denied.values())

    def add_descendant(self, pid: str, child_id: str) -> None:
        if pid in self.denied and child_id not in self.denied[pid].remix_descendants:
            self.denied[pid].remix_descendants.append(child_id)  # U4
            self._save()


# ------------------------------------------------------------------ the loop
class SelfUpgradeLoop:
    """Projected upgrade paths -> per-path HITL -> denied-path store -> remix."""

    def __init__(self, store_dir: Optional[Path | str] = None):
        self.store_dir = Path(store_dir) if store_dir else DEFAULT_IDE_STORE
        self.root = self.store_dir / ".self_upgrade"
        self.root.mkdir(parents=True, exist_ok=True)
        self.proposals_path = self.root / "proposals.json"
        self.receipts_path = self.root / "receipts.jsonl"
        self.sandbox_root = self.root / ".sandbox_tests"
        self.proposals: Dict[str, UpgradeProjection] = {}
        if self.proposals_path.exists():
            self.proposals = {
                k: UpgradeProjection.from_dict(v)
                for k, v in json.loads(
                    self.proposals_path.read_text(encoding="utf-8")).items()
            }
        self.denied_paths = DeniedPathStore(self.root / "denied_paths.json")
        # Quetta Pan drives the loop's learning: the RIEM advice at
        # proposal time and the approval/denial outcomes at decision
        # time both go through it (Q1). The denied-path store stays
        # separate — it is the parts library, not the learning loop.
        # Guarded: the sibling's quetta_loop may be absent on a fresh
        # checkout — fail closed here with a clear error, never a bare
        # ImportError at module load.
        self.qp = require_quetta_loop()(
            self.store_dir,
            compost_name=".upgrade_compost.jsonl",
            genome_name=".upgrade_genome.json",
            receipts_name=".upgrade_qp_receipts.jsonl",
        )
        # Snapshot-every-stage (S1): propose, decide, remix, and apply
        # each run under pre/post snapshots from this store.
        self._snapshots = SnapshotStore(self.store_dir / ".snapshots")
        self._guard = StageGuard(self._snapshots)
        self.applied: List[str] = []

    # ---- persistence -------------------------------------------------
    def _save_proposals(self) -> None:
        self.proposals_path.write_text(
            json.dumps({k: v.as_dict() for k, v in self.proposals.items()},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _receipt(self, pid: str, decision: str, reason: str,
                 projected_outcome: str) -> Dict[str, Any]:
        receipt = {
            "ts": _now(), "projection_id": pid, "decision": decision,
            "reason": reason, "projected_outcome": projected_outcome,
        }
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        return receipt

    # ---- proposing ---------------------------------------------------
    def propose_projection(
        self,
        title: str,
        change: Dict[str, Any],
        projected_outcome: str,
        source: str = SOURCE_RIEM,
        remix_lineage: Optional[List[str]] = None,
        rule_id: Optional[str] = None,
        context: str = "ide-upgrade",
    ) -> UpgradeProjection:
        """Project a new upgrade path. Quetta Pan's genome stage is
        consulted and the advice is recorded on the projection; it does
        not decide — Chauncey does."""
        riem_advice = "unknown"
        if rule_id is not None:
            steered = self.qp.steer(rule_id, context)
            riem_advice = (
                f"{steered['verdict']}: {steered['reason']}"
                if steered["verdict"] == "suppress"
                else steered["verdict"]
            )
        proj = UpgradeProjection(
            id=_pid(), title=title, change=dict(change),
            projected_outcome=projected_outcome, source=source,
            remix_lineage=list(remix_lineage or []),
            created_ts=_now(), riem_advice=riem_advice,
        )
        # S1: snapshot before the proposal lands in the store.
        run = self._guard.begin(
            "upgrade-propose",
            {"proposals_before": sorted(self.proposals.keys()),
             "new": proj.as_dict()},
        )
        run.act()
        self.proposals[proj.id] = proj
        self._save_proposals()
        self._receipt(proj.id, "proposed", "projection surfaced for HITL",
                      projected_outcome)
        run.end({"proposals_after": sorted(self.proposals.keys()),
                 "proposal_id": proj.id})
        return proj

    # ---- sandbox testing -------------------------------------------
    def sandbox_test_projection(self, pid: str) -> Dict[str, Any]:
        """Execute + test one projected path in the sandbox (B1–B5).

        Runs under the sandbox-test snapshot stage (S1): pre-snapshot
        before the run, post-snapshot with the tested outcome. The
        tested outcome lands on the projection; only sandbox_ok=True
        paths are approvable at the checkpoint (U7)."""
        proj = self.proposals.get(pid)
        if proj is None:
            return {"ok": False, "error": "unknown projection"}
        if proj.status != PROPOSED:
            return {"ok": False,
                    "error": f"already {proj.status} — sandbox tests run "
                             "before the decision"}
        # S1: snapshot before the sandbox run — the tested outcome can
        # be audited back to the exact untested projection.
        run = self._guard.begin(
            "sandbox-test",
            {"proposal": proj.as_dict()},
        )
        run.act()
        result = test_projection(proj.id, proj.change, proj.title,
                                 self.sandbox_root)
        proj.tested_outcome = tested_outcome_text(result)
        proj.sandbox_ok = bool(result.ok)
        self._save_proposals()
        receipt = self._receipt(pid, "sandbox-tested",
                                f"sandbox_ok={result.ok}",
                                proj.tested_outcome)
        run.end({"sandbox_ok": result.ok,
                 "tested_outcome": proj.tested_outcome,
                 "receipt": receipt})
        return {"ok": True, "sandbox_ok": result.ok,
                "tested_outcome": proj.tested_outcome,
                "result": result.as_dict(), "receipt": receipt}

    def checkpoint(self, pid: str) -> Dict[str, Any]:
        """The HITL checkpoint view: simulated + sandbox-tested outcomes
        together, always (U7). approvable is True only for proposed
        paths whose sandbox test passed."""
        proj = self.proposals.get(pid)
        if proj is None:
            return {"ok": False, "error": "unknown projection"}
        return {
            "ok": True,
            "id": proj.id,
            "title": proj.title,
            "change": dict(proj.change),
            "projected_outcome": proj.projected_outcome,  # simulated
            "tested_outcome": proj.tested_outcome,  # sandbox-tested
            "sandbox_ok": proj.sandbox_ok,
            "riem_advice": proj.riem_advice,
            "status": proj.status,
            "approvable": proj.status == PROPOSED and proj.sandbox_ok is True,
        }

    # ---- HITL decisions ----------------------------------------------
    def decide(self, pid: str, approve: bool,
               reason: str = "") -> Dict[str, Any]:
        """Approve or deny one path. U1: only approvals unlock apply.
        U7: approvals require a passed sandbox test — untested or
        failed paths are not approvable. Denials are always allowed.
        Decided projections are terminal — no re-decides."""
        proj = self.proposals.get(pid)
        if proj is None:
            return {"ok": False, "error": "unknown projection"}
        if proj.status != PROPOSED:
            return {"ok": False,
                    "error": f"already {proj.status} — decisions are terminal"}
        if approve and proj.sandbox_ok is not True:
            # Refused before any snapshot — nothing acted, nothing to undo.
            if proj.sandbox_ok is None:
                return {"ok": False,
                        "error": "refusing approve — no sandbox test run yet",
                        "detail": "run sandbox_test_projection(pid) first; "
                                  "untested paths are not approvable"}
            return {"ok": False,
                    "error": "refusing approve — sandbox test failed",
                    "detail": f"{proj.tested_outcome[:300]} — deny to route "
                              "to the remix store"}
        # S1: snapshot before the decision mutates anything — a decision
        # can be audited back to the exact undecided projection.
        run = self._guard.begin(
            "upgrade-decide",
            {"proposal": proj.as_dict(), "approve": approve,
             "reason": reason},
        )
        run.act()
        proj.status = APPROVED if approve else DENIED
        proj.decided_ts = _now()
        self._save_proposals()
        # The outcome is absorbed by Quetta Pan's compost stage (Q3):
        # approvals fold as successes, denials as failures — steering
        # the next projection. The denial ALSO lands in the denied-path
        # store below: that is the parts library, a different job.
        self.qp.absorb_outcome(
            "approval" if approve else "denial",
            rule_id=f"upgrade:{proj.id}",
            context="ide-upgrade",
            file="self_upgrade",
            detail=f"{'approved' if approve else 'denied'}: {reason or '—'} "
                   f"| projected: {proj.projected_outcome}"[:200],
        )
        if approve:
            receipt = self._receipt(pid, "approved", reason,
                                    proj.projected_outcome)
        else:
            denied = self.denied_paths.record(proj, reason)
            receipt = self._receipt(pid, "denied", reason,
                                    proj.projected_outcome)
            receipt["denied_path_id"] = denied.id
        run.end({"status": proj.status, "decided_ts": proj.decided_ts,
                 "receipt": receipt})
        return {"ok": True, "status": proj.status, "receipt": receipt}

    # ---- projection recombination ------------------------------------
    def recombine(
        self,
        denied_ids: List[str],
        title: str,
        change: Dict[str, Any],
        projected_outcome: str,
    ) -> Dict[str, Any]:
        """Recombine denied paths into a new projection. The denied paths
        stay in the store; the child cites them in remix_lineage (U4), and
        each parent records the child as a remix descendant."""
        missing = [d for d in denied_ids if self.denied_paths.get(d) is None]
        if missing:
            return {"ok": False, "error": "unknown denied path(s)",
                    "missing": missing}
        # S1: snapshot before Quetta Pan remixes denied paths — the
        # remix can be traced back to the exact denied parents.
        run = self._guard.begin(
            "quetta-remix",
            {"denied_ids": list(denied_ids), "title": title,
             "change": dict(change),
             "projected_outcome": projected_outcome},
        )
        proj = self.propose_projection(
            title=title, change=change,
            projected_outcome=projected_outcome,
            source=SOURCE_DENIED_REMIX,
            remix_lineage=list(denied_ids),
        )
        run.act()
        for d in denied_ids:
            self.denied_paths.add_descendant(d, proj.id)
        run.end({"child_id": proj.id,
                 "parents": list(denied_ids)})
        return {"ok": True, "projection": proj}

    # ---- guarded apply -------------------------------------------------
    def apply_projection(self, pid: str) -> Dict[str, Any]:
        """U1: refuse unless the projection carries an explicit approval.
        Application is permission-gated here; execution stays with the
        operator's normal builder path."""
        proj = self.proposals.get(pid)
        if proj is None:
            return {"ok": False, "error": "unknown projection"}
        if proj.status != APPROVED:
            return {
                "ok": False, "error": "refusing to apply",
                "detail": f"projection {pid} is '{proj.status}' — "
                          "apply needs an explicit approve decision first",
            }
        if pid in self.applied:
            return {"ok": False, "error": "already applied"}
        # S1: snapshot before the final write of an approved path.
        run = self._guard.begin(
            "upgrade-apply",
            {"proposal": proj.as_dict(),
             "applied_before": list(self.applied)},
        )
        run.act()
        self.applied.append(pid)
        receipt = self._receipt(pid, "applied",
                                "apply executed under explicit approval",
                                proj.projected_outcome)
        run.end({"applied_after": list(self.applied), "receipt": receipt})
        return {"ok": True, "projection": proj.as_dict(), "receipt": receipt}

    def list_projections(self, status: Optional[str] = None) -> List[UpgradeProjection]:
        projs = list(self.proposals.values())
        if status:
            projs = [p for p in projs if p.status == status]
        return projs


__all__ = [
    "APPROVED",
    "DENIED",
    "PROPOSED",
    "DeniedPath",
    "DeniedPathStore",
    "SelfUpgradeLoop",
    "UpgradeProjection",
]
