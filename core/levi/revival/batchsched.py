"""batchsched — continuous batching + chunked prefill + preemption, simulated.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.2).

The vLLM scheduling idea at reference scale, simulated with toy
sequences (no real model, no real GPU — the *decisions* are the
mechanism):

* **Continuous batching**: the scheduler re-decides the batch *every
  decode step*. Finished requests retire immediately and waiting
  requests join mid-flight; there is no "wait for the whole batch to
  finish" barrier. A naive static batcher idles on stragglers; the
  continuous scheduler does not.
* **Chunked prefill**: a long prompt's prefill is split into chunks.
  Each step's token budget serves all active decodes first (one token
  each), and the leftover budget goes to prefill chunks. Decodes never
  starve behind a giant prompt — the head-of-line blocking problem,
  solved by construction.
* **Preemption**: when the paged KV pool runs out of blocks, the
  scheduler frees the lowest-priority running request's blocks and
  requeues it; it recomputes later (cheap when its prefix is shared and
  still cached).

KV memory is modeled with the paged pool from ``kvcache``: each
sequence's tokens occupy blocks, sharing prefixes where they overlap.
``Scheduler`` exposes per-step events so a test can assert the
invariants: decodes never starve, waiting requests eventually join,
preemption frees blocks.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from levi.revival import kvcache

ORIGIN = "levi-revival/batchsched"


@dataclass
class Request:
    """One toy generation request."""

    req_id: str
    prompt_len: int  # tokens to prefill
    max_new_tokens: int  # decode budget
    priority: int = 0  # higher = preempted last
    prefilled: int = 0  # prompt tokens processed so far
    generated: int = 0  # decode tokens emitted so far
    preempted: int = 0  # times this request was preempted

    @property
    def prefill_done(self) -> bool:
        return self.prefilled >= self.prompt_len

    @property
    def done(self) -> bool:
        return self.prefill_done and self.generated >= self.max_new_tokens


@dataclass
class StepEvent:
    step: int
    retired: List[str] = field(default_factory=list)
    admitted: List[str] = field(default_factory=list)
    preempted: List[str] = field(default_factory=list)
    decoded: List[str] = field(default_factory=list)
    prefill_chunks: Dict[str, int] = field(default_factory=dict)
    blocks_used: int = 0
    decode_capable: int = 0  # running requests that could decode this step


class Scheduler:
    """Continuous-batching scheduler over a paged KV pool.

    ``step_budget``: total tokens processed per step. Decodes are served
    first (one token each), then the remainder goes to prefill chunks.
    ``max_running`` caps concurrent sequences.
    """

    def __init__(
        self,
        block_size: int = 4,
        pool_blocks: int = 32,
        step_budget: int = 16,
        max_running: int = 4,
        prefill_chunk: int = 8,
    ) -> None:
        self.kv = kvcache.PagedKVCache(block_size=block_size, pool_blocks=pool_blocks)
        self.step_budget = step_budget
        self.max_running = max_running
        self.prefill_chunk = prefill_chunk
        self.waiting: List[Request] = []
        self.running: List[Request] = []
        self.finished: List[Request] = []
        self.events: List[StepEvent] = []
        self.step = 0

    # -- admission ----------------------------------------------------------

    def submit(self, req: Request) -> None:
        self.waiting.append(req)

    def _admit(self, ev: StepEvent) -> None:
        """Admit waiting requests mid-flight while the batch has room."""
        while self.waiting and len(self.running) < self.max_running:
            req = self.waiting.pop(0)
            self.kv.new_sequence(req.req_id)
            self.running.append(req)
            ev.admitted.append(req.req_id)

    # -- preemption ----------------------------------------------------------

    def _preempt_lowest(self) -> Optional[Request]:
        """Free the lowest-priority running request's blocks; requeue it."""
        if not self.running:
            return None
        victim = min(self.running, key=lambda r: (r.priority, -r.generated))
        self.kv.free(victim.req_id)
        self.running.remove(victim)
        victim.prefilled = 0  # recompute on re-admission
        victim.preempted += 1
        self.waiting.insert(0, victim)
        return victim

    def _kv_row(self, req: Request, pos: int) -> tuple:
        # Deterministic toy K/V so the paged pool holds real content.
        import random

        rng = random.Random(hash((req.req_id, pos)) & 0xFFFFFFFF)
        return [rng.uniform(-1, 1) for _ in range(8)], [
            rng.uniform(-1, 1) for _ in range(8)
        ]

    # -- the step ------------------------------------------------------------

    def run_step(self) -> StepEvent:
        """One scheduler iteration: retire, admit, decode, chunk prefill."""
        self.step += 1
        ev = StepEvent(step=self.step)

        # 1. Retire finished requests, freeing their blocks immediately.
        for req in [r for r in self.running if r.done]:
            self.kv.free(req.req_id)
            self.running.remove(req)
            self.finished.append(req)
            ev.retired.append(req.req_id)

        # 2. Admit waiting requests into the freed slots (mid-flight join).
        self._admit(ev)
        ev.decode_capable = sum(
            1 for r in self.running if r.prefill_done and not r.done
        )

        # 3. Decodes first: one token per running request that finished prefill.
        budget = self.step_budget
        for req in list(self.running):
            if budget <= 0:
                break
            if req.prefill_done and not req.done:
                k, v = self._kv_row(req, req.prefilled + req.generated)
                try:
                    self.kv.append(req.req_id, k, v)
                except MemoryError:
                    victim = self._preempt_lowest()
                    if victim is not None:
                        ev.preempted.append(victim.req_id)
                    # Retry admission next step; this decode waits.
                    continue
                req.generated += 1
                budget -= 1
                ev.decoded.append(req.req_id)

        # 4. Leftover budget goes to prefill, chunked per request.
        for req in list(self.running):
            if budget <= 0 or req.prefill_done:
                continue
            chunk = min(self.prefill_chunk, req.prompt_len - req.prefilled, budget)
            for i in range(chunk):
                k, v = self._kv_row(req, req.prefilled + i)
                try:
                    self.kv.append(req.req_id, k, v)
                except MemoryError:
                    victim = self._preempt_lowest()
                    if victim is not None:
                        ev.preempted.append(victim.req_id)
                    break
                req.prefilled += 1
                budget -= 1
            ev.prefill_chunks[req.req_id] = chunk

        ev.blocks_used = self.kv.used_blocks()
        self.events.append(ev)
        return ev

    def run_until_done(self, max_steps: int = 10_000) -> List[StepEvent]:
        """Drive the scheduler until every submitted request finishes."""
        while (self.waiting or self.running) and self.step < max_steps:
            self.run_step()
        return self.events

    # -- invariants for tests -------------------------------------------------

    def decodes_never_starved(self) -> bool:
        """Decodes are never blocked by prefill: any step with a
        decode-capable request either decoded something or preempted."""
        for ev in self.events:
            if ev.decode_capable > 0 and not ev.decoded and not ev.preempted:
                return False
        return True
