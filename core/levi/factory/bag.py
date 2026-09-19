"""LEVI Factory Bag — Santa's bag.

Every first the factory owes the world: skills, features, services,
recreations, revivals, tools, engines, daemons, groundbreaking discoveries,
experiments, research, developments, strategic problem solutions,
first-time deliveries, releases, fascinating finds, methods.

Items flow: queued -> draft -> delivered. Nothing ships without a second
pair of eyes: 'draft' means built but unreviewed; 'delivered' means reviewed
and released into the product.

The night shift fills the bag around the clock: it takes the top queued
item and produces a draft per the category playbook. Drafts land in
~/.levi/factory/bag_drafts/ and wait for review.

Agent X rule: items flagged eyes_only never leave Chauncey's hands.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from levi.factory import review as bag_review

CATEGORIES = (
    "skill",
    "feature",
    "service",
    "recreation",
    "revival",
    "tool",
    "engine",
    "daemon",
    "discovery",
    "experiment",
    "research",
    "development",
    "solution",
    "first-delivery",
    "release",
    "find",
    "method",
    "drill",
    "field-guide",
)

STATUSES = ("queued", "draft", "delivered")

# Night-shift throughput: one item per run keeps quality tight, but when the
# queue runs deep the line is allowed to draft up to NIGHT_SHIFT_MAX_BATCH
# items in a single run instead of one.
NIGHT_SHIFT_MAX_BATCH = 3
NIGHT_SHIFT_DEEP_QUEUE = 6


def night_shift_batch_size(queue_depth: int) -> int:
    """How many queued items one night-shift run may draft.

    Deep queue (>= NIGHT_SHIFT_DEEP_QUEUE waiting) unlocks batching up to
    NIGHT_SHIFT_MAX_BATCH; otherwise the line drafts a single item.
    """
    if queue_depth >= NIGHT_SHIFT_DEEP_QUEUE:
        return NIGHT_SHIFT_MAX_BATCH
    return 1


# What the night shift produces for each category. The worker composes the
# draft; the bag only records it.
PLAYBOOK = {
    "skill": "Compose a markdown skill card: name, when it triggers, the move step-by-step, a worked example, and its failure mode.",
    "feature": "Write a feature brief: what it does, who it's for, the smallest shippable shape, and what it must never do.",
    "service": "Write a service offering sheet: the promise, the pipeline (analyze->quote->deliver->paid->showcase), the price shape, and the receipt it leaves.",
    "recreation": "Rebuild the thing from memory and first principles — no copying. Document what the original got right, what it got wrong, and what the recreation does that the original couldn't.",
    "revival": "Take something dead or abandoned and write its return plan: why it died, what changed, the smallest revival that proves life.",
    "tool": "Write a tool spec: the job, the interface, the edge cases, and the one command that proves it works.",
    "engine": "Write an engine design: inputs, outputs, the core loop, and the invariant it never violates.",
    "daemon": "Write a daemon charter: what it watches, when it wakes, what it does alone, and when it must ask a human.",
    "discovery": "Write the discovery as a field note: what was found, how, why nobody saw it before, and what it unlocks.",
    "experiment": "Write an experiment plan: hypothesis, setup, what success looks like, what failure teaches, and the stop rule.",
    "research": "Write a research brief: the question, what is known, the gap, and the three most promising leads.",
    "development": "Write a development log entry: what was built, the decision that mattered, and what's next.",
    "solution": "Write the problem, the constraints, the solution, and why it's the first of its kind.",
    "first-delivery": "Record the first delivery: what was delivered, to whom, the receipt, and why it had never been done before.",
    "release": "Write release notes: what shipped, who it's for, and the one line the world will quote.",
    "find": "Write the find as a field note: what it is, where it was hiding, and why it matters.",
    "method": "Write the method as a teachable: the pattern name, when to use it, the steps, and the anti-pattern it replaces.",
    "drill": "Write a drill card: the skill it trains, the setup, the steps under pressure, the scoring rubric, and the debrief questions.",
    "field-guide": "Write a field guide: the terrain, the signs to read, the tools to carry, the mistakes that hurt, and the one-page quick reference.",
}

DEFAULT_FACTORY_DIR = Path.home() / ".levi" / "factory"


def _now() -> float:
    return time.time()


def _receipt(prev: str, item_id: str, status: str) -> str:
    raw = f"{prev}|{item_id}|{status}|{_now()}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class BagItem:
    item_id: str
    category: str
    title: str
    brief: str
    status: str = "queued"
    eyes_only: bool = False
    draft_path: str = ""
    receipt: str = ""
    created: float = field(default_factory=_now)
    updated: float = field(default_factory=_now)

    def touch(self) -> None:
        self.updated = _now()


class Bag:
    """The bag itself: JSON persistence + receipt chain."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_FACTORY_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "bag.json"
        self.drafts_dir = self.data_dir / "bag_drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, BagItem] = {}
        self._last_receipt = "genesis"
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        self._last_receipt = raw.get("last_receipt", "genesis")
        for d in raw.get("items", []):
            try:
                self._items[d["item_id"]] = BagItem(**d)
            except (KeyError, TypeError):
                continue

    def _save(self) -> None:
        raw = {
            "last_receipt": self._last_receipt,
            "items": [asdict(i) for i in self._items.values()],
        }
        self.path.write_text(json.dumps(raw, indent=2))

    def _chain(self, item: BagItem, status: str) -> str:
        r = _receipt(self._last_receipt, item.item_id, status)
        self._last_receipt = r
        return r

    def queue(
        self, category: str, title: str, brief: str, eyes_only: bool = False
    ) -> BagItem:
        if category not in CATEGORIES:
            raise ValueError(f"unknown category {category!r}")
        item = BagItem(
            item_id=uuid.uuid4().hex[:8],
            category=category,
            title=title,
            brief=brief,
            eyes_only=eyes_only,
        )
        item.receipt = self._chain(item, "queued")
        self._items[item.item_id] = item
        self._save()
        return item

    def get(self, item_id: str) -> BagItem | None:
        return self._items.get(item_id)

    def list(
        self, status: str | None = None, category: str | None = None
    ) -> list[BagItem]:
        items = sorted(self._items.values(), key=lambda i: i.created)
        if status:
            items = [i for i in items if i.status == status]
        if category:
            items = [i for i in items if i.category == category]
        return items

    def next_up(self) -> BagItem | None:
        queued = self.list(status="queued")
        return queued[0] if queued else None

    def mark_draft(
        self, item_id: str, draft_path: str, receipt_note: str = ""
    ) -> BagItem:
        item = self._items[item_id]
        item.status = "draft"
        item.draft_path = draft_path
        item.touch()
        item.receipt = self._chain(item, "draft")
        if receipt_note:
            item.brief = item.brief + f"\n[draft note] {receipt_note}"
        self._save()
        return item

    def deliver(self, item_id: str, receipt_note: str = "") -> BagItem:
        item = self._items[item_id]
        if item.status == "queued":
            raise ValueError("cannot deliver an item still queued — draft it first")
        # The review gate: nothing ships without a second pair of eyes.
        record = bag_review.load_review(self.data_dir, item_id)
        if record is None:
            raise ValueError(
                "cannot deliver an unreviewed draft — "
                f"run `bag review --id {item_id}` first"
            )
        if not record.get("passed"):
            raise ValueError(
                "cannot deliver — draft failed review; fix the notes and re-review"
            )
        item.status = "delivered"
        item.touch()
        item.receipt = self._chain(item, "delivered")
        if receipt_note:
            item.brief = item.brief + f"\n[delivery note] {receipt_note}"
        self._save()
        return item

    def stats(self) -> dict:
        counts = {s: 0 for s in STATUSES}
        for i in self._items.values():
            counts[i.status] = counts.get(i.status, 0) + 1
        return {"total": len(self._items), **counts}


