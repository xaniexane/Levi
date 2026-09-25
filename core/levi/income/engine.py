"""Income portfolio engine — the 100-slot generator registry.

Canon (Chauncey, 2026-09-17):
- 50-100 automated income generators, all original/unique/from-scratch.
- Free to run / self-sufficient: zero operating cost, local-first, stdlib.
- 30% of every income event reinvests (premium/paid needs Chauncey
  approves); 70% to Chauncey.
- Money law: all money paths go through the Cybrus MoneyGateway ONLY.
  Income events are RECORDED here; nothing moves until Chauncey registers
  a rail (the gateway is fail-closed).
- Pricing doctrine: no free core, entry $1-5, ~30-60% below giants.

Honest architecture:
- Generators automate the WORK (produce real artifacts, run real logic).
  They return WorkReports: what was produced + an honest quoted amount.
- Income events are recorded ONLY with basis="confirmed" — a human
  (Chauncey) confirming money arrived. The engine never invents income.
- The 70/30 split applies at record time. The 30% pool allocates; spending
  it requires Chauncey's explicit approval and executes through the
  MoneyGateway (fail-closed, no rails).

Batches register generators from their own ``gen_<batch>.py`` modules via
:func:`register` with their assigned slot (1-100). ``discover()`` imports
every ``gen_*.py`` module in this package.
"""

from __future__ import annotations

import importlib
import json
import os
import pkgutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MAX_SLOTS = 100

KEEPER_SHARE = 0.70
POOL_SHARE = 0.30

KINDS = (
    "micro-tool",
    "content-engine",
    "audit-service",
    "template-pack",
    "data-product",
    "automation-service",
)

INCOME_KINDS = ("sale", "recurring", "payout")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _home_dir() -> Path:
    return Path(os.environ.get("LEVI_HOME", str(Path.home()))) / ".levi" / "income"


def _runs_path() -> Path:
    return _home_dir() / "runs.jsonl"


def _events_path() -> Path:
    return _home_dir() / "events.jsonl"


def _pool_path() -> Path:
    return _home_dir() / "pool.jsonl"


def _write_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


@dataclass
class WorkReport:
    """What one generator run actually produced (never income)."""

    generator_id: str
    produced: List[str] = field(default_factory=list)
    quoted_amount_usd: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Generator:
    """One automated income generator.

    ``run`` receives a ctx dict ({"levi_home": Path, "dry_run": bool,
    "params": dict}) and returns a WorkReport. It must be stdlib-only,
    free to run, and original from-scratch logic.
    """

    id: str
    name: str
    kind: str
    description: str
    run: Callable[[Dict[str, Any]], WorkReport]
    version: str = "1.0.0"
    entry_price_usd: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise ValueError("generator id must be a non-empty string")
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if not callable(self.run):
            raise ValueError("run must be callable")
        if self.entry_price_usd is not None:
            if not isinstance(self.entry_price_usd, (int, float)) or self.entry_price_usd <= 0:
                raise ValueError("entry_price_usd must be a positive number")


class Registry:
    """The 100-slot generator registry."""

    def __init__(self) -> None:
        self._slots: Dict[int, Generator] = {}
        self._ids: Dict[str, int] = {}

    def register(self, generator: Generator, slot: int) -> Generator:
        if not isinstance(slot, int) or not 1 <= slot <= MAX_SLOTS:
            raise ValueError(f"slot must be 1..{MAX_SLOTS}, got {slot!r}")
        if slot in self._slots:
            raise ValueError(
                f"slot {slot} already taken by {self._slots[slot].id!r}"
            )
        if generator.id in self._ids:
            raise ValueError(
                f"generator id {generator.id!r} already registered "
                f"(slot {self._ids[generator.id]})"
            )
        self._slots[slot] = generator
        self._ids[generator.id] = slot
        return generator

    def get(self, generator_id: str) -> Generator:
        try:
            return self._slots[self._ids[generator_id]]
        except KeyError:
            raise KeyError(f"no generator registered as {generator_id!r}") from None

    def slot_of(self, generator_id: str) -> int:
        try:
            return self._ids[generator_id]
        except KeyError:
            raise KeyError(f"no generator registered as {generator_id!r}") from None

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                "slot": slot,
                "id": g.id,
                "name": g.name,
                "kind": g.kind,
                "version": g.version,
                "entry_price_usd": g.entry_price_usd,
                "description": g.description,
            }
            for slot, g in sorted(self._slots.items())
        ]

    def count(self) -> int:
        return len(self._slots)

    def free_slots(self) -> List[int]:
        return [s for s in range(1, MAX_SLOTS + 1) if s not in self._slots]


REGISTRY = Registry()


def register(generator: Generator, slot: int) -> Generator:
    """Register a generator in its assigned slot (batches call this)."""
    return REGISTRY.register(generator, slot)


def discover() -> int:
    """Import every gen_*.py module in this package (they self-register)."""
    import levi.income as pkg

    found = 0
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("gen_"):
            importlib.import_module(f"levi.income.{info.name}")
            found += 1
    return found


def split_income(amount: float) -> Dict[str, float]:
    """The 70/30 split. Returns {"keeper": ..., "pool": ...}."""
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    pool = round(amount * POOL_SHARE, 2)
    keeper = round(amount - pool, 2)
    return {"keeper": keeper, "pool": pool}


