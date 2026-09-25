"""Live queries, typed message ports, cycle-boundary timing.

WORKING TITLE only — naming is Chauncey's, never canon.

B12: (1) live queries over a read-only ``MemoryView`` protocol — the
boundary pushes updates, queries never poll; (2) typed message ports —
every message validated against its port's schema and cycle-stamped;
(3) copper timing reinterpreted as the scan-cycle law: nothing in this
layer is timestamped finer than a cycle, and every delivery happens at
a boundary, never mid-cycle.  Tests drive the boundary manually via
:meth:`LiveQHub.boundary_flush` (the ``CycleHook`` protocol is what the
scan-mind's commit step will call).

Deliberately does NOT touch ``core/levi/copper/`` — the two coexist
without contact.

Stdlib-only. Zero network. No sentience or subjective-experience
claims: a port is a channel, not a voice.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol


class LiveQFault(Exception):
    """A receipted liveq fault.  The receipt is on ``.receipt``."""

    def __init__(self, receipt: Dict[str, Any]):
        self.receipt = receipt
        super().__init__(str(receipt.get("reason", "liveq fault")))


def _now() -> str:
    # Timestamps live ONLY inside receipts; logic never reads them.
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Memory view protocol + stub
# ---------------------------------------------------------------------------


class MemoryView(Protocol):
    """Read-only view live queries sit over (shared with A6 cards)."""

    def current_version(self) -> int: ...
    def match(self, predicate: Any, since_version: int) -> List[Dict[str, Any]]: ...


def _predicate_matches(predicate: Any, fact_key: str, fact_value: Any) -> bool:
    if callable(predicate):
        try:
            return bool(predicate(fact_key, fact_value))
        except Exception:
            return False
    if isinstance(predicate, dict):
        for k, want in predicate.items():
            if k == "key" and fact_key != want:
                return False
            if k == "value" and fact_value != want:
                return False
        return True
    return False


class StubMemoryView:
    """In-memory versioned fact store implementing :class:`MemoryView`.

    Facts are ``(key, value)`` pairs; every write bumps the version, so
    live queries can ask "what's new since version N".
    """

    def __init__(self):
        self._facts: List[Dict[str, Any]] = []
        self._version = 0

    def write_fact(self, key: str, value: Any) -> int:
        self._version += 1
        self._facts.append(
            {"key": key, "value": copy.deepcopy(value), "version": self._version}
        )
        return self._version

    def current_version(self) -> int:
        return self._version

    def match(self, predicate: Any, since_version: int) -> List[Dict[str, Any]]:
        out = []
        for fact in self._facts:
            if fact["version"] > since_version and _predicate_matches(
                predicate, fact["key"], fact["value"]
            ):
                out.append(copy.deepcopy(fact))
        return out


# ---------------------------------------------------------------------------
# Cycle hook protocol
# ---------------------------------------------------------------------------


class CycleHook(Protocol):
    """What the scan-mind's commit step calls at each boundary."""

    def on_boundary(self, cycle: int) -> None: ...


# ---------------------------------------------------------------------------
# Queries and ports
# ---------------------------------------------------------------------------


@dataclass
class LiveQuery:
    id: str
    predicate: Any
    holder: Callable[[str, List[Dict[str, Any]]], None]
    last_version: int
    open: bool = True


@dataclass
class Port:
    id: str
    schema: Any  # {field: type} or callable(payload) -> bool
    owner: str
    deliver: Optional[Callable[[Dict[str, Any]], None]] = None
    inbox: List[Dict[str, Any]] = field(default_factory=list)


