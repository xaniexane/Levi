"""Service bounties — the bounty hunter's case file.

A bounty is a problem + terms: hunt the problem, deliver a DETAILED and
ACCURATE solution, secure payment for the services. Bounties can be
registered manually or sensed from DemandPulse opportunities (composed,
not duplicated — see :func:`sense_bounties`).

State machine (forward-only, fail-closed):

    draft -> open -> quoted -> agreed -> hunting -> delivered -> paid
      |        |        |        |          |           |
      +--------+--------+--------+----------+-----------+-> cancelled
                                     delivered -> disputed -> hunting

The no-fabrication guard: nothing reaches ``delivered`` without a real
solution, real evidence, an honest confidence number, and verification
notes. The hunter wins on accuracy, not pressure — never manipulative.

Quotes are quotes, not charges: :func:`quote_bounty` composes the
founder-level price advisor for doctrine-compliant pricing advice; no
money moves. All money movement goes through the Cybrus money gateway
(``levi.cybrus.money``) — see :mod:`levi.bounty.payment`.

stdlib-only. Case files live at ``~/.levi/bounty/hunts.jsonl``,
owner-only (0o700 / 0o600).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME", str(Path.home() / ".levi")))


def _data_dir(home: Optional[Path] = None) -> Path:
    p = (home or _home()) / "bounty"
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p, 0o700)
    return p


def _hunts_path(home: Optional[Path] = None) -> Path:
    return _data_dir(home) / "hunts.jsonl"


class BountyError(ValueError):
    """A bounty operation was refused."""


class BountyState(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    QUOTED = "quoted"
    AGREED = "agreed"
    HUNTING = "hunting"
    DELIVERED = "delivered"
    PAID = "paid"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


# Forward-only transitions. PAID and CANCELLED are terminal.
_TRANSITIONS: Dict[BountyState, frozenset] = {
    BountyState.DRAFT: frozenset({BountyState.OPEN, BountyState.CANCELLED}),
    BountyState.OPEN: frozenset({BountyState.QUOTED, BountyState.CANCELLED}),
    BountyState.QUOTED: frozenset({BountyState.AGREED, BountyState.CANCELLED}),
    BountyState.AGREED: frozenset({BountyState.HUNTING, BountyState.CANCELLED}),
    BountyState.HUNTING: frozenset(
        {BountyState.DELIVERED, BountyState.DISPUTED, BountyState.CANCELLED}
    ),
    BountyState.DELIVERED: frozenset({BountyState.PAID, BountyState.DISPUTED}),
    BountyState.DISPUTED: frozenset({BountyState.HUNTING, BountyState.CANCELLED}),
    BountyState.PAID: frozenset(),
    BountyState.CANCELLED: frozenset(),
}


@dataclass
class Bounty:
    """One hunt: a problem, its terms, and the trail to payment."""

    id: str
    title: str
    problem: str
    scope: str = ""
    deadline: str = ""
    client: str = ""
    state: str = BountyState.DRAFT.value
    quote_usd: Optional[float] = None
    price_rationale: str = ""
    solution: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: Optional[float] = None  # honest 0..1, None = unstated
    verification: str = ""  # how the solution was verified
    payment_plan: Optional[Dict[str, Any]] = None  # gateway MoneyPlan dict
    payment_plan_id: str = ""
    payment_receipt: Optional[Dict[str, Any]] = None  # gateway receipt
    payment_state: str = "none"  # none | quoted | agreed | delivered | paid
    sensed_from: str = ""  # DemandPulse opportunity id, if sensed
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise BountyError("bounty id must be non-empty")
        if not self.title or not self.title.strip():
            raise BountyError("bounty title must be non-empty")
        if self.state not in {s.value for s in BountyState}:
            raise BountyError(f"unknown bounty state {self.state!r}")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise BountyError(
                f"confidence must be 0..1, got {self.confidence!r}"
            )

    def log(self, event: str, detail: str = "") -> None:
        self.history.append({"ts": _utcnow(), "event": event, "detail": detail})
        self.updated_at = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Bounty":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def new_bounty(
    title: str,
    problem: str,
    *,
    scope: str = "",
    deadline: str = "",
    client: str = "",
    sensed_from: str = "",
) -> Bounty:
    """Register a bounty manually (starts as a draft)."""
    if not problem or not problem.strip():
        raise BountyError("a bounty needs a real problem statement")
    b = Bounty(
        id="bnty_" + uuid.uuid4().hex[:10],
        title=title.strip(),
        problem=problem.strip(),
        scope=scope.strip(),
        deadline=deadline.strip(),
        client=client.strip(),
        sensed_from=sensed_from.strip(),
    )
    b.log("registered", "bounty registered as draft")
    return b


def transition(bounty: Bounty, to: BountyState, *, note: str = "") -> Bounty:
    """Move a bounty forward one step. Guards enforced; backward moves refuse."""
    if isinstance(to, str):
        to = BountyState(to)
    cur = BountyState(bounty.state)
    if to not in _TRANSITIONS[cur]:
        raise BountyError(
            f"bounty {bounty.id}: cannot move {cur.value} -> {to.value} "
            f"(allowed: {sorted(s.value for s in _TRANSITIONS[cur]) or 'none — terminal'})"
        )
    _guard(bounty, cur, to, note)
    bounty.state = to.value
    bounty.log("state", f"{cur.value} -> {to.value}" + (f": {note}" if note else ""))
    return bounty


def _guard(bounty: Bounty, cur: BountyState, to: BountyState, note: str) -> None:
    if to is BountyState.OPEN and not bounty.problem.strip():
        raise BountyError("cannot open a bounty with an empty problem statement")
    if to is BountyState.QUOTED:
        if bounty.quote_usd is None or bounty.quote_usd <= 0:
            raise BountyError("cannot move to quoted without a price — run quote first")
        if not bounty.price_rationale.strip():
            raise BountyError("cannot move to quoted without pricing rationale")
    if to is BountyState.AGREED and not note.strip():
        raise BountyError("agreement requires a recorded note (who agreed, to what terms)")
    if to is BountyState.DELIVERED:
        # The no-fabrication guard: a delivery must be REAL.
        if not bounty.solution.strip():
            raise BountyError("cannot deliver without a solution — no fabricated results")
        if not bounty.evidence:
            raise BountyError("cannot deliver without evidence — claims must be verifiable")
        if bounty.confidence is None:
            raise BountyError("cannot deliver without an honest confidence number")
        if not bounty.verification.strip():
            raise BountyError("cannot deliver without verification notes")
    if to is BountyState.PAID and not bounty.payment_receipt:
        raise BountyError(
            "cannot mark paid without a Cybrus gateway receipt — "
            "payment is confirmed through Cybrus only"
        )
    if to in (BountyState.DISPUTED, BountyState.CANCELLED) and not note.strip():
        raise BountyError(f"{to.value} requires a recorded reason")


def quote_bounty(
    bounty: Bounty,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    founder_commission: float = 0.0,
) -> Bounty:
    """Price the hunt via the founder-level price advisor.

    A QUOTE, not a charge: advises doctrine-compliant pricing (no free
    core, ~30-60% below giants, volume over margin). Moves nothing.
    """
    from levi.advisor.pricing import PricePlan, advise_price

    advice = advise_price(
        PricePlan(
            tier="entry",
            giant_price=giant_price,
            strategy=strategy,
            founder_commission=founder_commission,
        )
    )
    bounty.quote_usd = advice.recommended
    bounty.price_rationale = "; ".join(advice.rationale) or "doctrine anchors"
    bounty.log(
        "quoted",
        f"advisor quote ${advice.low:.2f}-${advice.high:.2f}, "
        f"recommended ${advice.recommended:.2f} (quote, not a charge)",
    )
    return transition(bounty, BountyState.QUOTED)


def sense_bounties(
    min_worth: float = 0.5, *, pulse: Optional[Any] = None
) -> List[Bounty]:
    """Sense bounty drafts from DemandPulse opportunities.

    Composes DemandPulse's scouting — it does not duplicate it. Returns
    DRAFT bounties; nothing is registered until the hunter says so.
    """
    from levi.demand.pulse import DemandPulse

    dp = pulse if pulse is not None else DemandPulse()
    drafts: List[Bounty] = []
    for opp in getattr(dp, "opportunities", []):
        try:
            worth = float(opp.worth)
        except Exception:
            continue
        if worth < min_worth:
            continue
        b = new_bounty(
            title=getattr(opp, "title", "sensed opportunity"),
            problem=(
                f"Sensed demand: {getattr(opp, 'title', '')}. "
                f"{getattr(opp, 'notes', '')}".strip()
            ),
            sensed_from=getattr(opp, "id", ""),
        )
        b.log("sensed", f"from DemandPulse opportunity {b.sensed_from} (worth {worth:.2f})")
        drafts.append(b)
    return drafts


class BountyStore:
    """Append-and-rewrite JSONL case file, owner-only."""

    def __init__(self, home: Optional[Path] = None):
        self.path = _hunts_path(home)
        if not self.path.exists():
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(fd)
        else:
            os.chmod(self.path, 0o600)

    def _read_all(self) -> Dict[str, Bounty]:
        out: Dict[str, Bounty] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                b = Bounty.from_dict(json.loads(line))
            except Exception:
                continue  # one corrupt line must not kill the file
            out[b.id] = b
        return out

    def _write_all(self, items: Dict[str, Bounty]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for b in items.values():
                fh.write(json.dumps(b.to_dict()) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def add(self, bounty: Bounty) -> Bounty:
        items = self._read_all()
        if bounty.id in items:
            raise BountyError(f"bounty {bounty.id} already registered")
        items[bounty.id] = bounty
        self._write_all(items)
        return bounty

    def save(self, bounty: Bounty) -> Bounty:
        items = self._read_all()
        items[bounty.id] = bounty
        self._write_all(items)
        return bounty

    def get(self, bounty_id: str) -> Bounty:
        items = self._read_all()
        try:
            return items[bounty_id]
        except KeyError:
            raise BountyError(f"unknown bounty {bounty_id!r}") from None

    def list(self, state: Optional[str] = None) -> List[Bounty]:
        items = list(self._read_all().values())
        if state:
            items = [b for b in items if b.state == state]
        return sorted(items, key=lambda b: b.created_at)


__all__ = [
    "Bounty",
    "BountyError",
    "BountyState",
    "BountyStore",
    "new_bounty",
    "transition",
    "quote_bounty",
    "sense_bounties",
]
