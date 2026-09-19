"""Merge/judge — the twin pair converges to ONE action.

Protocol (every turn offered to an agent):

1. **bid** — left and right hemispheres each propose a position.
2. **agree** — same action, both confident → act at once, with a joint
   receipt carrying both positions. No counsel needed.
3. **diverge** — positions differ → escalate to the agent's class CI
   counsel (AICI/SICI/XICI). Interface: agent id + both hemisphere
   positions in, verdict out. The counsel advises; the pair converges:
   - ``proceed`` / ``proceed-with-conditions`` → act on the
     higher-confidence hemisphere's action, annotated with conditions
   - ``hold-for-human`` → escalate to the keeper
   - ``refuse`` → stand down, receipted
   Agents capped at intake (no counsel) escalate divergence straight
   to the keeper.
4. **keeper** — the keeper's pick is the final word. Every keeper pick
   is exported to the growth loop as training signal — the resolutions
   that teach the pair to converge alone next time.

Counsel never commands: its verdict is advice the pair weighs.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.agent.agent import Agent, find_minion
from levi.agent.hemisphere import Position, TurnTask, positions_agree
from levi.ci import escalation as ci_escalation

__all__ = [
    "Decision",
    "decide",
    "escalate_to_counsel",
    "escalate_to_keeper",
    "keeper_pick",
    "mint_merge_receipt",
    "agent_home",
    "merge_receipts_dir",
]

#: Decision outcomes.
OUTCOMES = ("act", "counsel", "keeper", "keeper-pick", "refuse")

_GENESIS = "genesis:" + "0" * 64
_MINT_LOCK = threading.Lock()


def agent_home() -> Path:
    override = os.environ.get("LEVI_AGENT_HOME")
    p = Path(override).expanduser() if override else Path.home() / ".levi" / "agent"
    return p


def merge_receipts_dir() -> Path:
    p = agent_home() / "merge_receipts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _body_hash(envelope: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(envelope).encode("utf-8")).hexdigest()


def _existing_receipts() -> List[Path]:
    d = merge_receipts_dir()
    return sorted(d.glob("merge-*.json"))


def mint_merge_receipt(
    body: Dict[str, Any], receipts_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Mint a hash-chained receipt for one twin-pair resolution."""
    d = Path(receipts_dir) if receipts_dir else merge_receipts_dir()
    d.mkdir(parents=True, exist_ok=True)
    with _MINT_LOCK:
        existing = sorted(d.glob("merge-*.json"))
        seq = len(existing) + 1
        if existing:
            prev_hash = json.loads(existing[-1].read_text(encoding="utf-8"))[
                "body_hash"
            ]
        else:
            prev_hash = _GENESIS
        receipt = {
            "seq": seq,
            "prev_hash": prev_hash,
            "body": body,
            "body_hash": _body_hash({"seq": seq, "prev_hash": prev_hash, "body": body}),
            "minted_ts": _utcnow(),
        }
        path = d / f"merge-{seq:06d}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, indent=2, sort_keys=True))
        return receipt


def _task_fingerprint(task: TurnTask) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "task_id": task.task_id,
                "prompt": task.prompt,
                "context": task.context,
                "stakes": task.stakes,
            }
        ).encode("utf-8")
    ).hexdigest()


@dataclass
class Decision:
    """One converged resolution of the twin pair."""

    decision_id: str
    agent_id: str
    task_id: str
    outcome: str
    action: Optional[str]
    left_position: Dict[str, Any]
    right_position: Dict[str, Any]
    verdict: Optional[Dict[str, Any]] = None
    conditions: List[str] = field(default_factory=list)
    keeper_request: Optional[Dict[str, Any]] = None
    receipt: Optional[Dict[str, Any]] = None
    signaled: bool = False
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _decision_id(agent_id: str, task: TurnTask) -> str:
    return f"dec-{agent_id}-{_task_fingerprint(task)[:12]}"


def _signal_resolution(decision: Decision, agent: Agent, extra: Dict[str, Any]) -> bool:
    """Export the resolution to the growth loop as training signal.

    Best-effort, never fatal. Keeper picks are flagged as the premium
    signal — the resolutions that teach the pair to converge alone.
    """
    try:
        from levi.growth.journal import append_entry

        append_entry(
            {
                "kind": "agent_twin_resolution",
                "agent_id": decision.agent_id,
                "agent_class": agent.class_tag,
                "counsel": agent.counsel_name,
                "task_id": decision.task_id,
                "outcome": decision.outcome,
                "action": decision.action,
                "keeper_pick": decision.outcome == "keeper-pick",
                "verdict_ruling": (decision.verdict or {}).get("ruling"),
                "engine": "levi.agent.merge v1.0.0",
                "note": (
                    "twin-pair resolution; keeper picks are training signal "
                    "for future convergence"
                ),
                **extra,
            }
        )
        return True
    except Exception:
        return False


