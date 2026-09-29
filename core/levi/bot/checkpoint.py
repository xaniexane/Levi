"""Checkpoint bot — the memory of open loops.

Saves the currently open loops (tasks with state and a next step) to a
checkpoint file so an interrupted session can resume where it left off,
and lists the saved loops when asked.

Usage::

    from levi.bot import checkpoint

    # save: every loop needs a title and a next step, or it is refused
    record = checkpoint.save(
        [{"title": "Pack run 30", "state": "coding", "next_step": "run tests"}]
    )
    print(checkpoint.render(record))

    # resume later: the newest checkpoint that still has open loops
    loops = checkpoint.list_open()

``checkpoint.save`` writes ``checkpoints/<slug>-<stamp>.json`` under the
checkpoint directory (default ``~/.levi/bot/checkpoints/``) and appends
the record to ``ledger.jsonl``. A checkpoint is additive history — saving
never deletes or rewrites an earlier file.

Laws
----
- deny-closed: every loop needs a non-empty ``title`` and ``next_step``;
  ``status`` must be one of open/in-progress/waiting/paused (a
  ``done``/``closed`` loop is refused — checkpoints are for unfinished
  work); unknown fields or wrong types are refused, never guessed
- append-only: saves are new files; nothing is overwritten or deleted
- explicit writes: ``save`` always writes (it is the request); ``list_open``
  and ``render`` never touch the disk

CLI: ``python3 -m levi.bot.checkpoint save --loop title=... --loop ...``
or ``python3 -m levi.bot.checkpoint list`` / ``list --render``.

``MANIFEST_ENTRY`` documents the interop-manifest merge for the
``bot-checkpoint`` capability block; merging it is mechanical.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

MANIFEST_ENTRY = {
    "bot-checkpoint": {
        "provides": [
            "bot.checkpoint.save",
            "bot.checkpoint.list_open",
            "bot.checkpoint.render",
            "bot.checkpoint.cli",
        ],
        "requires": [],
        "description": "Checkpoint bot — save and resume open loops across sessions",
    }
}

_STATUSES = ("open", "in-progress", "waiting", "paused")


class CheckpointError(ValueError):
    """Raised when a checkpoint request is malformed."""


@dataclass
class Loop:
    """One unfinished loop: what it is and what comes next."""

    title: str
    next_step: str
    status: str = "open"
    state: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "next_step": self.next_step,
            "status": self.status,
            "state": self.state,
            "note": self.note,
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "Loop":
        if not isinstance(raw, dict):
            raise CheckpointError("checkpoint: each loop must be a dict")
        title = raw.get("title")
        next_step = raw.get("next_step")
        if not isinstance(title, str) or not title.strip():
            raise CheckpointError("checkpoint: loop needs a non-empty 'title'")
        if not isinstance(next_step, str) or not next_step.strip():
            raise CheckpointError("checkpoint: loop needs a non-empty 'next_step'")
        status = raw.get("status", "open")
        if status not in _STATUSES:
            raise CheckpointError(
                f"checkpoint: status {status!r} not allowed — "
                f"checkpoints are for unfinished loops {_STATUSES}"
            )
        for key in ("state", "note"):
            value = raw.get(key, "")
            if not isinstance(value, str):
                raise CheckpointError(f"checkpoint: '{key}' must be a string")
        extra = set(raw) - {"title", "next_step", "status", "state", "note"}
        if extra:
            raise CheckpointError(f"checkpoint: unknown loop fields {sorted(extra)}")
        return cls(
            title=title.strip(),
            next_step=next_step.strip(),
            status=status,
            state=str(raw.get("state", "")),
            note=str(raw.get("note", "")),
        )


@dataclass
class CheckpointRecord:
    """The receipt of one save: where it landed and what it holds."""

    path: str
    stamp: str
    loops: List[Loop] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "loops"


def _checkpoint_dir(base_dir: Optional[str]) -> Path:
    if base_dir:
        base = Path(base_dir)
    else:
        base = Path.home() / ".levi" / "bot" / "checkpoints"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save(
    loops: Sequence[Any],
    *,
    name: str = "loops",
    base_dir: Optional[str] = None,
) -> CheckpointRecord:
    """Save open loops as a new checkpoint file (append-only).

    Every loop is validated deny-closed; an empty loop list is refused.
    """
    parsed = [Loop.from_raw(raw) for raw in loops]
    if not parsed:
        raise CheckpointError("checkpoint: nothing to save — no loops given")
    directory = _checkpoint_dir(base_dir)
    stamp = time.strftime("%Y-%m-%dT%H%M%S")
    path = directory / f"{_slug(name)}-{stamp}.json"
    payload = {
        "stamp": stamp,
        "loops": [loop.to_dict() for loop in parsed],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    ledger = directory / "ledger.jsonl"
    with open(ledger, "a", encoding="utf-8") as handle:
        handle.write(
            json.dumps({"ts": stamp, "path": str(path), "loops": len(parsed)}) + "\n"
        )
    return CheckpointRecord(path=str(path), stamp=stamp, loops=parsed)


def list_open(
    base_dir: Optional[str] = None,
) -> List[Loop]:
    """List the open loops from the newest checkpoint that has any.

    Never writes; an empty checkpoint directory yields an empty list.
    """
    directory = _checkpoint_dir(base_dir)
    files = sorted(directory.glob("*.json"))
    for path in reversed(files):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a corrupt checkpoint is skipped, never trusted
        loops = payload.get("loops") if isinstance(payload, dict) else None
        if not loops:
            continue
        try:
            return [Loop.from_raw(raw) for raw in loops]
        except CheckpointError:
            continue
    return []


def render(record: CheckpointRecord) -> str:
    """Render a plain-text save receipt."""
    lines = [f"Checkpoint saved — {record.path}"]
    for loop in record.loops:
        detail = f" [{loop.status}]" if loop.status != "open" else ""
        lines.append(f"  - {loop.title}{detail}")
        lines.append(f"      next: {loop.next_step}")
        if loop.state:
            lines.append(f"      state: {loop.state}")
    return "\n".join(lines)


def render_list(loops: Sequence[Loop]) -> str:
    """Render a plain-text resume list."""
    if not loops:
        return "No open loops on record."
    lines = ["Open loops:"]
    for loop in loops:
        lines.append(f"  - {loop.title} [{loop.status}] -> {loop.next_step}")
    return "\n".join(lines)


def _loop_arg(text: str) -> Dict[str, str]:
    loop: Dict[str, str] = {}
    for chunk in text.split(";"):
        if "=" not in chunk:
            raise CheckpointError(f"checkpoint: bad --loop entry {text!r}")
        key, _, value = chunk.partition("=")
        loop[key.strip()] = value.strip()
    return loop


def cli(argv: Optional[List[str]] = None) -> int:
    """CLI entry: ``python3 -m levi.bot.checkpoint save|list``."""
    parser = argparse.ArgumentParser(
        prog="levi.bot.checkpoint",
        description="Checkpoint bot: save and resume open loops.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_save = sub.add_parser("save", help="save open loops to a checkpoint")
    p_save.add_argument(
        "--loop",
        action="append",
        default=[],
        help="one loop as k=v;k=v (title and next_step required); repeatable",
    )
    p_save.add_argument("--name", default="loops", help="checkpoint slug")
    p_save.add_argument("--base-dir", default=None)
    p_list = sub.add_parser("list", help="list newest open loops")
    p_list.add_argument("--base-dir", default=None)
    p_list.add_argument("--render", action="store_true", help="print the resume list")
    args = parser.parse_args(argv)
    if args.cmd == "save":
        try:
            record = save(
                [_loop_arg(t) for t in args.loop],
                name=args.name,
                base_dir=args.base_dir,
            )
        except CheckpointError as exc:
            print(f"checkpoint: {exc}", file=sys.stderr)
            return 2
        print(render(record))
        return 0
    loops = list_open(base_dir=args.base_dir)
    if args.render:
        print(render_list(loops))
    else:
        print(json.dumps([loop.to_dict() for loop in loops], indent=2))
    return 0


def main() -> None:
    sys.exit(cli())


if __name__ == "__main__":
    main()