def _fmt(item: BagItem) -> str:
    eye = " [eyes-only]" if item.eyes_only else ""
    return f"{item.item_id} [{item.category}/{item.status}]{eye} {item.title}"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="bag", description="LEVI Factory Bag")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list items")
    p.add_argument("--status", choices=STATUSES, default=None)
    p.add_argument("--category", choices=CATEGORIES, default=None)

    p = sub.add_parser("queue", help="queue a first")
    p.add_argument("--category", choices=CATEGORIES, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--brief", required=True)
    p.add_argument("--eyes-only", action="store_true")

    sub.add_parser("next", help="show the top queued item")
    p = sub.add_parser("draft", help="mark an item drafted")
    p.add_argument("--id", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--note", default="")
    p = sub.add_parser("deliver", help="mark an item delivered")
    p.add_argument("--id", required=True)
    p.add_argument("--note", default="")
    p = sub.add_parser("review", help="second-pass review of a draft")
    p.add_argument("--id", required=True)
    sub.add_parser("stats", help="bag counts")
    sub.add_parser("playbook", help="show the draft playbook for a category")
    sub.add_parser("playbooks", help="list all categories")

    args = ap.parse_args(argv)
    bag = Bag()

    if args.cmd == "list":
        for i in bag.list(status=args.status, category=args.category):
            print(_fmt(i))
    elif args.cmd == "queue":
        item = bag.queue(args.category, args.title, args.brief, args.eyes_only)
        print(f"queued {_fmt(item)} receipt={item.receipt}")
    elif args.cmd == "next":
        item = bag.next_up()
        if item is None:
            print("bag is empty — the line is starved, feed it")
        else:
            print(_fmt(item))
            print(f"brief: {item.brief}")
            print(f"playbook: {PLAYBOOK[item.category]}")
    elif args.cmd == "draft":
        item = bag.mark_draft(args.id, args.path, args.note)
        print(f"draft {_fmt(item)} -> {args.path}")
    elif args.cmd == "deliver":
        try:
            item = bag.deliver(args.id, args.note)
        except (KeyError, ValueError) as e:
            print(f"refused: {e}")
            return 1
        print(f"delivered {_fmt(item)} receipt={item.receipt}")
    elif args.cmd == "review":
        item = bag.get(args.id)
        if item is None:
            print(f"refused: unknown item {args.id!r}")
            return 1
        if item.status != "draft":
            print(
                f"refused: {args.id} is {item.status}, not a draft — nothing to review"
            )
            return 1
        rec = bag_review.review_draft(
            item.item_id,
            item.draft_path,
            item.title,
            item.brief,
            home=bag.data_dir,
        )
        print(f"review {args.id}: {'PASS' if rec['passed'] else 'FAIL'}")
        for name, check in rec["checklist"].items():
            mark = "ok" if check["passed"] else "XX"
            print(f"  [{mark}] {name}: {check['note']}")
    elif args.cmd == "stats":
        print(json.dumps(bag.stats(), indent=2))
    elif args.cmd == "playbook":
        print("usage: bag next  (shows the playbook for the top item)")
    elif args.cmd == "playbooks":
        for c in CATEGORIES:
            print(f"{c}: {PLAYBOOK[c]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
