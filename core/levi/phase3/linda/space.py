"""Linda coordination dialect — tuple spaces for the substrate.

WORKING TITLE only — naming is Chauncey's, never canon.

B9: ``out`` / ``in`` / ``rd`` / ``eval`` over an in-process tuple space.
Matching is deterministic (oldest match wins, receipt-sequence order);
``in``/``rd`` waits are bounded by the scan-cycle boundary, which the
tests drive manually via :meth:`TupleSpace.boundary`.  Every operation —
including faults — produces a receipt; timestamps live only inside
receipts.

Stdlib-only. Zero network. No sentience or subjective-experience claims:
a tuple is a message, not a thought.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Faults
# ---------------------------------------------------------------------------


class LindaFault(Exception):
    """A receipted Linda fault.  The receipt is always on ``.receipt``."""

    def __init__(self, receipt: Dict[str, Any]):
        self.receipt = receipt
        super().__init__(str(receipt.get("reason", "linda fault")))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _is_wildcard(pattern: Any) -> bool:
    return isinstance(pattern, str) and pattern.startswith("?") and len(pattern) > 1


def _field_eq(a: Any, b: Any) -> bool:
    """Strict field equality: same JSON type and same value.

    Plain ``==`` is too loose for a coordination dialect (``True == 1``,
    ``1 == 1.0``); strictness keeps matching deterministic and
    JSON-faithful.
    """
    return type(a) is type(b) and a == b


def match_template(
    template: Tuple[Any, ...], tag: str, fields: List[Any]
) -> Optional[Dict[str, Any]]:
    """Match a template ``(tag, pattern, ...)`` against a tuple.

    Returns the wildcard bindings dict on match, ``None`` on no match.
    Bindings are consistent within a template: the same ``?var`` must bind
    the same value at every position.
    """
    if not template or template[0] != tag:
        return None
    patterns = list(template[1:])
    if len(patterns) != len(fields):
        return None
    bindings: Dict[str, Any] = {}
    for pattern, value in zip(patterns, fields, strict=True):
        if _is_wildcard(pattern):
            if pattern in bindings:
                if not _field_eq(bindings[pattern], value):
                    return None
            else:
                bindings[pattern] = value
        elif not _field_eq(pattern, value):
            return None
    return bindings


def _check_jsonable(fields: List[Any]) -> bool:
    try:
        json.dumps(fields)
    except (TypeError, ValueError):
        return False
    return True


# ---------------------------------------------------------------------------
# Blackboard adapter protocol
# ---------------------------------------------------------------------------


class BlackboardSpace(Protocol):
    """The blackboard's tuple-space face: post / take / read.

    The middle team's blackboard implements this; until it exists,
    :class:`LocalSpace` is the in-process implementation.
    """

    def post_tuple(self, tag: str, *fields: Any) -> Dict[str, Any]: ...
    def take_tuple(self, template: Tuple[Any, ...]) -> Any: ...
    def read_tuple(self, template: Tuple[Any, ...]) -> Any: ...


# ---------------------------------------------------------------------------
# Parked waits
# ---------------------------------------------------------------------------


@dataclass
class PendingTicket:
    """A parked ``in``/``rd`` with no immediate match.

    Resolved by :meth:`TupleSpace.boundary` (receipted fault) or woken
    early when a matching tuple is ``out``'d.
    """

    ticket_id: int
    mode: str  # "in" | "rd"
    template: Tuple[Any, ...]
    outcome: Optional[Tuple[str, Any]] = field(default=None, repr=False)

    def result(self) -> Dict[str, Any]:
        """Return the tuple, or raise the receipted :class:`LindaFault`."""
        if self.outcome is None:
            raise LindaFault(
                {"op": "wait", "reason": "ticket not yet resolved", "ts": _now()}
            )
        kind, value = self.outcome
        if kind == "fault":
            raise value
        return value


@dataclass
class EvalTask:
    task_id: str
    fn: Callable[[], Any]
    out_tag: str
    receipt_seq: int


def _now() -> str:
    # Timestamps live ONLY inside receipts; logic never reads them.
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tuple space
# ---------------------------------------------------------------------------


class TupleSpace:
    """An in-process Linda tuple space with receipted operations."""

    def __init__(self, strict_tags: bool = True):
        self._strict_tags = strict_tags
        self._seq = 0
        self._cycle = 0
        self._tuples: List[Dict[str, Any]] = []  # insertion order = receipt order
        self._declared: Dict[str, int] = {}  # tag -> arity
        self._waiters: List[PendingTicket] = []
        self._eval_tasks: List[EvalTask] = []
        self._receipts: List[Dict[str, Any]] = []
        self._op_log: List[Tuple[Any, ...]] = []  # replayable op sequence
        self._accounting: Dict[int, str] = {}  # tuple receipt seq -> lifecycle state

    # -- receipts ------------------------------------------------------
    def _receipt(self, op: str, **kw: Any) -> Dict[str, Any]:
        self._seq += 1
        receipt: Dict[str, Any] = {"seq": self._seq, "op": op, "ts": _now()}
        receipt.update(kw)
        self._receipts.append(receipt)
        return receipt

    def receipts(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._receipts)

    # -- schema ---------------------------------------------------------
    def declare_tag(self, tag: str, arity: int) -> Dict[str, Any]:
        if not isinstance(tag, str) or not tag:
            raise LindaFault(self._receipt("declare", reason="bad tag", tag=tag))
        if not isinstance(arity, int) or arity < 0:
            raise LindaFault(
                self._receipt("declare", reason="bad arity", tag=tag, arity=arity)
            )
        self._declared[tag] = arity
        self._op_log.append(("declare", tag, arity))
        return self._receipt("declare", tag=tag, arity=arity, ok=True)

    def _check_tag(self, tag: str, arity: int) -> None:
        if tag not in self._declared:
            receipt = self._receipt(
                "tag_fault", reason="undeclared tag", tag=tag, strict=self._strict_tags
            )
            if self._strict_tags:
                raise LindaFault(receipt)
            return
        if self._declared[tag] != arity:
            raise LindaFault(
                self._receipt(
                    "tag_fault",
                    reason="arity mismatch",
                    tag=tag,
                    want=self._declared[tag],
                    got=arity,
                )
            )

    # -- out ------------------------------------------------------------
    def out(self, tag: str, *fields: Any, provenance: Any = None) -> Dict[str, Any]:
        field_list = list(fields)
        self._check_tag(tag, len(field_list))
        if not _check_jsonable(field_list):
            raise LindaFault(
                self._receipt("out", reason="fields not JSON values", tag=tag)
            )
        tup = {
            "tag": tag,
            "fields": copy.deepcopy(field_list),
            "provenance": provenance,
        }
        receipt = self._receipt(
            "out", tag=tag, fields=copy.deepcopy(field_list), ok=True
        )
        tup["receipt"] = receipt["seq"]
        self._tuples.append(tup)
        self._accounting[receipt["seq"]] = "posted"
        self._op_log.append(("out", tag, copy.deepcopy(field_list)))
        self._wake_waiters(tup)
        return receipt

    # -- in / rd ----------------------------------------------------------
    @staticmethod
    def _norm_template(template: Any) -> Tuple[Any, ...]:
        if isinstance(template, (tuple, list)):
            return tuple(template)
        raise LindaFault({"op": "template", "reason": "template must be tuple/list"})

    def _oldest_match(self, template: Tuple[Any, ...]) -> Optional[int]:
        for idx, tup in enumerate(self._tuples):
            if match_template(template, tup["tag"], tup["fields"]) is not None:
                return idx
        return None

    def _park(self, mode: str, template: Tuple[Any, ...]) -> PendingTicket:
        self._seq += 1
        ticket = PendingTicket(ticket_id=self._seq, mode=mode, template=tuple(template))
        self._waiters.append(ticket)
        self._receipt(
            "wait_parked", mode=mode, template=list(template), ticket=ticket.ticket_id
        )
        self._op_log.append((mode, list(template)))
        return ticket

    def in_(self, template: Any) -> Any:
        """Take the oldest matching tuple; park until the boundary if none."""
        tmpl = self._norm_template(template)
        idx = self._oldest_match(tmpl)
        if idx is not None:
            tup = self._tuples.pop(idx)
            self._accounting[tup["receipt"]] = "consumed"
            self._receipt("in", template=list(tmpl), took=tup["receipt"], ok=True)
            self._op_log.append(("in", list(tmpl)))
            return copy.deepcopy(tup)
        return self._park("in", tmpl)

    def rd(self, template: Any) -> Any:
        """Read (a copy of) the oldest matching tuple; park if none."""
        tmpl = self._norm_template(template)
        idx = self._oldest_match(tmpl)
        if idx is not None:
            tup = self._tuples[idx]
            self._receipt("rd", template=list(tmpl), read=tup["receipt"], ok=True)
            self._op_log.append(("rd", list(tmpl)))
            return copy.deepcopy(tup)
        return self._park("rd", tmpl)

    def _wake_waiters(self, tup: Dict[str, Any]) -> None:
        for waiter in list(self._waiters):
            if match_template(waiter.template, tup["tag"], tup["fields"]) is None:
                continue
            self._waiters.remove(waiter)
            if waiter.mode == "in":
                self._tuples.remove(tup)
                self._accounting[tup["receipt"]] = "consumed"
                waiter.outcome = ("tuple", copy.deepcopy(tup))
                self._receipt(
                    "in_woke",
                    ticket=waiter.ticket_id,
                    took=tup["receipt"],
                    ok=True,
                )
            else:
                waiter.outcome = ("tuple", copy.deepcopy(tup))
                self._receipt(
                    "rd_woke",
                    ticket=waiter.ticket_id,
                    read=tup["receipt"],
                    ok=True,
                )
            return  # one tuple wakes exactly one waiter (oldest first)

    # -- eval -------------------------------------------------------------
    def eval(
        self, fn: Callable[[], Any], out_tag: str, task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a task; its result is ``out``'d at the next boundary."""
        if not callable(fn):
            raise LindaFault(self._receipt("eval", reason="task not callable"))
        self._seq += 1
        tid = task_id or "task-%d" % self._seq
        self._eval_tasks.append(
            EvalTask(task_id=tid, fn=fn, out_tag=out_tag, receipt_seq=self._seq)
        )
        self._op_log.append(("eval", tid, out_tag))
        return self._receipt("eval_registered", task_id=tid, out_tag=out_tag, ok=True)

    def _run_eval_tasks(self) -> None:
        for task in self._eval_tasks:
            try:
                produced = task.fn()
            except Exception as exc:  # task failure is receipted, never silent
                self._receipt(
                    "eval_failed", task_id=task.task_id, reason=str(exc), ok=False
                )
                continue
            fields = list(produced) if produced is not None else []
            try:
                receipt = self.out(
                    task.out_tag, *fields, provenance={"task": task.task_id}
                )
            except LindaFault as fault:
                self._receipt(
                    "eval_failed",
                    task_id=task.task_id,
                    reason=fault.receipt.get("reason"),
                    ok=False,
                )
                continue
            self._receipt(
                "eval_completed",
                task_id=task.task_id,
                out_receipt=receipt["seq"],
                ok=True,
            )
        self._eval_tasks = []

    # -- expiry (no silent drops: every out is consumed or expired) --------
    def expire(self, template: Any) -> Dict[str, Any]:
        tmpl = self._norm_template(template)
        expired = []
        for tup in list(self._tuples):
            if match_template(tmpl, tup["tag"], tup["fields"]) is not None:
                self._tuples.remove(tup)
                self._accounting[tup["receipt"]] = "expired"
                expired.append(tup["receipt"])
        self._op_log.append(("expire", list(tmpl)))
        return self._receipt("expire", template=list(tmpl), expired=expired, ok=True)

    def lifecycle(self, out_receipt_seq: int) -> Optional[str]:
        """Lifecycle state of an ``out``'d tuple: posted/consumed/expired."""
        return self._accounting.get(out_receipt_seq)

    # -- cycle boundary ----------------------------------------------------
    def boundary(self) -> Dict[str, Any]:
        """Drive one scan-cycle boundary: run eval tasks, fault parked waits."""
        self._run_eval_tasks()
        faulted = []
        for waiter in self._waiters:
            fault = LindaFault(
                self._receipt(
                    "wait_fault",
                    mode=waiter.mode,
                    template=list(waiter.template),
                    ticket=waiter.ticket_id,
                    reason="no match at cycle boundary",
                    ok=False,
                )
            )
            waiter.outcome = ("fault", fault)
            faulted.append(waiter.ticket_id)
        self._waiters = []
        self._cycle += 1
        self._op_log.append(("boundary",))
        return self._receipt("boundary", cycle=self._cycle, faulted=faulted, ok=True)

    @property
    def cycle(self) -> int:
        return self._cycle

    # -- replay / determinism ----------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """Byte-comparable space state (no timestamps)."""
        return {
            "cycle": self._cycle,
            "declared": dict(sorted(self._declared.items())),
            "tuples": [
                {
                    "tag": t["tag"],
                    "fields": t["fields"],
                    "receipt": t["receipt"],
                    "provenance": t["provenance"],
                }
                for t in self._tuples
            ],
            "accounting": {str(k): v for k, v in sorted(self._accounting.items())},
        }

    def op_log(self) -> List[Tuple[Any, ...]]:
        return copy.deepcopy(self._op_log)

    @classmethod
    def replay(cls, ops: List[Tuple[Any, ...]], **kw: Any) -> "TupleSpace":
        """Rebuild a space by re-applying a recorded op sequence."""
        space = cls(**kw)
        pending: List[PendingTicket] = []
        for op in ops:
            kind = op[0]
            if kind == "declare":
                space.declare_tag(op[1], op[2])
            elif kind == "out":
                space.out(op[1], *op[2])
            elif kind in ("in", "rd"):
                ticket = getattr(space, "in_" if kind == "in" else "rd")(tuple(op[1]))
                if isinstance(ticket, PendingTicket):
                    pending.append(ticket)
            elif kind == "eval":
                # eval task bodies are callables, not serializable: replay
                # cannot reproduce them. Say so loudly, never silently.
                raise LindaFault(
                    space._receipt(
                        "replay_fault",
                        reason="eval tasks are not replayable",
                        task_id=op[1],
                        ok=False,
                    )
                )
            elif kind == "expire":
                space.expire(tuple(op[1]))
            elif kind == "boundary":
                space.boundary()
        for ticket in pending:
            try:
                ticket.result()
            except LindaFault:
                pass  # boundary-faulted waits replay as faults, as recorded
        return space


class LocalSpace(TupleSpace):
    """In-process :class:`BlackboardSpace` implementation (until the middle
    team's blackboard exists; tests target this)."""

    def post_tuple(self, tag: str, *fields: Any) -> Dict[str, Any]:
        return self.out(tag, *fields)

    def take_tuple(self, template: Tuple[Any, ...]) -> Any:
        return self.in_(template)

    def read_tuple(self, template: Tuple[Any, ...]) -> Any:
        return self.rd(template)
