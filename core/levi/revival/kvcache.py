"""kvcache — transformer KV cache + paged KV blocks, merged.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.1, §2.2).

Two published mechanisms live here as one merged module, because the
second is the first with an operating system's memory manager bolted on.

1. **KV cache** (the decode trick): a transformer reuses the keys and
   values of every previous token instead of recomputing them. Each
   decode step computes Q only for the new token and attends over the
   cached K/V — decode goes from quadratic recompute to linear streaming
   memory. ``KVCache`` below is the plain contiguous version: per-layer
   lists of (K, V) rows with a single-token decode step.

2. **Paged attention** (the memory-manager trick): instead of one
   contiguous buffer per sequence, the KV cache is cut into fixed-size
   blocks drawn from a global pool. Each sequence carries a block table
   mapping logical block -> physical block, exactly like virtual memory.
   Ref-counting plus copy-on-write lets many sequences share a common
   prefix (the system prompt, the tool definitions, the memory prefix —
   identical across an agent loop's steps) while paying for it once.

This is a small-scale, pure-Python reference. It is honest about being
a teaching and debugging tool, not a production engine: vectors are
plain Python lists, attention is a straightforward softmax, and the
"engine" is simulated. What it demonstrates faithfully is the
accounting — memory bytes, block reuse, ref-counts, CoW copies — which
is where the real wins live.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/kvcache"

FLOAT_BYTES = 4  # reference: fp32 accounting


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _softmax(xs: List[float]) -> List[float]:
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


# ---------------------------------------------------------------------------
# 1. Plain contiguous KV cache
# ---------------------------------------------------------------------------


class KVCache:
    """Per-layer contiguous KV cache with a one-token decode step.

    ``layers`` copies of the same head geometry are kept so the memory
    accounting (layers × heads × seq × head_dim) is faithful; the attention
    itself runs per layer head-averaged for the toy.
    """

    def __init__(self, layers: int, n_heads: int, head_dim: int, seed: int = 7) -> None:
        self.layers = layers
        self.n_heads = n_heads
        self.head_dim = head_dim
        self._rng = random.Random(seed)
        # keys[layer][position] -> vector; values the same.
        self.keys: List[List[List[float]]] = [[] for _ in range(layers)]
        self.values: List[List[List[float]]] = [[] for _ in range(layers)]
        self.decode_steps = 0

    def _project(self, token_id: int, layer: int, kind: str) -> List[float]:
        """Deterministic toy K/V projection of a token id (reference only)."""
        rng = random.Random((token_id * 100003 + layer * 917 + hash(kind)) & 0xFFFFFFFF)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.head_dim)]

    def prefill(self, token_ids: List[int]) -> None:
        """Process the prompt: fill the cache for every layer."""
        for tid in token_ids:
            for layer in range(self.layers):
                self.keys[layer].append(self._project(tid, layer, "k"))
                self.values[layer].append(self._project(tid, layer, "v"))

    def decode_step(self, token_id: int, layer: int = 0) -> List[float]:
        """One decode step: Q for the new token only, attend over cached K/V."""
        q = self._project(token_id, layer, "q")
        scale = 1.0 / math.sqrt(self.head_dim)
        scores = [_dot(q, k) * scale for k in self.keys[layer]]
        weights = _softmax(scores)
        dim = self.head_dim
        out = [0.0] * dim
        for w, v in zip(weights, self.values[layer], strict=True):
            for i in range(dim):
                out[i] += w * v[i]
        # Cache the new token's K/V so the next step can see it.
        self.keys[layer].append(self._project(token_id, layer, "k"))
        self.values[layer].append(self._project(token_id, layer, "v"))
        self.decode_steps += 1
        return out

    def seq_len(self, layer: int = 0) -> int:
        return len(self.keys[layer])

    def bytes(self) -> int:
        """Cached K+V bytes across all layers (fp32 reference accounting)."""
        total_rows = sum(len(k) for k in self.keys) + sum(len(v) for v in self.values)
        return total_rows * self.head_dim * FLOAT_BYTES

    def evict(self, layer: int, keep: int) -> None:
        """Drop oldest rows down to ``keep`` (sliding window / eviction)."""
        self.keys[layer] = self.keys[layer][-keep:]
        self.values[layer] = self.values[layer][-keep:]


# ---------------------------------------------------------------------------
# 2. Paged KV cache: global block pool + block tables + ref-counted sharing
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """One physical block: ``block_size`` consecutive (K, V) rows."""

    block_size: int
    rows: List[Optional[Tuple[List[float], List[float]]]] = field(default_factory=list)
    refcount: int = 0

    def __post_init__(self) -> None:
        if not self.rows:
            self.rows = [None] * self.block_size

    def used(self) -> int:
        return sum(1 for r in self.rows if r is not None)


class PagedKVCache:
    """KV cache as fixed-size blocks in a global pool.

    Each sequence owns a *block table*: logical block index -> physical
    block index. Prefix sharing: ``share_prefix`` makes a new sequence
    whose table points at the same physical blocks (refcount += 1); the
    first write to a shared block triggers a copy-on-write clone.
    """

    def __init__(self, block_size: int = 4, pool_blocks: int = 64) -> None:
        self.block_size = block_size
        self.pool: List[Block] = [Block(block_size) for _ in range(pool_blocks)]
        self.free_list: List[int] = list(range(pool_blocks))
        self.tables: Dict[str, List[int]] = {}  # seq_id -> block table
        self.lengths: Dict[str, int] = {}  # seq_id -> logical length
        self.cow_copies = 0

    # -- pool management ----------------------------------------------------

    def _alloc_block(self) -> int:
        if not self.free_list:
            raise MemoryError("paged KV pool exhausted")
        idx = self.free_list.pop()
        self.pool[idx].refcount = 1
        return idx

    def new_sequence(self, seq_id: str) -> None:
        self.tables[seq_id] = []
        self.lengths[seq_id] = 0

    def _ensure_block(self, seq_id: str, logical: int) -> None:
        table = self.tables[seq_id]
        while len(table) <= logical:
            table.append(self._alloc_block())

    def append(self, seq_id: str, k: List[float], v: List[float]) -> None:
        """Append one token's K/V, with copy-on-write on shared blocks."""
        pos = self.lengths[seq_id]
        logical = pos // self.block_size
        offset = pos % self.block_size
        self._ensure_block(seq_id, logical)
        phys = self.tables[seq_id][logical]
        block = self.pool[phys]
        if block.refcount > 1:
            # Copy-on-write: clone the block, remap, drop our ref.
            new_phys = self._alloc_block()
            new_block = self.pool[new_phys]
            new_block.rows = list(block.rows)
            block.refcount -= 1
            self.tables[seq_id][logical] = new_phys
            phys = new_phys
            block = new_block
            self.cow_copies += 1
        block.rows[offset] = (k, v)
        self.lengths[seq_id] = pos + 1

    def share_prefix(self, src_id: str, dst_id: str, tokens: int) -> None:
        """New sequence sharing ``tokens`` of ``src_id``'s prefix (refcounted)."""
        n_blocks = -(-tokens // self.block_size)
        table = []
        for logical in range(n_blocks):
            phys = self.tables[src_id][logical]
            self.pool[phys].refcount += 1
            table.append(phys)
        self.tables[dst_id] = table
        self.lengths[dst_id] = tokens

    def kv_rows(self, seq_id: str) -> List[Tuple[List[float], List[float]]]:
        rows: List[Tuple[List[float], List[float]]] = []
        table = self.tables[seq_id]
        for pos in range(self.lengths[seq_id]):
            phys = table[pos // self.block_size]
            rows.append(self.pool[phys].rows[pos % self.block_size])  # type: ignore[arg-type]
        return rows

    def decode_step(self, seq_id: str, q: List[float]) -> List[float]:
        """Single-token attention over the paged cache (equivalence check)."""
        rows = self.kv_rows(seq_id)
        scale = 1.0 / math.sqrt(len(q))
        scores = [_dot(q, k) * scale for k, _ in rows]
        weights = _softmax(scores)
        dim = len(q)
        out = [0.0] * dim
        for w, (_, v) in zip(weights, rows, strict=True):
            for i in range(dim):
                out[i] += w * v[i]
        return out

    def free(self, seq_id: str) -> None:
        """Release a sequence's blocks; shared blocks return when last ref drops."""
        for phys in set(self.tables[seq_id]):
            block = self.pool[phys]
            block.refcount -= 1
            if block.refcount == 0:
                block.rows = [None] * self.block_size
                self.free_list.append(phys)
        del self.tables[seq_id]
        del self.lengths[seq_id]

    def used_blocks(self) -> int:
        return len(self.pool) - len(self.free_list)

    def shared_prefix_saving(self, seq_id: str, other_id: str) -> int:
        """Physical blocks the two sequences share (the win of paging)."""
        return len(set(self.tables[seq_id]) & set(self.tables[other_id]))
