"""Vector index structures from scratch: HNSW, IVF, and product quantization.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.6)

Functional description: approximate nearest-neighbor indexes built from
scratch in pure Python at reference scale — correct structure, honest
small-corpus behavior, documented scale limits (noted per class).

- HNSW: multi-layer navigable small-world graph. Nodes get a random level
  (exponential decay); greedy descent from the top layer, then a beam
  search on layer 0. ``ef_search`` is the recall↔latency dial.
- IVF: k-means partition of the space into cells; search probes the
  ``nprobe`` nearest cells.
- ProductQuantizer: splits vectors into sub-vectors, learns a small
  codebook per subspace, encodes each vector as byte codes — memory wins,
  with asymmetric distance computation for search.
- DiskANN: deliberately a DESIGN SKETCH in the docstring below, not a fake
  implementation. LEVI does not claim to have built what it has not.

No provider branding, no network, no LLaMA. Not artificial — synthetic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

ORIGIN = "levi-revival/vecindex"

Vector = List[float]


def euclid(a: Vector, b: Vector) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=False)))


# --------------------------------------------------------------------------
# HNSW
# --------------------------------------------------------------------------


class HNSW:
    """Hierarchical Navigable Small World graph.

    Reference-scale: linear scans inside the beam search keep it correct on
    toy corpora; on millions of vectors a production port would need
    compressed adjacency and batch distance kernels. This class is the
    structure, honestly measured — check ``recall_at_k`` on your data.
    """

    def __init__(
        self, dim: int, m: int = 8, ef_construction: int = 40, seed: int = 7
    ) -> None:
        self.dim = dim
        self.m = m  # max neighbors per node per layer
        self.ef_construction = ef_construction
        self.rng = random.Random(seed)
        self.levels: List[int] = []
        self.vectors: List[Vector] = []
        # layers[node][layer] -> list of neighbor ids
        self.layers: List[List[List[int]]] = []
        self.entry = -1

    def _random_level(self) -> int:
        level = 0
        while self.rng.random() < 0.5 and level < 8:
            level += 1
        return level

    def _search_layer(
        self, q: Vector, entry: int, layer: int, ef: int
    ) -> List[Tuple[float, int]]:
        visited = {entry}
        cands: List[Tuple[float, int]] = [(euclid(q, self.vectors[entry]), entry)]
        best: List[Tuple[float, int]] = list(cands)
        while cands:
            cands.sort(key=lambda p: p[0])
            dist, node = cands.pop(0)
            worst = max(d for d, _ in best) if best else float("inf")
            if dist > worst:
                break
            for nb in self.layers[node][layer]:
                if nb in visited:
                    continue
                visited.add(nb)
                d = euclid(q, self.vectors[nb])
                if len(best) < ef or d < worst:
                    best.append((d, nb))
                    best.sort(key=lambda p: p[0])
                    best = best[:ef]
                    cands.append((d, nb))
        best.sort(key=lambda p: p[0])
        return best

    def add(self, vec: Vector) -> int:
        idx = len(self.vectors)
        self.vectors.append(list(vec))
        level = self._random_level()
        self.levels.append(level)
        self.layers.append([[] for _ in range(level + 1)])
        if self.entry == -1:
            self.entry = idx
            return idx
        # greedy descent from top
        cur = self.entry
        for layer in range(len(self.layers[cur]) - 1, level, -1):
            changed = True
            while changed:
                changed = False
                d0 = euclid(vec, self.vectors[cur])
                for nb in self.layers[cur][layer]:
                    d = euclid(vec, self.vectors[nb])
                    if d < d0:
                        d0, cur, changed = d, nb, True
        # connect on each layer <= level
        for layer in range(min(level, len(self.layers[cur]) - 1), -1, -1):
            cands = self._search_layer(vec, cur, layer, self.ef_construction)
            for _d, nb in cands[: self.m]:
                self.layers[idx][layer].append(nb)
                self.layers[nb][layer].append(idx)
                # prune to m
                if len(self.layers[nb][layer]) > self.m:
                    scored = sorted(
                        (euclid(self.vectors[nb], self.vectors[x]), x)
                        for x in self.layers[nb][layer]
                    )
                    self.layers[nb][layer] = [x for _d, x in scored[: self.m]]
            if cands:
                cur = cands[0][1]
        if level > len(self.layers[self.entry]) - 1:
            self.entry = idx
        return idx

    def search(
        self, q: Vector, k: int = 5, ef_search: int = 20
    ) -> List[Tuple[int, float]]:
        """``ef_search`` is the recall↔latency dial: larger = better recall."""
        if self.entry == -1:
            return []
        cur = self.entry
        for layer in range(len(self.layers[cur]) - 1, 0, -1):
            changed = True
            while changed:
                changed = False
                d0 = euclid(q, self.vectors[cur])
                for nb in self.layers[cur][layer]:
                    d = euclid(q, self.vectors[nb])
                    if d < d0:
                        d0, cur, changed = d, nb, True
        best = self._search_layer(q, cur, 0, max(ef_search, k))
        return [(idx, d) for d, idx in best[:k]]


# --------------------------------------------------------------------------
# IVF (k-means partition)
# --------------------------------------------------------------------------


class IVFIndex:
    """Inverted-file index: k-means cells, ``nprobe`` nearest probed.

    Reference-scale k-means with k-means++ seeding. Honest note: exact
    recall needs nprobe == nlist; production systems tune nprobe against a
    recall target on real data.
    """

    def __init__(
        self, nlist: int = 8, nprobe: int = 2, iters: int = 12, seed: int = 7
    ) -> None:
        self.nlist = nlist
        self.nprobe = nprobe
        self.iters = iters
        self.rng = random.Random(seed)
        self.centroids: List[Vector] = []
        self.cells: Dict[int, List[int]] = {}
        self.vectors: List[Vector] = []

    def _kmeans_pp(self, vecs: List[Vector], k: int) -> List[Vector]:
        centers = [list(self.rng.choice(vecs))]
        while len(centers) < k:
            dists = [min(euclid(v, c) ** 2 for c in centers) for v in vecs]
            total = sum(dists)
            if total == 0:
                centers.append(list(self.rng.choice(vecs)))
                continue
            r = self.rng.random() * total
            acc = 0.0
            for v, d in zip(vecs, dists, strict=False):
                acc += d
                if acc >= r:
                    centers.append(list(v))
                    break
        return centers

    def train(self, vecs: Sequence[Vector]) -> None:
        vecs = [list(v) for v in vecs]
        k = min(self.nlist, len(vecs))
        centers = self._kmeans_pp(vecs, k)
        for _ in range(self.iters):
            assign: List[List[Vector]] = [[] for _ in range(k)]
            for v in vecs:
                c = min(range(k), key=lambda i: euclid(v, centers[i]))
                assign[c].append(v)
            for i in range(k):
                if assign[i]:
                    centers[i] = [
                        sum(col) / len(assign[i])
                        for col in zip(*assign[i], strict=False)
                    ]
        self.centroids = centers
        self.cells = {i: [] for i in range(k)}
        for idx, v in enumerate(vecs):
            c = min(range(k), key=lambda i: euclid(v, centers[i]))
            self.cells[c].append(idx)
        self.vectors = vecs

    def search(
        self, q: Vector, k: int = 5, nprobe: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        if not self.centroids:
            return []
        np = nprobe if nprobe is not None else self.nprobe
        order = sorted(
            range(len(self.centroids)), key=lambda i: euclid(q, self.centroids[i])
        )[:np]
        cands: List[Tuple[int, float]] = []
        for cell in order:
            for idx in self.cells[cell]:
                cands.append((idx, euclid(q, self.vectors[idx])))
        cands.sort(key=lambda p: p[1])
        return cands[:k]


# --------------------------------------------------------------------------
# Product quantization
# --------------------------------------------------------------------------


class ProductQuantizer:
    """Splits vectors into ``m`` subspaces, learns ``ks`` centroids each.

    Each vector encodes to ``m`` bytes. Asymmetric distance: the query stays
    full-precision; distances to codebook entries are precomputed per query,
    so a code's distance is a table lookup + sum.
    """

    def __init__(
        self, m: int = 4, ks: int = 16, iters: int = 10, seed: int = 7
    ) -> None:
        self.m = m
        self.ks = ks
        self.iters = iters
        self.rng = random.Random(seed)
        self.codebooks: List[List[Vector]] = []  # m x ks x subdim
        self.codes: List[List[int]] = []
        self.dim = 0

    def _sub(self, v: Vector, s: int) -> Vector:
        n = self.dim // self.m
        return v[s * n : (s + 1) * n]

    def train(self, vecs: Sequence[Vector]) -> None:
        vecs = [list(v) for v in vecs]
        self.dim = len(vecs[0])
        assert self.dim % self.m == 0, "dim must split evenly into m subspaces"
        self.codebooks = []
        for s in range(self.m):
            subs = [self._sub(v, s) for v in vecs]
            k = min(self.ks, len(subs))
            # tiny k-means (reuse the idea, local loop)
            centers = [list(x) for x in self.rng.sample(subs, k)]
            for _ in range(self.iters):
                assign: List[List[Vector]] = [[] for _ in range(k)]
                for x in subs:
                    c = min(range(k), key=lambda i: euclid(x, centers[i]))
                    assign[c].append(x)
                for i in range(k):
                    if assign[i]:
                        centers[i] = [
                            sum(col) / len(assign[i])
                            for col in zip(*assign[i], strict=False)
                        ]
            self.codebooks.append(centers)

    def encode(self, vec: Vector) -> List[int]:
        return [
            min(range(len(cb)), key=lambda i: euclid(self._sub(vec, s), cb[i]))
            for s, cb in enumerate(self.codebooks)
        ]

    def add(self, vecs: Sequence[Vector]) -> None:
        self.codes = [self.encode(v) for v in vecs]

    def asymmetric_distances(self, q: Vector) -> List[float]:
        """ADC: precompute q-vs-codebook tables, then lookup+sum per code."""
        tables = []
        for s, cb in enumerate(self.codebooks):
            qs = self._sub(q, s)
            tables.append([euclid(qs, c) ** 2 for c in cb])
        return [
            math.sqrt(sum(tables[s][code] for s, code in enumerate(code)))
            for code in self.codes
        ]

    def search(self, q: Vector, k: int = 5) -> List[Tuple[int, float]]:
        dists = self.asymmetric_distances(q)
        order = sorted(range(len(dists)), key=lambda i: dists[i])
        return [(i, dists[i]) for i in order[:k]]


# --------------------------------------------------------------------------
# IVF-PQ combined
# --------------------------------------------------------------------------


@dataclass
class IVFPQIndex:
    """IVF coarse partition + PQ-encoded residuals in each cell."""

    ivf: IVFIndex = field(default_factory=IVFIndex)
    pq: ProductQuantizer = field(default_factory=ProductQuantizer)

    def train(self, vecs: Sequence[Vector]) -> None:
        self.ivf.train(vecs)
        residuals = []
        for v in self.ivf.vectors:
            cell = min(
                range(len(self.ivf.centroids)),
                key=lambda i: euclid(v, self.ivf.centroids[i]),
            )
            residuals.append(
                [a - b for a, b in zip(v, self.ivf.centroids[cell], strict=False)]
            )
        self.pq.train(residuals)
        self.pq.add(residuals)

    def search(
        self, q: Vector, k: int = 5, nprobe: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        if not self.ivf.centroids:
            return []
        np = nprobe if nprobe is not None else self.ivf.nprobe
        order = sorted(
            range(len(self.ivf.centroids)),
            key=lambda i: euclid(q, self.ivf.centroids[i]),
        )[:np]
        cands: List[Tuple[int, float]] = []
        for cell in order:
            qres = [a - b for a, b in zip(q, self.ivf.centroids[cell], strict=False)]
            dists = self.pq.asymmetric_distances(qres)
            for pos, idx in enumerate(self.ivf.cells[cell]):
                cands.append((idx, dists[pos]))
        cands.sort(key=lambda p: p[1])
        return cands[:k]


# --------------------------------------------------------------------------
# DiskANN — DESIGN SKETCH ONLY (deliberately not implemented)
# --------------------------------------------------------------------------
#
# DiskANN (graph-based SSD index) is recorded here as a design sketch so
# LEVI never claims an implementation it does not have:
#
#   - Graph: a Vamana-style directed graph over the corpus, each node with a
#     bounded out-degree R, built by greedy search + robust pruning
#     (keep an edge u->v only if no already-kept neighbor w of u is closer
#     to v than u is, times an alpha slack).
#   - Storage: full-precision vectors live on SSD in page-aligned blocks;
#     a small in-memory PQ-compressed copy serves the beam search.
#   - Search: beam search (beam width L) over the compressed vectors,
#     re-ranking the final candidate set against full vectors read from
#     disk with as few random reads as the beam allows.
#   - Why not built here: honest DiskANN needs an SSD page cache, async
#     I/O, and billion-scale validation — none of which a reference-scale
#     pure-Python module can meaningfully demonstrate. HNSW above covers
#     the graph-search idea; PQ above covers the compression idea.
