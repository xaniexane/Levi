"""Herald — the notification dispatcher daemon.

Automation runs, daemons, and the engine notice things; the herald tells
the human. :class:`HeraldQueue` is an owner-only JSONL outbox at
``~/.levi/herald/queue.jsonl``. :func:`dispatch_once` delivers every
pending notice through the configured sinks and records a delivery
receipt per notice — delivered, failed, or honestly unavailable.

Sinks (all stdlib-only):
* :class:`LogSink` — appends to ``~/.levi/herald/notices.log``; always
  available, the default sink;
* :class:`StdoutSink` — prints; used for debugging;
* :class:`TermuxSink` — ``termux-notification`` when the tool exists
  (Android/Termux); otherwise reports ``unavailable`` honestly instead of
  pretending to notify.

``run()`` loops ``dispatch_once()`` every ``interval_sec`` until
``stop()`` or a stop-file appears — the long-run entry is
``python3 -m levi.daemon.herald`` inside the perpetual supervisor, or a
plain thread via ``run_in_thread()``.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

__all__ = [
    "Notice",
    "NoticeReceipt",
    "HeraldQueue",
    "LogSink",
    "StdoutSink",
    "TermuxSink",
    "SinkResult",
    "dispatch_once",
    "notify",
    "DEFAULT_QUEUE_PATH",
    "DEFAULT_LOG_PATH",
]

DEFAULT_DIR = Path.home() / ".levi" / "herald"
DEFAULT_QUEUE_PATH = DEFAULT_DIR / "queue.jsonl"
DEFAULT_LOG_PATH = DEFAULT_DIR / "notices.log"

_LEVELS = ("info", "warn", "urgent")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_only(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _owner_only_dir(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _owner_only_dir(path.parent)


@dataclass
class Notice:
    """One thing the human should hear about."""

    title: str
    body: str = ""
    level: str = "info"  # info | warn | urgent
    source: str = ""  # which subsystem queued it
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("Notice needs a non-empty title")
        if self.level not in _LEVELS:
            raise ValueError(f"level must be one of {_LEVELS}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notice":
        return cls(
            title=str(data.get("title", "")),
            body=str(data.get("body", "")),
            level=str(data.get("level", "info")),
            source=str(data.get("source", "")),
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            created_at=str(data.get("created_at", _utcnow())),
        )


@dataclass
class NoticeReceipt:
    notice_id: str
    delivered: bool
    channel: str
    detail: str = ""
    at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SinkResult:
    channel: str
    ok: bool
    detail: str = ""


class LogSink:
    """Append notices to the owner-only notices log. Always available."""

    channel = "log"

    def __init__(self, log_path: str | Path = DEFAULT_LOG_PATH) -> None:
        self.log_path = Path(log_path)

    @property
    def available(self) -> bool:
        return True

    def send(self, notice: Notice) -> SinkResult:
        _ensure_parent(self.log_path)
        line = (
            f"{notice.created_at} [{notice.level}] {notice.title}"
            + (f" — {notice.body}" if notice.body else "")
            + (f" (from {notice.source})" if notice.source else "")
            + "\n"
        )
        existed = self.log_path.exists()
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        if not existed:
            _owner_only(self.log_path)
        return SinkResult(channel=self.channel, ok=True, detail=str(self.log_path))


class StdoutSink:
    """Print notices. For debugging only."""

    channel = "stdout"

    @property
    def available(self) -> bool:
        return True

    def send(self, notice: Notice) -> SinkResult:
        print(f"[herald:{notice.level}] {notice.title}")
        if notice.body:
            print(f"  {notice.body}")
        return SinkResult(channel=self.channel, ok=True, detail="printed")


class TermuxSink:
    """Android/Termux system notifications via ``termux-notification``.

    Honest by construction: when the tool is absent, ``available`` is
    False and ``send`` returns ``ok=False`` — the herald records the
    attempt as unavailable instead of dropping the notice silently.
    """

    channel = "termux"

    def __init__(self, runner: Any = None) -> None:
        self._runner = runner

    @property
    def available(self) -> bool:
        return shutil.which("termux-notification") is not None

    def send(self, notice: Notice) -> SinkResult:
        if not self.available:
            return SinkResult(
                channel=self.channel,
                ok=False,
                detail="termux-notification not installed — notice not sent.",
            )
        argv = [
            "termux-notification",
            "--title",
            notice.title,
            "--content",
            notice.body or notice.title,
            "--priority",
            {"info": "low", "warn": "default", "urgent": "high"}[notice.level],
        ]
        run = self._runner or subprocess.run
        try:
            proc = run(argv, capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as exc:
            return SinkResult(
                channel=self.channel, ok=False, detail=f"could not run: {exc}"
            )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            return SinkResult(
                channel=self.channel,
                ok=False,
                detail=f"termux-notification exited {proc.returncode}: {err}",
            )
        return SinkResult(channel=self.channel, ok=True, detail="notified")


class HeraldQueue:
    """Owner-only JSONL outbox of pending notices."""

    def __init__(self, queue_path: str | Path = DEFAULT_QUEUE_PATH) -> None:
        self.queue_path = Path(queue_path)

    def enqueue(self, notice: Notice) -> str:
        _ensure_parent(self.queue_path)
        existed = self.queue_path.exists()
        with self.queue_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(notice.to_dict()) + "\n")
        if not existed:
            _owner_only(self.queue_path)
        return notice.id

    def pending(self) -> List[Notice]:
        if not self.queue_path.exists():
            return []
        notices: List[Notice] = []
        with self.queue_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if isinstance(data, dict) and not data.get("delivered"):
                    try:
                        notices.append(Notice.from_dict(data))
                    except ValueError:
                        continue
        return notices

    def mark_delivered(self, notice_id: str, receipt: NoticeReceipt) -> bool:
        """Rewrite the queue with the notice marked delivered.

        Returns True when the notice was found.
        """
        if not self.queue_path.exists():
            return False
        found = False
        rows: List[str] = []
        with self.queue_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except ValueError:
                    rows.append(raw)
                    continue
                if isinstance(data, dict) and data.get("id") == notice_id:
                    data["delivered"] = True
                    data["receipt"] = receipt.to_dict()
                    found = True
                    rows.append(json.dumps(data))
                else:
                    rows.append(raw)
        tmp = self.queue_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + ("\n" if rows else ""))
        _owner_only(tmp)
        os.replace(tmp, self.queue_path)
        return found


def notify(
    title: str,
    body: str = "",
    *,
    level: str = "info",
    source: str = "",
    queue: HeraldQueue | None = None,
) -> str:
    """Queue one notice for the herald. Returns the notice id."""
    q = queue or HeraldQueue()
    return q.enqueue(Notice(title=title, body=body, level=level, source=source))


def dispatch_once(
    sinks: List[Any] | None = None,
    queue: HeraldQueue | None = None,
) -> List[NoticeReceipt]:
    """Deliver every pending notice through each available sink.

    A notice counts as delivered when at least one sink reports ``ok``.
    When no sink is available, the receipt says so plainly and the notice
    stays pending for the next round — never silently dropped.
    """
    q = queue or HeraldQueue()
    sinks = sinks if sinks is not None else [LogSink()]
    receipts: List[NoticeReceipt] = []
    for notice in q.pending():
        delivered = False
        details: List[str] = []
        used = "none"
        for sink in sinks:
            if not getattr(sink, "available", True):
                details.append(f"{sink.channel}: unavailable")
                continue
            try:
                result = sink.send(notice)
            except Exception as exc:  # a broken sink must not kill dispatch
                details.append(f"{sink.channel}: error {type(exc).__name__}")
                continue
            details.append(f"{result.channel}: {result.detail or 'ok'}")
            if result.ok:
                delivered = True
                used = result.channel
                break
        receipt = NoticeReceipt(
            notice_id=notice.id,
            delivered=delivered,
            channel=used,
            detail="; ".join(details),
        )
        if delivered:
            q.mark_delivered(notice.id, receipt)
        receipts.append(receipt)
    return receipts


def run(
    interval_sec: float = 30.0,
    stop_file: str = "",
    sinks: List[Any] | None = None,
    queue: HeraldQueue | None = None,
) -> None:
    """Dispatch loop: ``dispatch_once()`` every ``interval_sec``."""
    stop = threading.Event()

    def _watch_stop() -> None:
        if not stop_file:
            return
        while not stop.is_set():
            if os.path.exists(stop_file):
                stop.set()
                return
            time.sleep(1.0)

    if stop_file:
        threading.Thread(target=_watch_stop, daemon=True).start()
    try:
        while not stop.is_set():
            dispatch_once(sinks=sinks, queue=queue)
            stop.wait(interval_sec)
    except KeyboardInterrupt:
        pass


def run_in_thread(**kwargs: Any) -> threading.Thread:
    thread = threading.Thread(target=run, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="levi.daemon.herald")
    sub = parser.add_subparsers(dest="cmd")

    notify_p = sub.add_parser("notify", help="queue one notice")
    notify_p.add_argument("--title", required=True)
    notify_p.add_argument("--body", default="")
    notify_p.add_argument("--level", choices=list(_LEVELS), default="info")
    notify_p.add_argument("--source", default="cli")

    dispatch_p = sub.add_parser("dispatch", help="deliver pending notices now")
    dispatch_p.add_argument(
        "--sink", choices=["log", "stdout", "termux"], action="append", default=[]
    )

    run_p = sub.add_parser("run", help="dispatch loop (default)")
    run_p.add_argument("--interval", type=float, default=30.0)
    run_p.add_argument("--stop-file", default="")

    args = parser.parse_args()
    if args.cmd == "notify":
        print(notify(args.title, args.body, level=args.level, source=args.source))
    elif args.cmd == "dispatch":
        sink_map = {"log": LogSink(), "stdout": StdoutSink(), "termux": TermuxSink()}
        sinks = [sink_map[s] for s in (args.sink or ["log"])]
        for receipt in dispatch_once(sinks=sinks):
            state = "delivered" if receipt.delivered else "PENDING"
            print(
                f"{state} {receipt.notice_id} via {receipt.channel}: {receipt.detail}"
            )
    else:
        run(
            interval_sec=getattr(args, "interval", 30.0),
            stop_file=getattr(args, "stop_file", ""),
        )