def _receipt_body(
    decision_id: str,
    agent: Agent,
    task: TurnTask,
    outcome: str,
    action: Optional[str],
    left: Position,
    right: Position,
    verdict: Optional[Any] = None,
    conditions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "decision_id": decision_id,
        "agent_id": agent.agent_id,
        "agent_class": agent.class_tag,
        "counsel": agent.counsel_name,
        "pair_id": agent.pair_id,
        "task_id": task.task_id,
        "task_fingerprint": _task_fingerprint(task),
        "outcome": outcome,
        "action": action,
        "hemisphere_left": left.to_dict(),
        "hemisphere_right": right.to_dict(),
        "verdict_ruling": getattr(verdict, "ruling", None),
        "verdict_id": getattr(verdict, "verdict_id", None),
        "conditions": conditions or [],
        "ts": _utcnow(),
    }


def escalate_to_counsel(
    agent: Agent,
    left: Position,
    right: Position,
    task: TurnTask,
    dry_run: bool = True,
) -> Any:
    """Escalate a divergence to the agent's class CI counsel.

    Interface: agent id + both hemisphere positions in, verdict out.
    Compatible with :func:`levi.ci.escalation.counsel` — the counsel
    deliberates in full; with ``dry_run=True`` nothing is persisted.
    """
    if not agent.counsel_name:
        raise ValueError(
            f"agent {agent.agent_id} is capped at intake — no counsel serves it"
        )
    divergence = (
        f"left bids '{left.proposed_action}' (confidence {left.confidence:.2f}); "
        f"right bids '{right.proposed_action}' (confidence {right.confidence:.2f})"
    )
    result = ci_escalation.counsel(
        minion_id=agent.agent_id,
        question=(
            f"Twin-pair divergence on task '{task.task_id}': {divergence}. "
            f"Advise the pair toward one action."
        ),
        context={
            "hemisphere_left": left.to_dict(),
            "hemisphere_right": right.to_dict(),
            "divergence": divergence,
            "pair_id": agent.pair_id,
        },
        stakes=task.stakes,
        dry_run=dry_run,
    )
    return result.verdict


def escalate_to_keeper(
    agent: Agent,
    left: Position,
    right: Position,
    task: TurnTask,
    verdict: Optional[Any] = None,
    dry_run: bool = True,
) -> Decision:
    """Escalate to the keeper — the final word. Returns a keeper request."""
    decision_id = _decision_id(agent.agent_id, task)
    request = {
        "request_id": f"keeper-{decision_id}",
        "decision_id": decision_id,
        "agent_id": agent.agent_id,
        "agent_class": agent.class_tag,
        "task_id": task.task_id,
        "task_fingerprint": _task_fingerprint(task),
        "hemisphere_left": left.to_dict(),
        "hemisphere_right": right.to_dict(),
        "verdict_ruling": getattr(verdict, "ruling", None),
        "verdict_id": getattr(verdict, "verdict_id", None),
        "requested_at": _utcnow(),
        "status": "awaiting-keeper-pick",
    }
    body = _receipt_body(
        decision_id, agent, task, "keeper", None, left, right, verdict
    )
    receipt = None if dry_run else mint_merge_receipt(body)
    return Decision(
        decision_id=decision_id,
        agent_id=agent.agent_id,
        task_id=task.task_id,
        outcome="keeper",
        action=None,
        left_position=left.to_dict(),
        right_position=right.to_dict(),
        verdict=asdict(verdict) if verdict else None,
        keeper_request=request,
        receipt=receipt,
        note="escalated to the keeper; awaiting pick",
    )


