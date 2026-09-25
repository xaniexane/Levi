"""Streaming batch-1 trainer skeleton for LEVI's native brain.

Interpenetration piece 3 of 3: the mini-AGI *direction* (train on a
continuous stream, batch-1, on consumer hardware) as loop structure
over LEVI's real data path.

What this is
------------
- :func:`stream_char_batches`: stdlib generator yielding batch-1
  ``(x_ids, y_ids)`` pairs from a text stream, packed to
  ``block_size`` with document-boundary awareness (a document never
  leaks into the next chunk's labels). Char-level, using the trained
  char vocab — the same level tiny-gpt learned at.
- :class:`StreamingSkeleton`: the train loop as structure — stream a
  batch, forward, cross-entropy loss, log. **No weight updates.**
  Real updates need autograd (torch); this skeleton proves the loop
  plumbing runs and shows exactly where the optimizer step plugs in
  (see ``TODO: optimizer step``).

What this is not
----------------
- Not a trainer. No gradients, no optimizer, no checkpointing here.
  The real training path stays ``core/levi/brain/train/`` (torch) and
  Brain V2 stays stopped per the hard limit.
- When torch IS available, the production streamer is
  ``train/data_pipe.py`` (BPE, curriculum, doc isolation). This
  module documents that handoff in :func:`torch_stream_batches`.

Stdlib-only at import; numpy is imported lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


def _np():
    import numpy as np  # lazy: kernel stays stdlib-only at import

    return np


def stream_char_batches(
    text: str,
    char_to_id: Dict[str, int],
    block_size: int,
    unk_id: int = 0,
) -> Iterator[Tuple[List[int], List[int]]]:
    """Yield batch-1 (x, y) pairs; y is x shifted by one.

    The stream is cut at ``block_size`` *documents* — here one text is
    one document, chunked so no chunk's labels cross a chunk boundary
    (each chunk is block_size+1 ids; x = ids[:-1], y = ids[1:]).
    Deterministic: pure function of the inputs.
    """
    ids = [char_to_id.get(c, unk_id) for c in text]
    step = block_size  # non-overlapping chunks; labels never cross chunks
    for start in range(0, len(ids) - 1, step):
        chunk = ids[start : start + block_size + 1]
        if len(chunk) < 2:
            break
        yield chunk[:-1], chunk[1:]


def torch_stream_batches(*args: Any, **kwargs: Any) -> Iterator[Any]:
    """Handoff point: the torch data path (``train/data_pipe.py``).

    Raises a clear error naming the real module instead of silently
    degrading. Structure, not a fallback.
    """
    raise NotImplementedError(
        "batch streaming with BPE + curriculum lives in "
        "levi.brain.train.data_pipe (torch). This skeleton covers the "
        "stdlib/numpy loop structure only."
    )


@dataclass
class StepLog:
    step: int
    loss: float
    tokens: int


class StreamingSkeleton:
    """The batch-1 streaming loop as structure.

    ``forward_fn(ids) -> logits`` is any callable returning (T, vocab)
    logits — e.g. ``levi.brain.runtime._forward_numpy`` partially bound
    to params and config. ``step`` runs forward + cross-entropy and
    logs; weight updates are future work (marked in code).
    """

    def __init__(
        self,
        forward_fn: Callable[[List[int]], Any],
        vocab_size: int,
    ) -> None:
        self.forward_fn = forward_fn
        self.vocab_size = vocab_size
        self.history: List[StepLog] = []

    def loss(self, x_ids: List[int], y_ids: List[int]) -> float:
        """Cross-entropy of next-id prediction. Forward + loss only."""
        np = _np()
        logits = np.asarray(self.forward_fn(x_ids), dtype=np.float64)
        y = np.asarray(y_ids, dtype=np.int64)
        m = logits.max(axis=-1, keepdims=True)
        logp = logits - m - np.log(np.exp(logits - m).sum(axis=-1, keepdims=True))
        nll = -logp[np.arange(len(y)), y]
        return float(nll.mean())

    def step(self, x_ids: List[int], y_ids: List[int]) -> StepLog:
        """One streaming step: forward, loss, log. No weight update."""
        loss = self.loss(x_ids, y_ids)
        # TODO: optimizer step — needs autograd (torch). The loop order
        # is: forward -> loss -> backward -> optimizer.step -> zero_grad.
        # This skeleton proves stream -> forward -> loss runs; the
        # backward half stays in train/ where torch lives.
        entry = StepLog(step=len(self.history), loss=loss, tokens=len(x_ids))
        self.history.append(entry)
        return entry

    def run(
        self,
        batches: Iterator[Tuple[List[int], List[int]]],
        max_steps: Optional[int] = None,
    ) -> List[StepLog]:
        """Drain a batch stream through :meth:`step`."""
        for x, y in batches:
            self.step(x, y)
            if max_steps is not None and len(self.history) >= max_steps:
                break
        return self.history
