"""Omega substrate: the one bloodstream all five organs share.

INTERPENETRATION LAW (Chauncey, 2026-09-22) — not just contracts between
organs, one bloodstream:

1. SHARED STATE: receipts, learnings, genome entries, and the daemon
   schedule live in ONE pool (``SharedSubstrate``). Every organ reads and
   writes it — no organ sees only what gets handed across an interface.

2. STRICTEST-RISK-CEILING INHERITANCE: whenever organs interact, the
   strictest risk ceiling among them governs the whole interaction. A
   low-risk organ calling a high-risk action inherits the high-risk
   ceiling (approval record, audit receipt; critical actions need HITL).

3. INTERROGATION NEVER COLLAPSES: any organ may challenge another organ's
   output. A challenged receipt is QUARANTINED — no organ may consume it
   until the challenge is resolved. Challenge paths are first-class, not
   afterthoughts: Echo challenges Alpha's builds, Nexus refuses routes,
   the daemon quarantines skill results.

Origin tags: every pool entry records which organ wrote it. Nothing
anonymous crosses the bloodstream.

Public surface:

- Risk: ``RISK_LOW/STANDARD/ELEVATED/CRITICAL``, ``RISK_ORDER``,
  ``ORGAN_RISK`` (each organ's declared ceiling), ``ceiling_for(*organs,
  action_risk=None)``, ``requires_approval(tier)``,
  ``requires_hitl(tier)``.
- Records: ``Receipt``, ``Learning``, ``GenomeEntry``, ``ScheduleItem``,
  ``Challenge`` (dataclasses, all with ``id``, ``organ``, ``ts``).
- ``SharedSubstrate``: ``record_receipt``, ``receipts``, ``get_receipt``,
  ``record_learning``, ``learnings``, ``record_genome``, ``genome``,
  ``schedule``, ``due_jobs``, ``mark_job``, ``challenge``,
  ``resolve_challenge``, ``quarantined``, ``is_consumable``,
  ``save``/``load`` (JSONL, optional).

Defensive notes:

- In-memory by default; persistence is opt-in via ``save(path)`` /
  ``load(path)``. No network, no threads.
- ``challenge()`` on an unknown receipt id raises ``KeyError`` loudly —
  you cannot interrogate what was never recorded.
- ``resolve_challenge`` accepts only ``"upheld"`` or ``"dismissed"``.
  Upheld = the challenge stands, output stays quarantined forever.
  Dismissed = the output is released for consumption.
- ``is_consumable`` is the single gate every organ must check before
  consuming another organ's output. No bypasses.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival-omega/substrate"

# ---------------------------------------------------------------------------
# Risk model: strictest ceiling wins
# ---------------------------------------------------------------------------

RISK_LOW = "low"
RISK_STANDARD = "standard"
RISK_ELEVATED = "elevated"
RISK_CRITICAL = "critical"
RISK_ORDER = (RISK_LOW, RISK_STANDARD, RISK_ELEVATED, RISK_CRITICAL)
_RISK_RANK = {tier: i for i, tier in enumerate(RISK_ORDER)}

# Each organ's declared ceiling — the strictest guard it will accept for
# itself. Interactions inherit the strictest (highest) tier involved.
ORGAN_RISK: Dict[str, str] = {
    "echo": RISK_STANDARD,    # design is reversible; a bad blueprint costs time
    "alpha": RISK_ELEVATED,   # builds write files to disk
    "nexus": RISK_STANDARD,   # routing decisions shape what runs where
    "daemon": RISK_ELEVATED,  # executes on schedule without a human watching
    "skill": RISK_ELEVATED,   # skills act in the world
}
ORGANS = frozenset(ORGAN_RISK)


def _check_tier(tier: str) -> str:
    if tier not in _RISK_RANK:
        raise ValueError(f"unknown risk tier: {tier!r} (want one of {RISK_ORDER})")
    return tier


def ceiling_for(*organs: str, action_risk: Optional[str] = None) -> str:
    """Strictest risk ceiling for an interaction.

    Takes the highest tier among the organs involved and the action's own
    tier (if given). A low-risk organ calling a high-risk action inherits
    the high-risk ceiling — trust never flows downhill.
    """
    tiers = [_check_tier(ORGAN_RISK[o]) if o in ORGAN_RISK else _check_tier(o)
             for o in organs]
    if action_risk is not None:
        tiers.append(_check_tier(action_risk))
    if not tiers:
        return RISK_STANDARD
    return max(tiers, key=lambda t: _RISK_RANK[t])


def requires_approval(tier: str) -> bool:
    """Elevated and above need a recorded approval before execution."""
    return _RISK_RANK[_check_tier(tier)] >= _RISK_RANK[RISK_ELEVATED]


def requires_hitl(tier: str) -> bool:
    """Critical needs a human in the loop — no standing approval suffices."""
    return _RISK_RANK[_check_tier(tier)] >= _RISK_RANK[RISK_CRITICAL]


# ---------------------------------------------------------------------------
# Records: everything that crosses the bloodstream
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class Receipt:
    """Proof that an organ did a thing. The bloodstream's unit of truth."""
    id: str
    organ: str            # which organ acted
    kind: str             # e.g. "blueprint", "build", "route", "skill_run", "loop"
    payload: Dict[str, Any]
    risk: str             # ceiling that governed this action
    approved_by: Optional[str] = None  # who/what approved (required if requires_approval(risk))
    quarantined: bool = False
    ts: str = field(default_factory=_utcnow)


