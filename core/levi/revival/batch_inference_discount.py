"""batch_inference_discount — batch windows that cut delay-tolerant API spend.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§4 — modern UUCP analog].

Shape studied: real-time inference spend gets 30–50% cheaper when the
work is delay-tolerant enough to be scheduled in batches rather than
fired off immediately.

Mechanism (heuristic pricing, no real API calls):
* every request carries prompt/completion token counts and a delay
  tolerance — how long it may wait, in minutes
* batch tiering: >=10 min → 30% off, >=60 min → 40%, >=240 min → 50% off
* BatchWindow collects requests and releases a batch when it reaches the
  target size OR the earliest deadline is approaching — realtime requests
  (tolerance 0) never wait in a batch
* SavingsReport compares the all-realtime bill against the scheduled bill

Honest limits: discount tiers and the per-token price are configurable
heuristics modeled on public batch-inference pricing shapes, not quotes.
The scheduler is a deterministic simulation — it *decides* batching, it
never calls any inference API.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/batch_inference_discount"

#: Heuristic blended price: dollars per 1,000 tokens (prompt + completion).
PRICE_PER_KTOK = 1.00

#: (minimum delay tolerance in minutes, discount fraction), highest first.
BATCH_TIERS = (
    (240.0, 0.50),
    (60.0, 0.40),
    (10.0, 0.30),
)


@dataclass(frozen=True)
class InferenceRequest:
    """One unit of delay-tolerant inference work."""

    request_id: str
    prompt_tokens: int
    max_tokens: int
    tolerance_min: float = 0.0
    submitted_at: float = 0.0  # minutes on the scheduler's clock

    @property
    def deadline(self) -> float:
        return self.submitted_at + self.tolerance_min

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.max_tokens


@dataclass
class Batch:
    """A released group of requests, priced at one tier."""

    requests: List[InferenceRequest] = field(default_factory=list)
    discount: float = 0.0

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.requests)


def discount_for(tolerance_min: float) -> float:
    """Discount fraction earned by a delay tolerance (heuristic tiers)."""
    for floor, discount in BATCH_TIERS:
        if tolerance_min >= floor:
            return discount
    return 0.0


def price(
    tokens: int, discount: float, price_per_ktok: float = PRICE_PER_KTOK
) -> float:
    """Dollar price for ``tokens`` at a discount fraction."""
    if tokens < 0:
        raise ValueError("tokens must be >= 0")
    if not 0.0 <= discount <= 1.0:
        raise ValueError("discount must be within [0, 1]")
    return tokens / 1000.0 * price_per_ktok * (1.0 - discount)


class BatchWindow:
    """Collects requests, releases batches on size or approaching deadline.

    Realtime requests (``tolerance_min == 0``) are never held: they are
    returned as singleton batches at their full-discount tier (0.0) on the
    next ``collect`` call.
    """

    def __init__(self, target_batch_size: int = 8, urgency_margin_min: float = 2.0):
        if target_batch_size < 1:
            raise ValueError("target_batch_size must be >= 1")
        self.target_batch_size = target_batch_size
        self.urgency_margin_min = urgency_margin_min
        self._waiting: List[InferenceRequest] = []

    def submit(self, request: InferenceRequest) -> None:
        if any(r.request_id == request.request_id for r in self._waiting):
            raise ValueError(f"duplicate request_id {request.request_id!r}")
        self._waiting.append(request)

    def pending(self) -> int:
        return len(self._waiting)

    def collect(self, now_min: float) -> List[Batch]:
        """Release due batches as of ``now_min``. Returns released batches.

        Realtime requests go out immediately as singleton full-price
        batches. The rest accumulate in deadline order and release when
        the batch reaches target size or the earliest deadline is near.
        """
        realtime = [r for r in self._waiting if r.tolerance_min <= 0]
        waiting = sorted(
            (r for r in self._waiting if r.tolerance_min > 0),
            key=lambda r: r.deadline,
        )
        released = [Batch(requests=[r], discount=0.0) for r in realtime]
        batch: List[InferenceRequest] = []
        remaining: List[InferenceRequest] = []
        for req in waiting:
            batch.append(req)
            urgent = req.deadline <= now_min + self.urgency_margin_min
            if len(batch) >= self.target_batch_size or urgent:
                released.append(
                    Batch(
                        requests=batch,
                        discount=discount_for(min(r.tolerance_min for r in batch)),
                    )
                )
                batch = []
        remaining = batch
        self._waiting = remaining
        return released

    def flush(self) -> List[Batch]:
        """Release everything still waiting, grouped by earned tier."""
        groups: Dict[float, List[InferenceRequest]] = {}
        for req in self._waiting:
            if req.tolerance_min <= 0:
                groups.setdefault(0.0, []).append(req)
            else:
                groups.setdefault(discount_for(req.tolerance_min), []).append(req)
        self._waiting = []
        return [Batch(requests=rs, discount=d) for d, rs in sorted(groups.items())]


@dataclass
class SavingsReport:
    """All-realtime bill vs the scheduled bill, for one run of batches."""

    realtime_cost: float
    scheduled_cost: float
    requests: int
    batched: int

    @property
    def saved(self) -> float:
        return self.realtime_cost - self.scheduled_cost

    @property
    def savings_fraction(self) -> float:
        if self.realtime_cost <= 0:
            return 0.0
        return self.saved / self.realtime_cost


def report(
    batches: List[Batch], price_per_ktok: float = PRICE_PER_KTOK
) -> SavingsReport:
    """Build a SavingsReport from released batches."""
    realtime = 0.0
    scheduled = 0.0
    requests = 0
    batched = 0
    for batch in batches:
        for req in batch.requests:
            realtime += price(req.total_tokens, 0.0, price_per_ktok)
            scheduled += price(req.total_tokens, batch.discount, price_per_ktok)
            requests += 1
            if batch.discount > 0:
                batched += 1
    return SavingsReport(
        realtime_cost=realtime,
        scheduled_cost=scheduled,
        requests=requests,
        batched=batched,
    )
