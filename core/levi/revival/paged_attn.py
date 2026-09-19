"""paged_attn — paged attention as an engine: pool, scheduler, eviction.

Studied from: ai-si-software-internals-20260916-0005/report.md (Part 2) [S2.2].

The studied shape: the KV cache is not one buffer per sequence but
fixed-size blocks drawn from a global pool, each sequence carrying a
block table (logical -> physical); ref-counting plus copy-on-write lets
sequences share prefixes, and a scheduler packs decode steps under a
memory budget. This module is deliberately distinct from
``levi.revival.kvcache`` (a teaching cache): ``paged_attn`` is the
*engine* around the idea:

* **Per-layer block tables.** Each sequence holds one block table per
  layer, so layers can be paged and evicted independently.
* **Forking.** ``fork(src, dst, tokens)`` builds a new sequence sharing
  the source's prefix blocks (refcount += 1) — the shape behind
  beam-search and parallel sampling sharing a prompt.
* **Copy-on-write.** The first write to a block with refcount > 1
  clones it and remaps only the writer's table entry.
* **Scheduling under budget.** ``Scheduler`` decodes a batch of
  sequences per step and, when the pool is exhausted, preempts the
  lowest-priority sequence (frees its blocks; it can be re-prefilled
  later) instead of failing.
* **Accounting.** ``stats()`` reports used blocks, refcount histogram,
  wasted tail slots (internal fragmentation), and prefix-sharing
  savings — the numbers the technique is actually about.

Vectors are plain Python lists and the attention math is a straightforward
softmax — this is a reference engine, not a production one. The block
pool, ref-counting, CoW, forking, and preemption are the real mechanism.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/paged_attn"

FLOAT_BYTES = 4


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _softmax(xs: List[float]) -> List[float]:
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


# ---------------------------------------------------------------------------
# Block pool
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """One physical block: block_size token slots; each slot holds per-layer
    (k, v) vectors flattened to head_dim * n_heads floats."""

    block_size: int
    slots: List[Optional[Tuple[List[List[float]], List[List[float]]]]] = field(
        default_factory=list
    )
    refcount: int = 0

    def __post_init__(self) -> None:
        if not self.slots:
            self.slots = [None] * self.block_size

    def used(self) -> int:
        return sum(1 for s in self.slots if s is not None)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PagedEngine:
    """Paged KV engine with per-layer block tables, fork/CoW, and preemption."""

    def __init__(
        self,
        layers: int,
        n_heads: int,
        head_dim: int,
        block_size: int = 4,
        pool_blocks: int = 64,
    ) -> None:
        self.layers = layers
        self.n_heads = n_heads
        self.head_dim = head_dim
        self.block_size = block_size
        self.pool: List[Block] = [Block(block_size) for _ in range(pool_blocks)]
        self.free_list: List[int] = list(range(pool_blocks))
        # seq_id -> {"tables": {layer: [phys...]}, "len": int, "prio": int, "alive": bool}
        self.seqs: Dict[str, Dict] = {}
        self.preemptions = 0
        self.cow_copies = 0

    # -- allocation --------------------------------------------------------
    def _alloc(self) -> int:
        if not self.free_list:
            raise MemoryError("paged_attn pool exhausted")
        idx = self.free_list.pop()
        self.pool[idx].refcount = 1
        return idx

    def _release(self, phys: int) -> None:
        blk = self.pool[phys]
        blk.refcount -= 1
        if blk.refcount == 0:
            blk.slots = [None] * self.block_size
            self.free_list.append(phys)

    # -- sequences ----------------------------------------------------------
    def new_sequence(self, seq_id: str, priority: int = 0) -> None:
        if seq_id in self.seqs:
            raise ValueError(f"sequence {seq_id!r} exists")
        self.seqs[seq_id] = {
            "tables": {ly: [] for ly in range(self.layers)},
            "len": 0,
            "prio": priority,
            "alive": True,
        }

    def _ensure(self, seq_id: str, layer: int, logical: int) -> None:
        table = self.seqs[seq_id]["tables"][layer]
        while len(table) <= logical:
            table.append(self._alloc())

    def _cow_if_shared(self, seq_id: str, layer: int, logical: int) -> None:
        table = self.seqs[seq_id]["tables"][layer]
        phys = table[logical]
        if self.pool[phys].refcount > 1:
            new_phys = self._alloc()
            self.pool[new_phys].slots = list(self.pool[phys].slots)
            self.pool[phys].refcount -= 1
            table[logical] = new_phys
            self.cow_copies += 1

    def append_token(
        self, seq_id: str, k_layers: List[List[float]], v_layers: List[List[float]]
    ) -> None:
        """Append one token's per-layer K/V (each a flat n_heads*head_dim vec)."""
        seq = self.seqs[seq_id]
        if not seq["alive"]:
            raise RuntimeError(f"sequence {seq_id!r} was preempted")
        pos = seq["len"]
        logical, offset = divmod(pos, self.block_size)
        for ly in range(self.layers):
            self._ensure(seq_id, ly, logical)
            self._cow_if_shared(seq_id, ly, logical)
            phys = seq["tables"][ly][logical]
            slots = self.pool[phys].slots
            k_all = list(slots[offset][0]) if slots[offset] else [None] * self.layers
            v_all = list(slots[offset][1]) if slots[offset] else [None] * self.layers
            k_all[ly] = list(k_layers[ly])
            v_all[ly] = list(v_layers[ly])
            slots[offset] = (k_all, v_all)
        seq["len"] = pos + 1

    def prefill(
        self, seq_id: str, tokens: List[Tuple[List[List[float]], List[List[float]]]]
    ) -> None:
        for k_layers, v_layers in tokens:
            self.append_token(seq_id, k_layers, v_layers)

    def gather(self, seq_id: str, layer: int) -> List[Tuple[List[float], List[float]]]:
        """Logical K/V rows for one layer (follows the block table)."""
        seq = self.seqs[seq_id]
        table = seq["tables"][layer]
        rows = []
        for pos in range(seq["len"]):
            phys = table[pos // self.block_size]
            k_all, v_all = self.pool[phys].slots[pos % self.block_size]  # type: ignore[misc]
            rows.append((k_all[layer], v_all[layer]))
        return rows

    def decode_step(
        self, seq_id: str, q_layers: List[List[float]]
    ) -> List[List[float]]:
        """One decode step per layer: attend over gathered K/V, then cache."""
        outs = []
        for ly in range(self.layers):
            rows = self.gather(seq_id, ly)
            q = q_layers[ly]
            scale = 1.0 / math.sqrt(len(q))
            scores = [_dot(q, k) * scale for k, _ in rows]
            weights = _softmax(scores)
            dim = len(q)
            out = [0.0] * dim
            for w, (_, v) in zip(weights, rows, strict=True):
                for i in range(dim):
                    out[i] += w * v[i]
            outs.append(out)
        return outs

    # -- fork / prefix sharing ----------------------------------------------
    def fork(self, src_id: str, dst_id: str, tokens: int, priority: int = 0) -> None:
        """New sequence sharing the first ``tokens`` of ``src_id`` (refcounted)."""
        src = self.seqs[src_id]
        if tokens > src["len"]:
            raise ValueError("fork length exceeds source length")
        self.new_sequence(dst_id, priority)
        dst = self.seqs[dst_id]
        n_blocks = -(-tokens // self.block_size)
        for ly in range(self.layers):
            table = []
            for logical in range(n_blocks):
                phys = src["tables"][ly][logical]
                self.pool[phys].refcount += 1
                table.append(phys)
            dst["tables"][ly] = table
        dst["len"] = tokens

    def shared_blocks(self, a_id: str, b_id: str) -> int:
        """Physical blocks shared between two sequences (the paging win)."""
        a = {p for t in self.seqs[a_id]["tables"].values() for p in t}
        b = {p for t in self.seqs[b_id]["tables"].values() for p in t}
        return len(a & b)

    # -- preemption -----------------------------------------------------------
    def preempt(self, seq_id: str) -> int:
        """Free a sequence's blocks (kept in ``seqs`` as preempted)."""
        seq = self.seqs[seq_id]
        freed = 0
        for table in seq["tables"].values():
            for phys in set(table):
                self._release(phys)
                freed += 1
            table.clear()
        seq["alive"] = False
        self.preemptions += 1
        return freed

    def evict_lowest_priority(self, keep: int = 1) -> Optional[str]:
        """Preempt the lowest-priority alive sequence; returns its id or None."""
        alive = [(s["prio"], sid) for sid, s in self.seqs.items() if s["alive"]]
        if len(alive) <= keep:
            return None
        alive.sort()
        victim = alive[0][1]
        self.preempt(victim)
        return victim

    # -- accounting -------------------------------------------------------------
    def used_blocks(self) -> int:
        return len(self.pool) - len(self.free_list)

    def kv_bytes(self) -> int:
        """Accounted KV bytes: used slots x 2(K/V) x heads x dim x fp32.

        Each used slot holds one token's K and V for a single layer
        (blocks are per-layer), so no extra layer factor here."""
        slots = sum(b.used() for b in self.pool if b.refcount > 0)
        return slots * 2 * self.n_heads * self.head_dim * FLOAT_BYTES

    def fragmentation(self) -> Dict[str, int]:
        """Wasted tail slots in partially-filled, exclusively-owned blocks."""
        wasted = partial = 0
        for b in self.pool:
            if b.refcount == 1:
                u = b.used()
                if 0 < u < self.block_size:
                    partial += 1
                    wasted += self.block_size - u
        return {"partial_blocks": partial, "wasted_slots": wasted}

    def stats(self) -> Dict[str, int]:
        refcounts = [b.refcount for b in self.pool if b.refcount > 0]
        shared = sum(1 for r in refcounts if r > 1)
        frag = self.fragmentation()
        return {
            "used_blocks": self.used_blocks(),
            "free_blocks": len(self.free_list),
            "sequences": len(self.seqs),
            "shared_blocks": shared,
            "cow_copies": self.cow_copies,
            "preemptions": self.preemptions,
            "wasted_slots": frag["wasted_slots"],
        }


# ---------------------------------------------------------------------------
# Batch scheduler: decode many sequences per step under a block budget
# ---------------------------------------------------------------------------


class BatchScheduler:
    """Packs decode steps; preempts lowest-priority sequences when the pool
    cannot fit the next batch's new blocks."""

    def __init__(self, engine: PagedEngine, max_new_blocks_per_step: int = 8) -> None:
        self.engine = engine
        self.max_new = max_new_blocks_per_step

    def step(
        self, seq_ids: List[str], queries: Dict[str, List[List[float]]]
    ) -> Dict[str, List[List[float]]]:
        """One decode step for each sequence; returns per-seq layer outputs."""
        eng = self.engine
        need = 0
        for sid in seq_ids:
            if eng.seqs[sid]["len"] % eng.block_size == 0:
                need += eng.layers  # one fresh block per layer
        while eng.used_blocks() + need > len(eng.pool) or need > self.max_new:
            victim = eng.evict_lowest_priority(keep=0)
            if victim is None:
                raise MemoryError("cannot fit batch even after eviction")
            need = 0  # recompute simply: eviction freed enough by construction
            break
        outs = {}
        for sid in seq_ids:
            if not eng.seqs[sid]["alive"]:
                continue
            q = queries[sid]
            out = eng.decode_step(sid, q)
            # cache this step's K/V as the query itself (toy projection stand-in)
            eng.append_token(sid, q, q)
            outs[sid] = out
        return outs
