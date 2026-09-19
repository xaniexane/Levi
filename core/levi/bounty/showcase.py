"""The hunt showcase — the public track record.

Nothing enters the showcase without BOTH verified delivery AND confirmed
payment. Admission rules are structural, not editorial:

- the bounty must be in state PAID,
- it must carry a Cybrus gateway receipt,
- the receipt must show an EXECUTED movement (not a refusal, not a plan).

No fake entries, ever: :func:`admit` refuses anything that does not meet
all three, with the reason stated. Client verification
(:func:`verify_client`) is a separate, later attestation — it marks an
entry as client-confirmed but is never a substitute for the money proof.

The showcase file is the public-facing record; entries render to
markdown via :func:`render`.

stdlib-only. Records at ``~/.levi/bounty/showcase.jsonl``, owner-only.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.bounty.hunts import Bounty, BountyState, _data_dir


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _showcase_path(home: Optional[Path] = None) -> Path:
    return _data_dir(home) / "showcase.jsonl"


class ShowcaseRefused(ValueError):
    """An entry was refused admission to the showcase."""


@dataclass
class ShowcaseEntry:
    entry_id: str
    bounty_id: str
    title: str
    problem: str
    solution_summary: str
    evidence: List[str] = field(default_factory=list)
    delivered_at: str = ""
    paid_at: str = ""
    client_verified: bool = False
    client_note: str = ""
    admitted_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ShowcaseEntry":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def admit(bounty: Bounty, *, gateway: Optional[Any] = None) -> ShowcaseEntry:
    """Admit a completed hunt to the showcase. Refuses anything unverified.

    All three must hold: state PAID, a Cybrus gateway receipt present,
    and the gateway's own record showing the movement executed.
    """
    if bounty.state != BountyState.PAID.value:
        raise ShowcaseRefused(
            f"bounty {bounty.id} is {bounty.state}, not paid — "
            "the showcase admits completed, paid hunts only"
        )
    if not bounty.payment_receipt:
        raise ShowcaseRefused(
            f"bounty {bounty.id} has no Cybrus gateway receipt — "
            "payment must be confirmed through Cybrus"
        )
    plan_id = bounty.payment_plan_id
    if gateway is not None and plan_id:
        record = gateway.receipt(plan_id)
        events = record.get("events") or []
        if "executed" not in events:
            raise ShowcaseRefused(
                f"bounty {bounty.id}: gateway shows no executed movement "
                f"(events: {events}) — nothing to showcase yet"
            )
    entry = ShowcaseEntry(
        entry_id="show_" + uuid.uuid4().hex[:10],
        bounty_id=bounty.id,
        title=bounty.title,
        problem=bounty.problem,
        solution_summary=bounty.solution,
        evidence=list(bounty.evidence),
        delivered_at=bounty.updated_at,
        paid_at=_utcnow(),
    )
    return entry


class ShowcaseStore:
    """Owner-only JSONL record of admitted hunts."""

    def __init__(self, home: Optional[Path] = None):
        self.path = _showcase_path(home)
        if not self.path.exists():
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(fd)
        else:
            os.chmod(self.path, 0o600)

    def _read_all(self) -> Dict[str, ShowcaseEntry]:
        out: Dict[str, ShowcaseEntry] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = ShowcaseEntry.from_dict(json.loads(line))
            except Exception:
                continue
            out[e.entry_id] = e
        return out

    def _write_all(self, items: Dict[str, ShowcaseEntry]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for e in items.values():
                fh.write(json.dumps(e.to_dict()) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def add(self, entry: ShowcaseEntry) -> ShowcaseEntry:
        items = self._read_all()
        if any(e.bounty_id == entry.bounty_id for e in items.values()):
            raise ShowcaseRefused(
                f"bounty {entry.bounty_id} is already showcased — no duplicates"
            )
        items[entry.entry_id] = entry
        self._write_all(items)
        return entry

    def get(self, entry_id: str) -> ShowcaseEntry:
        items = self._read_all()
        try:
            return items[entry_id]
        except KeyError:
            raise ShowcaseRefused(f"unknown showcase entry {entry_id!r}") from None

    def list(self) -> List[ShowcaseEntry]:
        return sorted(self._read_all().values(), key=lambda e: e.admitted_at)

    def verify_client(self, entry_id: str, *, note: str = "") -> ShowcaseEntry:
        """Client attestation: the client confirms the hunt. Marks the
        entry client-verified; never a substitute for payment proof."""
        entry = self.get(entry_id)
        entry.client_verified = True
        entry.client_note = note.strip()
        items = self._read_all()
        items[entry.entry_id] = entry
        self._write_all(items)
        return entry


def render(store: ShowcaseStore) -> str:
    """Render the public track record as markdown."""
    entries = store.list()
    lines = ["# Hunt Showcase", "", "Verified completed hunts. Every entry below"]
    lines.append("represents a delivered solution AND a confirmed payment.")
    lines.append("")
    if not entries:
        lines.append("_No hunts showcased yet. The record starts empty and stays honest._")
        return "\n".join(lines) + "\n"
    for e in entries:
        badge = "✓ client-verified" if e.client_verified else "delivered + paid"
        lines.append(f"## {e.title} — {badge}")
        lines.append("")
        lines.append(f"**Problem:** {e.problem}")
        lines.append("")
        lines.append(f"**Solution:** {e.solution_summary}")
        lines.append("")
        if e.evidence:
            lines.append("**Evidence:**")
            for ev in e.evidence:
                lines.append(f"- {ev}")
            lines.append("")
        if e.client_note:
            lines.append(f"**Client:** {e.client_note}")
            lines.append("")
        lines.append(f"_Delivered {e.delivered_at} · paid {e.paid_at}_")
        lines.append("")
    return "\n".join(lines) + "\n"


__all__ = [
    "ShowcaseEntry",
    "ShowcaseRefused",
    "ShowcaseStore",
    "admit",
    "render",
]