@dataclass
class Learning:
    """Something an organ learned, available to all organs."""
    id: str
    organ: str
    lesson: str
    ts: str = field(default_factory=_utcnow)


@dataclass
class GenomeEntry:
    """A durable trait for the organism's genome (RIEM-facing)."""
    id: str
    organ: str
    trait: str
    ts: str = field(default_factory=_utcnow)


@dataclass
class ScheduleItem:
    """A daemon job waiting in the shared schedule pool."""
    id: str
    organ: str            # which organ scheduled it
    job: str              # job name, e.g. "symbiotic_loop"
    run_at: str           # ISO timestamp; due when <= now
    payload: Dict[str, Any]
    status: str = "pending"  # pending | running | done | failed
    ts: str = field(default_factory=_utcnow)


@dataclass
class Challenge:
    """An interrogation: one organ questioning another's output."""
    id: str
    challenger: str       # organ raising the challenge
    target_organ: str     # organ whose output is questioned
    target_receipt_id: str
    grounds: str          # why, in plain words
    status: str = "open"  # open | resolved
    verdict: Optional[str] = None  # upheld | dismissed (set on resolve)
    note: str = ""
    ts: str = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# The pool itself
# ---------------------------------------------------------------------------

class SharedSubstrate:
    """One pool for receipts, learnings, genome entries, schedule, and
    challenges. Every organ reads and writes here; nothing crosses the
    bloodstream anonymously."""

    def __init__(self) -> None:
        self._receipts: Dict[str, Receipt] = {}
        self._learnings: Dict[str, Learning] = {}
        self._genome: Dict[str, GenomeEntry] = {}
        self._schedule: Dict[str, ScheduleItem] = {}
        self._challenges: Dict[str, Challenge] = {}

    # -- receipts ---------------------------------------------------------
    def record_receipt(
        self,
        organ: str,
        kind: str,
        payload: Dict[str, Any],
        risk: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> Receipt:
        if organ not in ORGANS:
            raise ValueError(f"unknown organ: {organ!r} (want one of {sorted(ORGANS)})")
        tier = _check_tier(risk) if risk is not None else ORGAN_RISK[organ]
        if requires_approval(tier) and not approved_by:
            raise ValueError(
                f"risk ceiling {tier!r} requires a recorded approval "
                f"(approved_by) — refusing to record unapproved {kind}"
            )
        receipt = Receipt(
            id=_new_id("rcpt"),
            organ=organ,
            kind=kind,
            payload=dict(payload),
            risk=tier,
            approved_by=approved_by,
        )
        self._receipts[receipt.id] = receipt
        return receipt

    def receipts(self, organ: Optional[str] = None,
                 kind: Optional[str] = None) -> List[Receipt]:
        out = list(self._receipts.values())
        if organ is not None:
            out = [r for r in out if r.organ == organ]
        if kind is not None:
            out = [r for r in out if r.kind == kind]
        return out

    def get_receipt(self, receipt_id: str) -> Optional[Receipt]:
        return self._receipts.get(receipt_id)

    # -- learnings / genome -----------------------------------------------
    def record_learning(self, organ: str, lesson: str) -> Learning:
        if organ not in ORGANS:
            raise ValueError(f"unknown organ: {organ!r}")
        entry = Learning(id=_new_id("learn"), organ=organ, lesson=lesson)
        self._learnings[entry.id] = entry
        return entry

    def learnings(self, organ: Optional[str] = None) -> List[Learning]:
        out = list(self._learnings.values())
        if organ is not None:
            out = [e for e in out if e.organ == organ]
        return out

    def record_genome(self, organ: str, trait: str) -> GenomeEntry:
        if organ not in ORGANS:
            raise ValueError(f"unknown organ: {organ!r}")
        entry = GenomeEntry(id=_new_id("gene"), organ=organ, trait=trait)
        self._genome[entry.id] = entry
        return entry

    def genome(self) -> List[GenomeEntry]:
        return list(self._genome.values())

    # -- schedule ----------------------------------------------------------
    def schedule(self, organ: str, job: str, run_at: str,
                 payload: Dict[str, Any]) -> ScheduleItem:
        if organ not in ORGANS:
            raise ValueError(f"unknown organ: {organ!r}")
        item = ScheduleItem(
            id=_new_id("sched"), organ=organ, job=job,
            run_at=run_at, payload=dict(payload),
        )
        self._schedule[item.id] = item
        return item

    def due_jobs(self, now: Optional[str] = None) -> List[ScheduleItem]:
        stamp = now or _utcnow()
        return [j for j in self._schedule.values()
                if j.status == "pending" and j.run_at <= stamp]

    def mark_job(self, item_id: str, status: str) -> ScheduleItem:
        if status not in ("pending", "running", "done", "failed"):
            raise ValueError(f"bad job status: {status!r}")
        item = self._schedule[item_id]
        item.status = status
        return item

    # -- challenges: interrogation never collapses -------------------------
    def challenge(self, challenger: str, target_receipt_id: str,
                  grounds: str) -> Challenge:
        """One organ questions another's recorded output. The target
        receipt is quarantined immediately — no organ may consume it
        until the challenge resolves."""
        if challenger not in ORGANS:
            raise ValueError(f"unknown organ: {challenger!r}")
        target = self._receipts.get(target_receipt_id)
        if target is None:
            raise KeyError(f"no receipt {target_receipt_id!r} to challenge")
        if not grounds or not grounds.strip():
            raise ValueError("a challenge needs grounds, in plain words")
        ch = Challenge(
            id=_new_id("chal"),
            challenger=challenger,
            target_organ=target.organ,
            target_receipt_id=target_receipt_id,
            grounds=grounds.strip(),
        )
        target.quarantined = True
        self._challenges[ch.id] = ch
        return ch

    def resolve_challenge(self, challenge_id: str, verdict: str,
                          note: str = "") -> Challenge:
        """verdict "upheld": the challenge stands, output stays quarantined
        forever. verdict "dismissed": the output is released."""
        if verdict not in ("upheld", "dismissed"):
            raise ValueError("verdict must be 'upheld' or 'dismissed'")
        ch = self._challenges[challenge_id]
        if ch.status == "resolved":
            raise ValueError(f"challenge {challenge_id} already resolved")
        ch.status = "resolved"
        ch.verdict = verdict
        ch.note = note
        target = self._receipts.get(ch.target_receipt_id)
        if target is not None and verdict == "dismissed":
            # release only if no OTHER open challenge still holds it AND no
            # earlier challenge was upheld — an upheld verdict holds forever,
            # even if a later challenge on the same receipt is dismissed.
            still_held = any(
                c.status == "open" and c.target_receipt_id == target.id
                for c in self._challenges.values()
            )
            ever_upheld = any(
                c.status == "resolved" and c.verdict == "upheld"
                and c.target_receipt_id == target.id
                for c in self._challenges.values()
            )
            if not still_held and not ever_upheld:
                target.quarantined = False
        return ch

    def challenges(self, status: Optional[str] = None) -> List[Challenge]:
        out = list(self._challenges.values())
        if status is not None:
            out = [c for c in out if c.status == status]
        return out

    def quarantined(self) -> List[Receipt]:
        return [r for r in self._receipts.values() if r.quarantined]

    def is_consumable(self, receipt_id: str) -> bool:
        """THE gate: True only if the receipt exists and is not under an
        open challenge. Every organ checks this before consuming another
        organ's output. No bypasses."""
        r = self._receipts.get(receipt_id)
        return r is not None and not r.quarantined

    # -- persistence (opt-in) ------------------------------------------------
    def save(self, path: str) -> str:
        data = {
            "receipts": [asdict(r) for r in self._receipts.values()],
            "learnings": [asdict(e) for e in self._learnings.values()],
            "genome": [asdict(e) for e in self._genome.values()],
            "schedule": [asdict(j) for j in self._schedule.values()],
            "challenges": [asdict(c) for c in self._challenges.values()],
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path: str) -> "SharedSubstrate":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        sub = cls()
        for r in data.get("receipts", []):
            sub._receipts[r["id"]] = Receipt(**r)
        for e in data.get("learnings", []):
            sub._learnings[e["id"]] = Learning(**e)
        for e in data.get("genome", []):
            sub._genome[e["id"]] = GenomeEntry(**e)
        for j in data.get("schedule", []):
            sub._schedule[j["id"]] = ScheduleItem(**j)
        for c in data.get("challenges", []):
            sub._challenges[c["id"]] = Challenge(**c)
        return sub
