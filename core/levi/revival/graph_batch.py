"""graph_batch — the model as a per-batch compute graph, scheduled by hand.

Studied from: ai-si-software-internals-20260916-0005/report.md (Part 2) [S2.2].

The studied shape: instead of a fixed pipeline, the model for each
batch is a compute graph; a backend scheduler places graph nodes across
processors (CPU/GPU/Metal), offloads some layers elsewhere, and mixes
precisions — the same graph, different placements per batch. LEVI's
version:

* **Graph.** ``Node``s (``const``, ``add``, ``mul``, ``matmul``,
  ``softmax``, ``relu``, ``layernorm``, ``linear``) form a DAG over
  tensors (nested Python lists). ``Graph.forward()`` evaluates in
  topological order and returns the output tensor.
* **Placement.** ``Scheduler`` assigns each node to a backend
  (``"cpu"`` / ``"gpu"``) under an offload policy: ``offload_every=k``
  moves every k-th linear layer to the slower backend, modeling
  per-layer offload without any real device.
* **Mixed precision.** Each node carries a dtype (``fp32``/``fp16``);
  ``memory_bytes()`` accounts 4 vs 2 bytes per element, and a policy
  can quantize a subgraph — the arithmetic stays fp32 (honest: this is
  a scheduling/accounting reference), the *budget* reflects the mix.
* **Per-batch rebuild.** ``build_mlp`` constructs a fresh graph per
  batch configuration, mirroring the "graph per batch" idea.

Honest limits: no real accelerators, no real fp16 arithmetic — tensors
are Python lists and placement affects only the reported plan and byte
budget, not speed. What is real: the graph semantics, the topological
evaluation, the placement decisions, and the accounting.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/graph_batch"

CPU = "cpu"
GPU = "gpu"
DTYPE_BYTES = {"fp32": 4, "fp16": 2}


# ---------------------------------------------------------------------------
# Tiny tensor helpers (nested lists)
# ---------------------------------------------------------------------------


def _shape(t: Any) -> Tuple[int, ...]:
    s = []
    while isinstance(t, list):
        s.append(len(t))
        t = t[0] if t else None
    return tuple(s)


def _numel(shape: Tuple[int, ...]) -> int:
    n = 1
    for d in shape:
        n *= d
    return n


def _add(a: Any, b: Any) -> Any:
    if isinstance(a, list):
        return [_add(x, y) for x, y in zip(a, b, strict=True)]
    return a + b


def _matvec(m: List[List[float]], v: List[float]) -> List[float]:
    return [sum(x * y for x, y in zip(row, v, strict=True)) for row in m]


def _matmul(a: Any, b: Any) -> Any:
    # batched: a is [B, M], b is [M, N] -> [B, N]
    bt = list(zip(*b, strict=True))
    return [
        [sum(x * y for x, y in zip(row, col, strict=True)) for col in bt] for row in a
    ]


def _softmax_row(row: List[float]) -> List[float]:
    m = max(row)
    exps = [math.exp(x - m) for x in row]
    s = sum(exps)
    return [e / s for e in exps]


def _relu(t: Any) -> Any:
    if isinstance(t, list):
        return [_relu(x) for x in t]
    return max(0.0, t)


def _layernorm(t: List[float], eps: float = 1e-5) -> List[float]:
    mean = sum(t) / len(t)
    var = sum((x - mean) ** 2 for x in t) / len(t)
    return [(x - mean) / math.sqrt(var + eps) for x in t]


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """One compute node: op, input node names, constant payload, dtype."""

    name: str
    op: str  # const|add|mul|matmul|softmax|relu|layernorm|linear
    inputs: Tuple[str, ...] = ()
    payload: Any = None  # const tensor | linear (weight, bias)
    dtype: str = "fp32"
    layer: int = -1  # layer index, for offload policies

    def output_shape(self, shapes: Dict[str, Tuple[int, ...]]) -> Tuple[int, ...]:
        if self.op == "const":
            return _shape(self.payload)
        if self.op in ("add", "mul"):
            return shapes[self.inputs[0]]
        if self.op == "matmul":
            b, m = shapes[self.inputs[0]]
            _, n = shapes[self.inputs[1]]
            return (b, n)
        if self.op == "linear":
            w, _ = self.payload
            bsz = shapes[self.inputs[0]][0]
            return (bsz, len(w))
        if self.op in ("softmax", "relu", "layernorm"):
            return shapes[self.inputs[0]]
        raise ValueError(f"unknown op {self.op!r}")


class Graph:
    """A per-batch compute graph: build, place, evaluate."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.placement: Dict[str, str] = {}

    def add(self, node: Node) -> "Graph":
        if node.name in self.nodes:
            raise ValueError(f"duplicate node {node.name!r}")
        self.nodes[node.name] = node
        return self

    def topo(self) -> List[Node]:
        order: List[Node] = []
        seen: Dict[str, str] = {}

        def visit(name: str) -> None:
            mark = seen.get(name)
            if mark == "done":
                return
            if mark == "visiting":
                raise ValueError(f"cycle at {name!r}")
            if name not in self.nodes:
                raise ValueError(f"unknown input {name!r}")
            seen[name] = "visiting"
            for dep in self.nodes[name].inputs:
                visit(dep)
            seen[name] = "done"
            order.append(self.nodes[name])

        for name in self.nodes:
            visit(name)
        return order

    def forward(self, feeds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate in topological order; returns every node's tensor."""
        values: Dict[str, Any] = dict(feeds or {})
        for node in self.topo():
            if node.name in values:  # fed input overrides const
                continue
            ins = [values[i] for i in node.inputs]
            if node.op == "const":
                values[node.name] = node.payload
            elif node.op == "add":
                values[node.name] = _add(ins[0], ins[1])
            elif node.op == "mul":
                values[node.name] = _elemul(ins[0], ins[1])
            elif node.op == "matmul":
                values[node.name] = _matmul(ins[0], ins[1])
            elif node.op == "softmax":
                values[node.name] = [_softmax_row(r) for r in ins[0]]
            elif node.op == "relu":
                values[node.name] = _relu(ins[0])
            elif node.op == "layernorm":
                values[node.name] = [_layernorm(r) for r in ins[0]]
            elif node.op == "linear":
                w, b = node.payload
                out = _matmul(ins[0], w)
                values[node.name] = [
                    [x + bi for x, bi in zip(r, b, strict=True)] for r in out
                ]
            else:
                raise ValueError(f"unknown op {node.op!r}")
        return values

    def memory_bytes(self) -> int:
        """Weight + activation footprint under the current dtype mix."""
        shapes: Dict[str, Tuple[int, ...]] = {}
        total = 0
        for node in self.topo():
            shapes[node.name] = node.output_shape(shapes)
            total += _numel(shapes[node.name]) * DTYPE_BYTES[node.dtype]
        return total


def _elemul(a: Any, b: Any) -> Any:
    if isinstance(a, list):
        return [_elemul(x, y) for x, y in zip(a, b, strict=True)]
    return a * b


# ---------------------------------------------------------------------------
# Scheduler: placement + mixed precision
# ---------------------------------------------------------------------------


@dataclass
class Schedule:
    placement: Dict[str, str]
    bytes_cpu: int = 0
    bytes_gpu: int = 0


class Scheduler:
    """Place nodes on backends; quantize a subgraph to fp16 on request."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def place(self, default: str = GPU, offload_every: int = 0) -> Schedule:
        """Assign backends. ``offload_every=k``: every k-th linear layer -> cpu.

        ``offload_every=0`` disables offloading (everything on ``default``).
        """
        placement: Dict[str, str] = {}
        for node in self.graph.topo():
            backend = default
            if (
                offload_every > 0
                and node.op == "linear"
                and node.layer >= 0
                and (node.layer + 1) % offload_every == 0
            ):
                backend = CPU if default == GPU else GPU
            placement[node.name] = backend
        self.graph.placement = placement
        sched = Schedule(placement=placement)
        # naive byte split: activations counted per placement
        shapes: Dict[str, Tuple[int, ...]] = {}
        for node in self.graph.topo():
            shapes[node.name] = node.output_shape(shapes)
            b = _numel(shapes[node.name]) * DTYPE_BYTES[node.dtype]
            if placement[node.name] == CPU:
                sched.bytes_cpu += b
            else:
                sched.bytes_gpu += b
        return sched

    def quantize(self, layer_from: int, dtype: str = "fp16") -> None:
        """Set dtype for nodes at/after a layer (mixed-precision policy)."""
        for node in self.graph.nodes.values():
            if node.layer >= layer_from:
                node.dtype = dtype


# ---------------------------------------------------------------------------
# Builder: a fresh graph per batch (a tiny MLP)
# ---------------------------------------------------------------------------


def build_mlp(batch: int, dims: List[int], seed: int = 11) -> Tuple[Graph, str]:
    """Build a per-batch MLP graph: input -> [linear, relu]* -> linear.

    Returns (graph, output_node_name). Weights are deterministic from seed.
    """
    rng = random.Random(seed)
    g = Graph()
    g.add(Node("x", "const", payload=[[0.0] * dims[0] for _ in range(batch)]))
    prev, prev_dim = "x", dims[0]
    out_name = "x"
    for li, dim in enumerate(dims[1:]):
        w = [[rng.uniform(-0.5, 0.5) for _ in range(dim)] for _ in range(prev_dim)]
        b = [0.0] * dim
        lin = f"lin{li}"
        act = f"act{li}"
        g.add(Node(lin, "linear", inputs=(prev,), payload=(w, b), layer=li))
        last = li == len(dims) - 2
        if not last:
            g.add(Node(act, "relu", inputs=(lin,), layer=li))
            prev = act
        else:
            prev = lin
        prev_dim = dim
        out_name = prev
    return g, out_name


def feed_input(graph: Graph, name: str, tensor: List[List[float]]) -> Dict[str, Any]:
    """Evaluate the graph with an external input tensor for ``name``."""
    return graph.forward(feeds={name: tensor})