def keeper_pick(
    keeper_request: Dict[str, Any],
    chosen_action: str,
    note: str = "",
    dry_run: bool = True,
) -> Decision:
    """Record the keeper's pick — the final word, and training signal.

    Every keeper pick is exported to the growth loop: the resolutions
    that teach the pair to converge alone next time.
    """
    try:
        agent = next(
            (a for a in _agent_cache().values()
             if a.agent_id == keeper_request["agent_id"]),
            None,
        )
    except Exception:
        agent = None
    decision_id = keeper_request["decision_id"]
    left = keeper_request["hemisphere_left"]
    right = keeper_request["hemisphere_right"]
    body = {
        "decision_id": decision_id,
        "agent_id": keeper_request["agent_id"],
        "task_id": keeper_request["task_id"],
        "task_fingerprint": keeper_request["task_fingerprint"],
        "outcome": "keeper-pick",
        "action": chosen_action,
        "hemisphere_left": left,
        "hemisphere_right": right,
        "keeper_note": note,
        "keeper_request_id": keeper_request["request_id"],
        "ts": _utcnow(),
    }
    receipt = None if dry_run else mint_merge_receipt(body)
    decision = Decision(
        decision_id=decision_id,
        agent_id=keeper_request["agent_id"],
        task_id=keeper_request["task_id"],
        outcome="keeper-pick",
        action=chosen_action,
        left_position=left,
        right_position=right,
        keeper_request={**keeper_request, "status": "picked"},
        receipt=receipt,
        note=note or "the keeper has spoken",
    )
    if not dry_run and agent is not None:
        decision.signaled = _signal_resolution(decision, agent, {})
    return decision


_AGENT_CACHE: Dict[str, Agent] = {}


def _agent_cache() -> Dict[str, Agent]:
    if not _AGENT_CACHE:
        from levi.agent.registry import REGISTRY_PATH, load_registry

        try:
            agents = load_registry() if REGISTRY_PATH.is_file() else None
        except Exception:
            agents = None
        if agents is None:
            from levi.agent.agent import build_agents
            from levi.agent.registry import load_grades

            agents = build_agents(load_grades())
        for a in agents:
            _AGENT_CACHE[a.agent_id] = a
    return _AGENT_CACHE


def decide(
    agent: Agent,
    task: TurnTask,
    left_pos: Optional[Position] = None,
    right_pos: Optional[Position] = None,
    dry_run: bool = True,
) -> Decision:
    """Run the merge/judge protocol: the pair converges to one action."""
    minion = find_minion(agent.agent_id)
    left = left_pos or agent.left.propose(task, minion)
    right = right_pos or agent.right.propose(task, minion)
    decision_id = _decision_id(agent.agent_id, task)

    # 1. Agreement → act at once, joint receipt.
    if positions_agree(left, right):
        action = left.proposed_action
        body = _receipt_body(
            decision_id, agent, task, "act", action, left, right
        )
        receipt = None if dry_run else mint_merge_receipt(body)
        decision = Decision(
            decision_id=decision_id,
            agent_id=agent.agent_id,
            task_id=task.task_id,
            outcome="act",
            action=action,
            left_position=left.to_dict(),
            right_position=right.to_dict(),
            receipt=receipt,
            note="hemispheres agree; joint action",
        )
        if not dry_run:
            decision.signaled = _signal_resolution(decision, agent, {})
        return decision

    # 2. Divergence → counsel, or keeper when no counsel serves.
    if not agent.counsel_name:
        return escalate_to_keeper(agent, left, right, task, dry_run=dry_run)

    verdict = escalate_to_counsel(agent, left, right, task, dry_run=dry_run)
    ruling = verdict.ruling
    if ruling in ("proceed", "proceed-with-conditions"):
        winner = left if left.confidence >= right.confidence else right
        action = winner.proposed_action
        conditions = list(verdict.conditions)
        body = _receipt_body(
            decision_id, agent, task, "counsel", action, left, right,
            verdict, conditions,
        )
        receipt = None if dry_run else mint_merge_receipt(body)
        decision = Decision(
            decision_id=decision_id,
            agent_id=agent.agent_id,
            task_id=task.task_id,
            outcome="counsel",
            action=action,
            left_position=left.to_dict(),
            right_position=right.to_dict(),
            verdict=asdict(verdict),
            conditions=conditions,
            receipt=receipt,
            note=f"counsel {verdict.counsel} advises '{ruling}'; pair converges",
        )
        if not dry_run:
            decision.signaled = _signal_resolution(decision, agent, {})
        return decision
    if ruling == "hold-for-human":
        return escalate_to_keeper(agent, left, right, task, verdict, dry_run=dry_run)

    # refuse → stand down, receipted.
    body = _receipt_body(
        decision_id, agent, task, "refuse", None, left, right, verdict
    )
    receipt = None if dry_run else mint_merge_receipt(body)
    decision = Decision(
        decision_id=decision_id,
        agent_id=agent.agent_id,
        task_id=task.task_id,
        outcome="refuse",
        action=None,
        left_position=left.to_dict(),
        right_position=right.to_dict(),
        verdict=asdict(verdict),
        receipt=receipt,
        note=f"counsel {verdict.counsel} refuses; pair stands down",
    )
    if not dry_run:
        decision.signaled = _signal_resolution(decision, agent, {})
    return decision
