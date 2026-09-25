"""Triage — the inbound sorting bot.

Switchboard routes messages; triage decides what order the human reads
them in. :func:`score_item` is a deterministic heuristic — urgency
keywords, time pressure, whether the sender is known, and staleness —
producing 0–100 with a plain-language breakdown so the ranking is never
a black box. :class:`TriageQueue` is an owner-only JSONL queue:
:class:`add` scores and files an item with its receipt,
:meth:`next` pops the highest-priority item, :meth:`list_pending`
shows the ranked backlog.

Heuristic, not a model: it scores what it can see honestly and buckets
``now`` (>= 70), ``soon`` (>= 40), ``later``. Nothing is ever deleted
silently — every pop writes a receipt to ``receipts.jsonl``.

Run it: ``python -m levi.bot.triage add --title ... --source ...``,
``python -m levi.bot.triage list``, ``python -m levi.bot.triage next``.
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Item",
    "ScoreBreakdown",
    "TriageQueue",
    "score_item",
    "bucket",
    "state_dir",
    "queue_path",
    "receipts_path",
    "main",
]


# ------------------------------------------------------------------ home


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def state_dir() -> Path:
    return _home() / "triage"


def queue_path() -> Path:
    return state_dir() / "queue.jsonl"


def receipts_path() -> Path:
    return state_dir() / "receipts.jsonl"


def _owner_only(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _owner_only_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _owner_only_dir(path.parent)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
    _owner_only(path)


# --------------------------------------------------------------- scoring

_URGENT = (
    "urgent",
    "emergency",
    "critical",
    "asap",
    "immediately",
    "breaking",
    "outage",
    "down",
    "breach",
    "expired",
    "deadline",
    "overdue",
)
_TIME_PRESSURE = (
    "today",
    "tonight",
    "now",
    "eod",
    "end of day",
    "this morning",
    "tomorrow morning",
    "right away",
)
_KNOWN_SOURCE_BONUS = 15
_MAX = 100


@dataclass
class ScoreBreakdown:
    """The visible math behind one item's score."""

    score: int
    bucket: str
    reasons: List[str] = field(default_factory=list)


def _contains_any(text: str, words: Tuple[str, ...]) -> List[str]:
    lowered = text.lower()
    return [w for w in words if w in lowered]


def score_item(
    title: str,
    body: str = "",
    source: str = "",
    known_sources: Tuple[str, ...] = (),
    age_hours: float = 0.0,
) -> ScoreBreakdown:
    """Deterministic 0–100 priority score with the reasons attached."""
    text = f"{title}\n{body}"
    reasons: List[str] = []
    score = 20  # baseline: it arrived, so it matters a little

    hits = _contains_any(text, _URGENT)
    if hits:
        score += 35
        reasons.append(f"urgency keywords: {', '.join(hits[:4])} (+35)")
    press = _contains_any(text, _TIME_PRESSURE)
    if press:
        score += 20
        reasons.append(f"time pressure: {', '.join(press[:3])} (+20)")
    if "?" in title:
        score += 10
        reasons.append("asks a question (+10)")
    if source and source.lower() in {s.lower() for s in known_sources}:
        score += _KNOWN_SOURCE_BONUS
        reasons.append(f"known source {source!r} (+{_KNOWN_SOURCE_BONUS})")
    if title.isupper() and len(title) > 8:
        score += 10
        reasons.append("all-caps title, read as shouting (+10)")
    if len(body) > 800:
        score -= 10
        reasons.append("long body, probably not urgent (-10)")
    if age_hours > 48:
        score -= 15
        reasons.append(f"stale ({age_hours:.0f}h old, -15)")
    elif age_hours > 24:
        score -= 5
        reasons.append(f"aging ({age_hours:.0f}h old, -5)")

    score = max(0, min(_MAX, score))
    if not reasons:
        reasons.append("no signals; baseline only")
    return ScoreBreakdown(score=score, bucket=bucket(score), reasons=reasons)


def bucket(score: int) -> str:
    """now >= 70, soon >= 40, otherwise later."""
    if score >= 70:
        return "now"
    if score >= 40:
        return "soon"
    return "later"


# ----------------------------------------------------------------- items