def record_income(
    generator_id: str,
    amount: float,
    kind: str,
    *,
    basis: str,
    counterparty: str = "",
    note: str = "",
) -> Dict[str, Any]:
    """Record a CONFIRMED income event and apply the 70/30 split.

    basis must be "confirmed" — Chauncey confirming money arrived.
    Anything else raises: the engine never invents income.
    """
    REGISTRY.get(generator_id)  # must be a registered generator
    if kind not in INCOME_KINDS:
        raise ValueError(f"kind must be one of {INCOME_KINDS}, got {kind!r}")
    if basis != "confirmed":
        raise ValueError(
            f"basis must be 'confirmed' (human-confirmed money), got {basis!r}"
        )
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")

    split = split_income(amount)
    event = {
        "id": uuid.uuid4().hex[:12],
        "at": _utcnow(),
        "generator_id": generator_id,
        "kind": kind,
        "amount": amount,
        "currency": "USD",
        "keeper": split["keeper"],
        "pool": split["pool"],
        "counterparty": counterparty,
        "note": note,
    }
    _write_jsonl(_events_path(), event)
    _write_jsonl(
        _pool_path(),
        {
            "id": uuid.uuid4().hex[:12],
            "at": _utcnow(),
            "event_id": event["id"],
            "generator_id": generator_id,
            "allocated": split["pool"],
            "reason": "30% reinvestment allocation",
        },
    )
    # Compose with the shared monetize ledger (records, never moves).
    try:
        from levi.monetize.ledger import log_event as _log

        _log(
            project=f"income:{generator_id}",
            kind=kind,
            amount=amount,
            note=f"70/30 split — keeper ${split['keeper']:.2f} / "
            f"reinvest pool ${split['pool']:.2f}. {note}".strip(),
            counterparty=counterparty,
        )
    except Exception:
        pass  # ledger is a record, not a gate; the event file is canonical
    return event


def pool_balance() -> Dict[str, float]:
    """Current reinvestment-pool standing (allocated vs approved-spent)."""
    allocated = sum(r.get("allocated", 0.0) for r in _read_jsonl(_pool_path()))
    spent = sum(
        r.get("amount", 0.0)
        for r in _read_jsonl(_pool_path())
        if r.get("type") == "spend"
    )
    return {
        "allocated": round(allocated, 2),
        "spent": round(spent, 2),
        "available": round(allocated - spent, 2),
    }


def approve_pool_spend(amount: float, purpose: str, *, by: str) -> Dict[str, Any]:
    """Approve a reinvestment-pool spend. Chauncey only.

    Records the approval; actual money movement executes ONLY through the
    Cybrus MoneyGateway (fail-closed, no rails registered).
    """
    if by != "chauncey":
        raise ValueError("pool spends are approved by Chauncey only")
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    bal = pool_balance()
    if amount > bal["available"]:
        raise ValueError(
            f"spend ${amount:.2f} exceeds pool available ${bal['available']:.2f}"
        )
    record = {
        "id": uuid.uuid4().hex[:12],
        "at": _utcnow(),
        "type": "spend",
        "amount": amount,
        "purpose": purpose,
        "approved_by": by,
        "movement": "pending — executes only via Cybrus MoneyGateway",
    }
    _write_jsonl(_pool_path(), record)
    return record


def run_generator(
    generator_id: str, *, dry_run: bool = True, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run one generator's automation cycle. Returns the recorded run.

    dry_run=True is the default: the generator runs its logic and reports
    what it WOULD do; nothing is written outside the run log.
    """
    gen = REGISTRY.get(generator_id)
    ctx = {
        "levi_home": Path(os.environ.get("LEVI_HOME", str(Path.home()))),
        "dry_run": dry_run,
        "params": params or {},
    }
    report = gen.run(ctx)
    if not isinstance(report, WorkReport):
        raise ValueError(
            f"generator {generator_id!r} run() must return a WorkReport"
        )
    if report.generator_id != generator_id:
        raise ValueError("WorkReport.generator_id mismatch")
    record = {
        "id": uuid.uuid4().hex[:12],
        "at": _utcnow(),
        "generator_id": generator_id,
        "slot": REGISTRY.slot_of(generator_id),
        "dry_run": dry_run,
        "produced": report.produced,
        "quoted_amount_usd": report.quoted_amount_usd,
        "notes": report.notes,
    }
    _write_jsonl(_runs_path(), record)
    return record


def run_all(*, dry_run: bool = True) -> List[Dict[str, Any]]:
    """Run every registered generator's cycle. Returns run records."""
    results = []
    for entry in REGISTRY.list():
        try:
            results.append(run_generator(entry["id"], dry_run=dry_run))
        except Exception as exc:  # one bad generator never kills the sweep
            results.append(
                {
                    "generator_id": entry["id"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results


def advise_entry_price(giant_price: Optional[float] = None) -> Dict[str, Any]:
    """Price a generator's entry tier per the founder pricing doctrine."""
    from levi.advisor.pricing import PricePlan, advise_price

    advice = advise_price(PricePlan(tier="entry", giant_price=giant_price))
    return {
        "recommended": advice.recommended,
        "band": [advice.low, advice.high],
        "seat_cap": advice.seat_cap,
        "rationale": advice.rationale,
    }


def summary() -> Dict[str, Any]:
    """Portfolio standing: generators, events, pool, keeper totals."""
    events = _read_jsonl(_events_path())
    by_kind: Dict[str, int] = {}
    for g in REGISTRY.list():
        by_kind[g["kind"]] = by_kind.get(g["kind"], 0) + 1
    return {
        "generators": REGISTRY.count(),
        "slots_used": MAX_SLOTS - len(REGISTRY.free_slots()),
        "by_kind": by_kind,
        "events": len(events),
        "gross_recorded": round(sum(e.get("amount", 0.0) for e in events), 2),
        "keeper_total": round(sum(e.get("keeper", 0.0) for e in events), 2),
        "pool": pool_balance(),
    }