def _validate_schema(schema: Any, payload: Any) -> Optional[str]:
    """Return None if valid, else a human reason string."""
    if callable(schema):
        try:
            ok = schema(payload)
        except Exception as exc:
            return "schema callable raised: %s" % exc
        return None if ok else "schema callable rejected payload"
    if not isinstance(schema, dict):
        return "schema must be a {field: type} dict or a callable"
    if not isinstance(payload, dict):
        return "payload must be a dict"
    for fname, ftype in schema.items():
        if fname not in payload:
            return "missing field %r" % fname
        value = payload[fname]
        if (
            ftype is float
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            continue
        if type(value) is not ftype:  # strict: bool is not int here
            return "field %r must be %s, got %s" % (
                fname,
                getattr(ftype, "__name__", ftype),
                type(value).__name__,
            )
    return None


class LiveQHub:
    """Cycle-quantized live queries + typed ports."""

    def __init__(self, memory_view: Optional[MemoryView] = None):
        self._view: MemoryView = memory_view or StubMemoryView()
        self._cycle = 0
        self._seq = 0
        self._queries: Dict[str, LiveQuery] = {}
        self._ports: Dict[str, Port] = {}
        self._queue: List[Dict[str, Any]] = []  # undelivered messages
        self._hooks: List[CycleHook] = []
        self._receipts: List[Dict[str, Any]] = []
        self._delivered: List[Dict[str, Any]] = []  # delivery order record

    # -- receipts ------------------------------------------------------
    def _receipt(self, op: str, **kw: Any) -> Dict[str, Any]:
        self._seq += 1
        receipt: Dict[str, Any] = {
            "seq": self._seq,
            "op": op,
            "cycle": self._cycle,
            "ts": _now(),
        }
        receipt.update(kw)
        self._receipts.append(receipt)
        return receipt

    def receipts(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._receipts)

    @property
    def cycle(self) -> int:
        return self._cycle

    @property
    def view(self) -> MemoryView:
        return self._view

    # -- live queries ----------------------------------------------------
    def register_query(
        self, predicate: Any, holder: Callable[[str, List[Dict[str, Any]]], None]
    ) -> Dict[str, Any]:
        if not callable(holder):
            raise LiveQFault(
                self._receipt("query_register", reason="holder not callable", ok=False)
            )
        self._seq += 1
        qid = "q-%d" % self._seq
        self._queries[qid] = LiveQuery(
            id=qid,
            predicate=predicate,
            holder=holder,
            last_version=self._view.current_version(),
        )
        return self._receipt("query_register", query_id=qid, ok=True)

    def close_query(self, query_id: str) -> Dict[str, Any]:
        query = self._queries.get(query_id)
        if query is None or not query.open:
            raise LiveQFault(
                self._receipt(
                    "query_close", reason="unknown query", query_id=query_id, ok=False
                )
            )
        query.open = False
        del self._queries[query_id]
        return self._receipt("query_close", query_id=query_id, ok=True)

    def open_queries(self) -> List[str]:
        return sorted(self._queries)

    # -- ports -------------------------------------------------------------
    def create_port(
        self,
        port_id: str,
        schema: Any,
        owner: str,
        deliver: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if port_id in self._ports:
            raise LiveQFault(
                self._receipt(
                    "port_create", reason="port exists", port_id=port_id, ok=False
                )
            )
        self._ports[port_id] = Port(
            id=port_id, schema=schema, owner=owner, deliver=deliver
        )
        return self._receipt("port_create", port_id=port_id, owner=owner, ok=True)

    def send(self, port_id: str, payload: Any) -> Dict[str, Any]:
        """Validate, cycle-stamp, and enqueue for the next boundary."""
        port = self._ports.get(port_id)
        if port is None:
            raise LiveQFault(
                self._receipt("send", reason="unknown port", port_id=port_id, ok=False)
            )
        problem = _validate_schema(port.schema, payload)
        if problem is not None:
            raise LiveQFault(
                self._receipt(
                    "send_fault",
                    port_id=port_id,
                    reason="schema violation: %s" % problem,
                    ok=False,
                )
            )
        message = {
            "port_id": port_id,
            "payload": copy.deepcopy(payload),
            "cycle": self._cycle,  # quantized: boundary granularity only
            "seq": self._seq + 1,
        }
        receipt = self._receipt("send", port_id=port_id, ok=True)
        message["receipt_id"] = receipt["seq"]
        message["seq"] = receipt["seq"]
        self._queue.append(message)
        return receipt

    # -- hooks -------------------------------------------------------------
    def add_hook(self, hook: CycleHook) -> None:
        self._hooks.append(hook)

    # -- boundary ------------------------------------------------------------
    def boundary_flush(self) -> Dict[str, Any]:
        """One cycle boundary: deliver port messages in (cycle, port_id,
        receipt seq) order, push live-query updates, fire cycle hooks."""
        self._cycle += 1
        delivered_now: List[Dict[str, Any]] = []

        for message in sorted(
            self._queue, key=lambda m: (m["cycle"], m["port_id"], m["seq"])
        ):
            port = self._ports[message["port_id"]]
            if port.deliver is not None:
                port.deliver(copy.deepcopy(message))
            else:
                port.inbox.append(copy.deepcopy(message))
            delivered_now.append(message)
            self._delivered.append(message)
        self._queue = []

        query_deliveries: List[Dict[str, Any]] = []
        for qid in sorted(self._queries):
            query = self._queries[qid]
            if not query.open:
                continue
            new_matches = self._view.match(query.predicate, query.last_version)
            if new_matches:
                query.holder(qid, new_matches)
                query.last_version = self._view.current_version()
                query_deliveries.append(
                    {"query_id": qid, "delivered": len(new_matches)}
                )

        for hook in self._hooks:
            hook.on_boundary(self._cycle)

        return self._receipt(
            "boundary_flush",
            cycle=self._cycle,
            messages_delivered=len(delivered_now),
            queries_updated=len(query_deliveries),
            ok=True,
        )

    def delivery_order(self) -> List[Dict[str, Any]]:
        """Record of every delivered message, in delivery order."""
        return copy.deepcopy(self._delivered)
