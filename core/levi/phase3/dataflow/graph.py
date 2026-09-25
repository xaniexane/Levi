"""Dataflow firing-rule execution — the act step's semantics.

WORKING TITLE only — naming is Chauncey's, never canon.

B11: multi-step plans compile to DAGs; a node fires iff all its input
edges hold values, ties broken by node-id order.  Malformed plans
(cycles, missing producers, unknown ops) are rejected at build time —
never discovered mid-execution.  Node ops execute through a
verb-dispatch callable injected at construction (default: a test
double; ready to accept the B10 ``operate()`` later).

Stdlib-only. Zero network. No sentience or subjective-experience
claims: a firing is an execution, not a decision.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class DataflowFault(Exception):
    """A receipted dataflow fault.  The receipt is on ``.receipt``."""

    def __init__(self, receipt: Dict[str, Any]):
        self.receipt = receipt
        super().__init__(str(receipt.get("reason", "dataflow fault")))


def _now() -> str:
    # Timestamps live ONLY inside receipts; logic never reads them.
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Graph model
# ---------------------------------------------------------------------------


@dataclass
class Node:
    id: str
    op: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    budget: int = 1


@dataclass
class Graph:
    nodes: Dict[str, Node]
    # edge name -> {"producer": node_id | None, "consumers": [node_id]}
    edges: Dict[str, Dict[str, Any]]
    external_inputs: List[str]
    sink_outputs: List[str]


# ---------------------------------------------------------------------------
# PlanList adapter (thin; until the middle pins its act protocol)
# ---------------------------------------------------------------------------


class PlanList:
    """Takes ``(node_id, op, inputs, outputs)`` rows; ``build()`` compiles
    them to a validated :class:`Graph`."""

    def __init__(self):
        self._items: List[Tuple[Any, ...]] = []

    def add(
        self,
        node_id: str,
        op: str,
        inputs: Iterable[str],
        outputs: Iterable[str],
        budget: int = 1,
    ) -> "PlanList":
        self._items.append((node_id, op, list(inputs), list(outputs), budget))
        return self

    def build(
        self, known_ops: Iterable[str], external_inputs: Iterable[str] = ()
    ) -> Graph:
        return build_graph(self._items, known_ops, external_inputs)


# ---------------------------------------------------------------------------
# Build + validate
# ---------------------------------------------------------------------------


def build_graph(
    plan: Iterable[Tuple[Any, ...]],
    known_ops: Iterable[str],
    external_inputs: Iterable[str] = (),
) -> Graph:
    """Compile plan rows to a graph, rejecting malformed plans at build.

    Build faults: duplicate node ids, unknown ops, duplicate producers,
    missing producers (non-external input edges with no producer),
    cycles, bad budgets.
    """
    known = set(known_ops)
    external = list(external_inputs)
    nodes: Dict[str, Node] = {}
    edges: Dict[str, Dict[str, Any]] = {}

    def edge(name: str) -> Dict[str, Any]:
        return edges.setdefault(name, {"producer": None, "consumers": []})

    def fault(reason: str, **kw: Any) -> DataflowFault:
        return DataflowFault({"op": "build", "reason": reason, "ts": _now(), **kw})

    for row in plan:
        if len(row) not in (4, 5):
            raise fault("bad plan row", row=list(row))
        node_id, op, inputs, outputs = row[0], row[1], list(row[2]), list(row[3])
        budget = row[4] if len(row) == 5 else 1
        if node_id in nodes:
            raise fault("duplicate node id", node_id=node_id)
        if op not in known:
            raise fault("unknown op", node_id=node_id, op_name=op)
        if not isinstance(budget, int) or budget < 0:
            raise fault("bad budget", node_id=node_id, budget=budget)
        node = Node(id=node_id, op=op, inputs=inputs, outputs=outputs, budget=budget)
        nodes[node_id] = node
        for name in outputs:
            info = edge(name)
            if info["producer"] is not None:
                raise fault(
                    "duplicate producer",
                    edge=name,
                    producers=[info["producer"], node_id],
                )
            info["producer"] = node_id
        for name in inputs:
            edge(name)["consumers"].append(node_id)

    for name, info in edges.items():
        if info["producer"] is None and name not in external:
            raise fault(
                "missing producer",
                edge=name,
                consumers=info["consumers"],
            )

    # Acyclicity via Kahn's algorithm over node dependencies.
    deps: Dict[str, set] = {nid: set() for nid in nodes}
    for _name, info in edges.items():
        producer = info["producer"]
        if producer is None:
            continue
        for consumer in info["consumers"]:
            if consumer != producer:
                deps[consumer].add(producer)
    remaining = {nid: set(d) for nid, d in deps.items()}
    order: List[str] = []
    while True:
        free = sorted(n for n, d in remaining.items() if not d)
        if not free:
            break
        nxt = free[0]
        order.append(nxt)
        del remaining[nxt]
        for d in remaining.values():
            d.discard(nxt)
    if remaining:
        raise fault("cycle detected", nodes=sorted(remaining))

    sinks = [name for name, info in edges.items() if not info["consumers"]]
    return Graph(nodes=nodes, edges=edges, external_inputs=external, sink_outputs=sinks)


def validate(graph: Graph) -> Dict[str, Any]:
    """Re-run the build-time checks on an existing graph (idempotent)."""
    rows = [(n.id, n.op, n.inputs, n.outputs, n.budget) for n in graph.nodes.values()]
    known = {n.op for n in graph.nodes.values()}
    rebuilt = build_graph(rows, known, graph.external_inputs)
    return {
        "op": "validate",
        "ok": True,
        "nodes": len(rebuilt.nodes),
        "edges": len(rebuilt.edges),
        "ts": _now(),
    }


# ---------------------------------------------------------------------------
# Verb-dispatch test double (default; B10 operate() plugs in later)
# ---------------------------------------------------------------------------


class TestDoubleDispatch:
    """Default verb-dispatch: op name -> callable ``fn(inputs, outputs)``.

    ``fn`` receives the input edge values and the node's declared output
    edge names, and returns ``{edge: value}`` covering every declared
    output.  Every firing is audit-logged in the uniform B10 shape
    ``{namespace, verb, target, args}`` so T6 holds end to end.
    """

    __test__ = False  # helper, not a pytest test class

    def __init__(self, namespace: str = "dataflow-test"):
        self.namespace = namespace
        self._ops: Dict[str, Callable[[Dict[str, Any], List[str]], Dict[str, Any]]] = {}
        self.audit: List[Dict[str, Any]] = []
        self._seq = 0

    def register(
        self, op_name: str, fn: Callable[[Dict[str, Any], List[str]], Dict[str, Any]]
    ) -> None:
        self._ops[op_name] = fn

    @property
    def known_ops(self) -> set:
        return set(self._ops)

    def __call__(
        self, op: str, input_values: Dict[str, Any], output_names: List[str]
    ) -> Dict[str, Any]:
        self._seq += 1
        self.audit.append(
            {
                "namespace": self.namespace,
                "verb": "run",
                "target": "/tools/%s" % op,
                "args": copy.deepcopy(input_values),
                "receipt_id": self._seq,
                "ok": True,
                "ts": _now(),
            }
        )
        try:
            fn = self._ops[op]
        except KeyError:
            raise DataflowFault(
                {
                    "op": "dispatch",
                    "reason": "unknown op at runtime",
                    "op_name": op,
                    "ts": _now(),
                }
            ) from None
        try:
            produced = fn(dict(input_values), list(output_names))
        except Exception as exc:
            raise DataflowFault(
                {
                    "op": "dispatch",
                    "reason": "op failed: %s" % exc,
                    "op_name": op,
                    "ts": _now(),
                }
            ) from None
        if not isinstance(produced, dict):
            raise DataflowFault(
                {
                    "op": "dispatch",
                    "reason": "op must return a dict of edge values",
                    "op_name": op,
                    "ts": _now(),
                }
            )
        return produced


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@dataclass
class ExecutionTrace:
    fire_order: List[str]
    node_records: List[Dict[str, Any]]
    outputs: Dict[str, Any]
    receipts: List[Dict[str, Any]]

    def annotated(self) -> Dict[str, Any]:
        """The graph annotated with fire order — mechanically replayable."""
        return {
            "fire_order": list(self.fire_order),
            "node_records": copy.deepcopy(self.node_records),
            "outputs": copy.deepcopy(self.outputs),
        }


def execute(
    graph: Graph,
    inputs: Dict[str, Any],
    dispatch: Optional[
        Callable[[str, Dict[str, Any], List[str]], Dict[str, Any]]
    ] = None,
) -> ExecutionTrace:
    """Run the firing rule to completion.  Deterministic: same graph +
    same inputs -> same fire order and outputs, bit-identical."""
    validate(graph)
    dispatch = dispatch or TestDoubleDispatch()

    def fault(reason: str, **kw: Any) -> DataflowFault:
        return DataflowFault({"op": "execute", "reason": reason, "ts": _now(), **kw})

    missing = [e for e in graph.external_inputs if e not in inputs]
    if missing:
        raise fault("missing external inputs", edges=missing)
    values: Dict[str, Any] = {
        e: copy.deepcopy(inputs[e]) for e in graph.external_inputs
    }
    fired: set = set()
    fire_order: List[str] = []
    node_records: List[Dict[str, Any]] = []
    receipts: List[Dict[str, Any]] = []
    seq = 0

    while True:
        ready = sorted(
            n.id
            for n in graph.nodes.values()
            if n.id not in fired and all(e in values for e in n.inputs)
        )
        if not ready:
            if len(fired) == len(graph.nodes):
                break
            raise fault(
                "unfireable remainder",
                unfired=sorted(set(graph.nodes) - fired),
                reason_detail="build-time analysis missed it",
            )
        node_id = ready[0]  # deterministic tie-break: node-id order
        node = graph.nodes[node_id]
        in_values = {e: values[e] for e in node.inputs}
        produced = dispatch(node.op, in_values, node.outputs)
        absent = [e for e in node.outputs if e not in produced]
        if absent:
            raise fault(
                "op did not produce declared outputs",
                node_id=node_id,
                edges=absent,
            )
        for e in node.outputs:
            values[e] = copy.deepcopy(produced[e])
        fired.add(node_id)
        fire_order.append(node_id)
        seq += 1
        record = {
            "seq": seq,
            "node_id": node_id,
            "op": node.op,
            "inputs": copy.deepcopy(in_values),
            "outputs": {e: copy.deepcopy(produced[e]) for e in node.outputs},
            "ts": _now(),
        }
        node_records.append(record)
        receipts.append(record)

    outputs = {e: copy.deepcopy(values[e]) for e in graph.sink_outputs}
    return ExecutionTrace(
        fire_order=fire_order,
        node_records=node_records,
        outputs=outputs,
        receipts=receipts,
    )


def replay(
    graph: Graph,
    trace: ExecutionTrace,
    inputs: Dict[str, Any],
    dispatch: Optional[
        Callable[[str, Dict[str, Any], List[str]], Dict[str, Any]]
    ] = None,
) -> ExecutionTrace:
    """Re-execute and demand fire order + outputs identical to ``trace``."""
    fresh = execute(graph, inputs, dispatch)
    if fresh.fire_order != trace.fire_order:
        raise DataflowFault(
            {
                "op": "replay",
                "reason": "fire order diverged",
                "want": trace.fire_order,
                "got": fresh.fire_order,
                "ts": _now(),
            }
        )
    if fresh.outputs != trace.outputs:
        raise DataflowFault(
            {
                "op": "replay",
                "reason": "outputs diverged",
                "want": trace.outputs,
                "got": fresh.outputs,
                "ts": _now(),
            }
        )
    return fresh


__all__ = [
    "DataflowFault",
    "ExecutionTrace",
    "Graph",
    "Node",
    "PlanList",
    "TestDoubleDispatch",
    "build_graph",
    "execute",
    "replay",
    "validate",
]
