"""Streaming data pipeline for LEVI's native brain v2.

Reads a JSONL corpus (``{"text": ...}`` records, e.g. ``corpus.jsonl``) as a
stream, tokenizes on the fly, and packs documents into fixed-length training
batches with document-boundary awareness:

- Every document's tokens are followed by the tokenizer's ``<eod>`` id.
- Each batch carries ``segment_ids`` (one integer per token position marking
  which document the token belongs to).
- With ``isolate_docs=True`` (default) each batch also carries an additive
  attention mask that is causal *and* block-diagonal over documents, so no
  token can attend across a document boundary — no cross-document
  contamination. Set ``isolate_docs=False`` for plain causal packing.

Also supports:
- curriculum ordering: an ordered manifest (JSON) of stages, each naming
  doc ids; documents stream in stage order. Unlisted docs come first
  (stage -1) and this is documented, not hidden.
- on-the-fly validation split: docs are routed to train/val by a stable
  hash of their doc id, so the split is deterministic across runs and
  needs no second pass over the data.

Batches are dicts: ``input_ids`` (B, T), ``labels`` (B, T),
``segment_ids`` (B, T), ``attn_mask`` (B, 1, T, T) or None.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import torch

if __package__:
    from .tok import ByteBPETokenizer
else:  # imported as a top-level module (tests, standalone scripts)
    from tok import ByteBPETokenizer

CHUNK_OVERLAP_NOTE = (
    "Chunks are block_size+1 tokens so labels are the input shifted by one."
)


def stable_hash01(key: str) -> float:
    """Deterministic [0, 1) hash for split routing."""
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def doc_boundary_mask(segment_ids: torch.Tensor) -> torch.Tensor:
    """Additive mask: causal AND block-diagonal over documents.

    segment_ids: (B, T) long. Returns (B, 1, T, T) float with 0.0 for
    allowed positions and -inf for blocked ones (future positions, or
    positions belonging to a different document).
    """
    B, T = segment_ids.shape
    causal = torch.full((T, T), float("-inf")).triu(1)  # (T, T)
    same_doc = segment_ids[:, None, :] == segment_ids[:, :, None]  # (B, T, T)
    doc_block = torch.zeros((B, T, T))
    doc_block[~same_doc] = float("-inf")
    return (causal[None, None, :, :] + doc_block[:, None, :, :]).to(torch.float32)


def iter_jsonl_docs(path: str | Path, text_field: str = "text"):
    """Yield (doc_id, text) streaming, one JSON record per line."""
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get(text_field, "")
            if not text:
                continue
            yield str(rec.get("id", f"doc-{i}")), text


class Curriculum:
    """Ordered manifest: {"stages": [{"name": str, "doc_ids": [str, ...]}, ...]}.

    Documents are streamed stage by stage (stage 0, then 1, ...). Doc ids not
    named in the manifest form stage -1 and stream FIRST. Within a stage the
    order is the manifest's order (or ``shuffle_within_stage``).
    """

    def __init__(
        self, manifest: str | Path | dict, shuffle_within_stage=False, seed: int = 1337
    ):
        if isinstance(manifest, (str, Path)):
            manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
        self.stages: list[dict] = manifest.get("stages", [])
        self.shuffle_within_stage = shuffle_within_stage
        self.seed = seed
        self._stage_of: dict[str, tuple[int, int]] = {}
        for si, stage in enumerate(self.stages):
            for oi, did in enumerate(stage.get("doc_ids", [])):
                # first mention wins; duplicates are a manifest bug, not fatal
                self._stage_of.setdefault(str(did), (si, oi))

    def order_key(self, doc_id: str, file_seq: int) -> tuple[int, int]:
        stage, pos = self._stage_of.get(str(doc_id), (-1, file_seq))
        return (stage, pos)

    def stage_of(self, doc_id: str) -> int:
        return self._stage_of.get(str(doc_id), (-1, 0))[0]


class DataPipeline:
    """Streaming tokenized batching with doc-boundary-aware packing."""

    def __init__(
        self,
        corpus: str | Path,
        tokenizer: ByteBPETokenizer,
        block_size: int = 512,
        batch_size: int = 8,
        val_fraction: float = 0.02,
        seed: int = 1337,
        curriculum: Curriculum | None = None,
        isolate_docs: bool = True,
        shuffle_buffer: int = 512,
        prepend_doc_token: bool = False,
        text_field: str = "text",
    ):
        self.corpus = Path(corpus)
        self.tok = tokenizer
        self.block_size = block_size
        self.batch_size = batch_size
        self.val_fraction = val_fraction
        self.seed = seed
        self.curriculum = curriculum
        self.isolate_docs = isolate_docs
        self.shuffle_buffer = shuffle_buffer
        self.prepend_doc_token = prepend_doc_token
        self.text_field = text_field
        self._plan: list[tuple[tuple[int, int], str, int]] | None = None

    # ------------------------------------------------------------ planning

    def _build_plan(self) -> list[tuple[tuple[int, int], str, int]]:
        """One indexing pass: (order_key, doc_id, file_offset) per document.

        Offsets let later passes seek straight to a document, so curriculum
        ordering and train/val routing never hold the corpus in memory.
        """
        if self._plan is not None:
            return self._plan
        plan: list[tuple[tuple[int, int], str, int]] = []
        seen: set[str] = set()
        with open(self.corpus, encoding="utf-8") as fh:
            seq = 0
            while True:
                offset = fh.tell()
                line = fh.readline()
                if not line:
                    break
                s = line.strip()
                if not s:
                    continue
                try:
                    rec = json.loads(s)
                except json.JSONDecodeError:
                    continue
                text = rec.get(self.text_field, "")
                if not text:
                    continue
                doc_id = str(rec.get("id", f"doc-{seq}"))
                seq += 1
                if doc_id in seen:  # duplicate id: keep first occurrence
                    continue
                seen.add(doc_id)
                key = (
                    self.curriculum.order_key(doc_id, seq)
                    if self.curriculum
                    else (0, seq)
                )
                plan.append((key, doc_id, offset))
        plan.sort(key=lambda e: e[0])
        self._plan = plan
        return plan

    def _is_val(self, doc_id: str) -> bool:
        return stable_hash01(f"val-split:{doc_id}") < self.val_fraction

    def _read_doc_at(self, offset: int) -> str:
        with open(self.corpus, encoding="utf-8") as fh:
            fh.seek(offset)
            rec = json.loads(fh.readline())
            return rec.get(self.text_field, "")

    def _encode_doc(self, text: str) -> list[int]:
        ids = self.tok.encode(text)
        if self.prepend_doc_token:
            ids = [self.tok.doc_id] + ids
        return ids + [self.tok.eod_id]

    # ------------------------------------------------------------ batching

    def _chunk_stream(self, want_val: bool):
        """Yield (input_ids, labels, segment_ids) chunks, streaming."""
        plan = self._build_plan()
        tokens: list[int] = []
        segs: list[int] = []
        seg_counter = 0
        need = self.block_size + 1  # +1 so labels = inputs shifted by one
        for _, doc_id, offset in plan:
            if self._is_val(doc_id) != want_val:
                continue
            ids = self._encode_doc(self._read_doc_at(offset))
            tokens.extend(ids)
            segs.extend([seg_counter] * len(ids))
            seg_counter += 1
            while len(tokens) >= need:
                chunk_t = tokens[:need]
                chunk_s = segs[:need]
                tokens = tokens[need:]
                segs = segs[need:]
                x = torch.tensor(chunk_t[:-1], dtype=torch.long)
                y = torch.tensor(chunk_t[1:], dtype=torch.long)
                s = torch.tensor(chunk_s[:-1], dtype=torch.long)
                yield x, y, s
        # trailing partial chunk is dropped (standard practice; documented)

    def _batch_stream(self, want_val: bool, shuffle: bool):
        buf: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
        rng = random.Random(self.seed + (1 if want_val else 0))
        B = self.batch_size

        def make_batch(items):
            xs = torch.stack([it[0] for it in items])
            ys = torch.stack([it[1] for it in items])
            ss = torch.stack([it[2] for it in items])
            mask = doc_boundary_mask(ss) if self.isolate_docs else None
            return {
                "input_ids": xs,
                "labels": ys,
                "segment_ids": ss,
                "attn_mask": mask,
            }

        for item in self._chunk_stream(want_val):
            if shuffle:
                buf.append(item)
                if len(buf) >= self.shuffle_buffer:
                    rng.shuffle(buf)
                    while len(buf) >= B:
                        yield make_batch([buf.pop() for _ in range(B)])
            else:
                buf.append(item)
                if len(buf) == B:
                    yield make_batch(buf)
                    buf = []
        if shuffle:
            rng.shuffle(buf)
        while len(buf) >= B:
            yield make_batch([buf.pop(0) for _ in range(B)])
        # leftover partial batch is dropped

    def iter_train(self, shuffle: bool = True):
        """Yield training batches (dicts)."""
        yield from self._batch_stream(want_val=False, shuffle=shuffle)

    def iter_val(self, max_batches: int | None = None):
        """Yield validation batches in deterministic order."""
        n = 0
        for b in self._batch_stream(want_val=True, shuffle=False):
            yield b
            n += 1
            if max_batches is not None and n >= max_batches:
                break

    # ------------------------------------------------------------ introspection

    def stats(self) -> dict:
        plan = self._build_plan()
        n_val = sum(1 for _, did, _ in plan if self._is_val(did))
        stages: dict[int, int] = {}
        for (stage, _), _did, _ in plan:
            stages[stage] = stages.get(stage, 0) + 1
        return {
            "documents": len(plan),
            "train_documents": len(plan) - n_val,
            "val_documents": n_val,
            "val_fraction_target": self.val_fraction,
            "block_size": self.block_size,
            "batch_size": self.batch_size,
            "isolate_docs": self.isolate_docs,
            "curriculum_stages": stages,
        }