@dataclass
class Item:
    """One triaged inbound item."""

    title: str
    body: str = ""
    source: str = ""
    score: int = 0
    bucket: str = "later"
    reasons: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    received_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("Item needs a non-empty title")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        return cls(
            title=str(data.get("title", "")),
            body=str(data.get("body", "")),
            source=str(data.get("source", "")),
            score=int(data.get("score", 0)),
            bucket=str(data.get("bucket", "later")),
            reasons=list(data.get("reasons", [])),
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            received_at=str(data.get("received_at", _utcnow())),
        )


# ----------------------------------------------------------------- queue


class TriageQueue:
    """Owner-only scored queue with per-decision receipts."""

    def __init__(
        self,
        queue: Optional[Path] = None,
        receipts: Optional[Path] = None,
        known_sources: Tuple[str, ...] = (),
    ) -> None:
        self.queue = queue or queue_path()
        self.receipts = receipts or receipts_path()
        self.known_sources = known_sources

    # -- internals ----------------------------------------------------
    def _read(self) -> List[Item]:
        if not self.queue.exists():
            return []
        items: List[Item] = []
        for line in self.queue.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(Item.from_dict(json.loads(line)))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue  # corrupt line: skip honestly, never half-load
        return items

    def _rewrite(self, items: List[Item]) -> None:
        _owner_only_dir(self.queue.parent)
        tmp = self.queue.with_suffix(".tmp")
        tmp.write_text(
            "".join(json.dumps(i.to_dict(), sort_keys=True) + "\n" for i in items),
            encoding="utf-8",
        )
        _owner_only(tmp)
        os.replace(tmp, self.queue)

    def _receipt(self, action: str, item: Item, note: str = "") -> None:
        _append_jsonl(
            self.receipts,
            {
                "action": action,
                "item_id": item.id,
                "title": item.title,
                "score": item.score,
                "bucket": item.bucket,
                "note": note,
                "at": _utcnow(),
            },
        )

    # -- public API ---------------------------------------------------
    def add(
        self,
        title: str,
        body: str = "",
        source: str = "",
        age_hours: float = 0.0,
    ) -> Item:
        scored = score_item(title, body, source, self.known_sources, age_hours)
        item = Item(
            title=title,
            body=body,
            source=source,
            score=scored.score,
            bucket=scored.bucket,
            reasons=scored.reasons,
        )
        _append_jsonl(self.queue, item.to_dict())
        self._receipt("added", item)
        return item

    def list_pending(self) -> List[Item]:
        """Ranked backlog: bucket now > soon > later, then score, then age."""
        order = {"now": 0, "soon": 1, "later": 2}
        items = self._read()
        items.sort(key=lambda i: (order.get(i.bucket, 3), -i.score, i.received_at))
        return items

    def next(self) -> Optional[Item]:
        """Pop the highest-priority item; receipted. None when empty."""
        items = self.list_pending()
        if not items:
            return None
        top = items[0]
        rest = [i for i in self._read() if i.id != top.id]
        self._rewrite(rest)
        self._receipt("popped", top, note="highest priority")
        return top

    def counts(self) -> Dict[str, int]:
        counts = {"now": 0, "soon": 0, "later": 0}
        for item in self._read():
            counts[item.bucket] = counts.get(item.bucket, 0) + 1
        return counts


# ------------------------------------------------------------------ cli


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="levi.bot.triage", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add", help="score and file an inbound item")
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--body", default="")
    add_p.add_argument("--source", default="")
    add_p.add_argument(
        "--known", action="append", default=[], help="known source (repeatable)"
    )

    sub.add_parser("list", help="show the ranked backlog")
    sub.add_parser("next", help="pop the highest-priority item")
    sub.add_parser("counts", help="bucket counts")

    args = ap.parse_args(argv)
    q = TriageQueue(known_sources=tuple(args.known) if hasattr(args, "known") else ())

    if args.cmd == "add":
        item = q.add(args.title, body=args.body, source=args.source)
        print(f"[{item.bucket}] {item.score:3d} {item.title}")
        for reason in item.reasons:
            print(f"    - {reason}")
    elif args.cmd == "list":
        for item in q.list_pending():
            print(
                f"[{item.bucket:5s}] {item.score:3d} {item.title}  (from {item.source or 'unknown'})"
            )
    elif args.cmd == "next":
        item = q.next()
        if item is None:
            print("queue empty")
        else:
            print(f"[{item.bucket}] {item.score:3d} {item.title}")
            if item.body:
                print(item.body)
    elif args.cmd == "counts":
        print(json.dumps(q.counts(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
