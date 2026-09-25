"""DemandPulse Watch — the live tracker of everything.

DemandPulse is the operator overall: it keeps watch over ALL work and
tracks status for every system, goal, build, and open thread.

LAWS (plain words):
  W1 fixed statuses — an item's status is exactly one of
     {queued, in_progress, blocked, held, complete}. Anything else is
     rejected at the boundary, never stored.
  W2 append-only history — every status change appends one event to the
     history log. History is never rewritten, edited, or truncated.
  W3 snapshot + log — the registry file is a snapshot; the JSONL log is
     the source of truth. The snapshot must always equal a replay of the
     log (machine-checked by ``check_laws``).
  W4 nothing deleted — no item is ever removed. Completed items stay as
     permanent record (the nothing-thrown-away law).
  W5 honest waiters — ``waiting_on`` is exactly one of {him, me, none}:
     him = Chauncey's move, me = an agent's move, none = done/free.
  W6 honest seed — seeded items reflect the map and the standing list as
     surveyed; statuses marked per evidence, never invented.

State lives OUTSIDE the repo (live state, not code):
  ~/workspace/demandpulse-watch/registry.json   (snapshot)
  ~/workspace/demandpulse-watch/history.jsonl   (append-only log)

Stdlib only. Entry: ``levi demandpulse watch``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# laws (machine-checkable)

STATUSES = ("queued", "in_progress", "blocked", "held", "complete")
WAITERS = ("him", "me", "none")
ALERT_STATUSES = ("complete", "blocked")  # queue a line to the alert pipeline

LAWS = (
    "W1 fixed statuses: status in {queued, in_progress, blocked, held, complete}",
    "W2 append-only history: status changes append events, never rewrite",
    "W3 snapshot + log: snapshot equals replay of the history log",
    "W4 nothing deleted: completed items stay as permanent record",
    "W5 honest waiters: waiting_on in {him, me, none}",
    "W6 honest seed: seeded items reflect the surveyed map/standing list",
)


class WatchError(RuntimeError):
    """Base for all watch errors."""


class InvalidStatusError(WatchError):
    """Status outside STATUSES — rejected at the boundary (W1)."""


class InvalidWaiterError(WatchError):
    """waiting_on outside WAITERS — rejected at the boundary (W5)."""


class UnknownItemError(WatchError):
    """No item with that id."""


# ---------------------------------------------------------------------------
# paths

def watch_dir() -> Path:
    base = Path(
        os.environ.get(
            "DEMANDPULSE_WATCH_DIR",
            str(Path.home() / "workspace" / "demandpulse-watch"),
        )
    )
    return base


def registry_path() -> Path:
    return watch_dir() / "registry.json"


def history_path() -> Path:
    return watch_dir() / "history.jsonl"


def alert_outbox_path() -> Path:
    """The DemandPulse file outbox the device alerter already drains."""
    home = Path(os.environ.get("LEVI_HOME", str(Path.home())))
    return home / ".levi" / "demand_alerts_outbox.jsonl"


NOTIFY_SCRIPT = Path.home() / "workspace" / "bin" / "notify-chauncey.sh"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:48] or "item"


# ---------------------------------------------------------------------------
# registry

class WatchRegistry:
    """Snapshot + append-only log of everything under watch."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or watch_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._items: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> None:
        p = self.root / "registry.json"
        if p.exists():
            with p.open(encoding="utf-8") as fh:
                data = json.load(fh)
            self._items = data.get("items", {})
        else:
            self._items = {}

    def _save(self) -> None:
        p = self.root / "registry.json"
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(
                {"items": self._items, "updated_at": _utcnow()},
                fh,
                indent=2,
                sort_keys=True,
            )
        tmp.replace(p)

    def _append_history(self, event: Dict[str, Any]) -> Dict[str, Any]:
        p = self.root / "history.jsonl"
        seq = self._history_len() + 1
        event = {"seq": seq, "ts": _utcnow(), **event}
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def _history_len(self) -> int:
        p = self.root / "history.jsonl"
        if not p.exists():
            return 0
        n = 0
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    n += 1
        return n

    def history(self) -> List[Dict[str, Any]]:
        p = self.root / "history.jsonl"
        if not p.exists():
            return []
        out: List[Dict[str, Any]] = []
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    out.append(json.loads(ln))
        return out

    def history_for(self, item_id: str) -> List[Dict[str, Any]]:
        if item_id not in self._items:
            raise UnknownItemError(f"no watch item {item_id!r}")
        return [e for e in self.history() if e.get("id") == item_id]

    # -- mutations --------------------------------------------------------

    def add(
        self,
        name: str,
        area: str,
        status: str = "queued",
        note: str = "",
        waiting_on: str = "none",
    ) -> Dict[str, Any]:
        """Add an item. W1/W5 enforced at the boundary."""
        if status not in STATUSES:
            raise InvalidStatusError(
                f"status {status!r} not in {list(STATUSES)}"
            )
        if waiting_on not in WAITERS:
            raise InvalidWaiterError(
                f"waiting_on {waiting_on!r} not in {list(WAITERS)}"
            )
        base = _slug(name)
        item_id = base
        n = 2
        while item_id in self._items:
            item_id = f"{base}-{n}"
            n += 1
        item = {
            "id": item_id,
            "name": name,
            "area": area,
            "status": status,
            "waiting_on": waiting_on,
            "note": note,
            "updated_at": _utcnow(),
        }
        self._items[item_id] = item
        self._append_history(
            {"event": "created", "id": item_id, "to": status, "note": note}
        )
        self._save()
        return dict(item)

    def set_status(
        self,
        item_id: str,
        status: str,
        note: str = "",
        *,
        ping: bool = False,
    ) -> Dict[str, Any]:
        """Change an item's status. Appends history (W2); alerts on
        complete/blocked via the alert pipeline; nothing ever deleted (W4)."""
        if status not in STATUSES:
            raise InvalidStatusError(
                f"status {status!r} not in {list(STATUSES)}"
            )
        item = self._items.get(item_id)
        if item is None:
            raise UnknownItemError(f"no watch item {item_id!r}")
        old = item["status"]
        if old == status and not note:
            return dict(item)  # not a change — no history event (W2)
        item["status"] = status
        if note:
            item["note"] = note
        item["updated_at"] = _utcnow()
        self._append_history(
            {"event": "status", "id": item_id, "from": old, "to": status,
             "note": note}
        )
        self._save()
        if status in ALERT_STATUSES:
            self._queue_alert(item, old, status)
            if ping:
                self._ping_chauncey(item, status)
        return dict(item)

    def set_waiter(self, item_id: str, waiting_on: str) -> Dict[str, Any]:
        if waiting_on not in WAITERS:
            raise InvalidWaiterError(
                f"waiting_on {waiting_on!r} not in {list(WAITERS)}"
            )
        item = self._items.get(item_id)
        if item is None:
            raise UnknownItemError(f"no watch item {item_id!r}")
        old = item["waiting_on"]
        if old == waiting_on:
            return dict(item)
        item["waiting_on"] = waiting_on
        item["updated_at"] = _utcnow()
        self._append_history(
            {"event": "waiter", "id": item_id, "from": old, "to": waiting_on}
        )
        self._save()
        return dict(item)

    # -- reads ------------------------------------------------------------

    def get(self, item_id: str) -> Dict[str, Any]:
        item = self._items.get(item_id)
        if item is None:
            raise UnknownItemError(f"no watch item {item_id!r}")
        return dict(item)

    def items(self) -> List[Dict[str, Any]]:
        return [dict(v) for v in self._items.values()]

    def board(self) -> Dict[str, Any]:
        """Grouped view: counts at top, items per status."""
        groups: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STATUSES}
        for item in self._items.values():
            groups[item["status"]].append(item)
        for lst in groups.values():
            lst.sort(key=lambda i: i["name"].lower())
        return {
            "counts": {s: len(groups[s]) for s in STATUSES},
            "total": len(self._items),
            "groups": groups,
        }

    # -- alert pipeline hook ----------------------------------------------

    def _queue_alert(
        self, item: Dict[str, Any], old: str, new: str
    ) -> Dict[str, Any]:
        """Queue a short line into the DemandPulse alert outbox — the
        store the on-device alerter already drains. Extends the pipeline;
        the alerter itself is untouched. Body kept short for SMS."""
        seq = self._history_len()
        line = (
            f"{item['name']} → {new}"
            + (f" — {item['note'][:100]}" if item.get("note") else "")
        )
        rec = {
            "dedup_key": f"watch:{item['id']}:{new}:{seq}",
            "title": f"Watch: {item['name']}",
            "kind": f"watch:{new}",
            "body": line[:160],
            "item_id": item["id"],
            "from": old,
            "to": new,
            "ts": _utcnow(),
        }
        path = alert_outbox_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def _ping_chauncey(self, item: Dict[str, Any], status: str) -> None:
        """Immediate sandbox-side ping via the notifier script. SMS body
        stays within the script's 160-char cap. Never carries secrets."""
        if not NOTIFY_SCRIPT.exists():
            return
        msg = f"Watch: {item['name']} → {status}"
        if item.get("note"):
            msg += f" — {item['note'][:100]}"
        subprocess.run(
            [
                str(NOTIFY_SCRIPT),
                "--subject",
                f"Watch: {item['name']}",
                "--message",
                msg,
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )

    # -- machine proof ----------------------------------------------------

    def check_laws(self) -> Dict[str, Any]:
        """Replay the history log and prove W1..W4 structurally."""
        problems: List[str] = []
        seen: Dict[str, Dict[str, Any]] = {}
        last_seq = 0
        for ev in self.history():
            seq = ev.get("seq")
            if not isinstance(seq, int) or seq != last_seq + 1:
                problems.append(f"history seq break at {ev!r}")
                break
            last_seq = seq
            kind = ev.get("event")
            iid = ev.get("id")
            if kind == "created":
                if iid in seen:
                    problems.append(f"duplicate created for {iid!r}")
                to = ev.get("to")
                if to not in STATUSES:
                    problems.append(f"W1: illegal seeded status {to!r}")
                seen[iid] = {"status": to, "waiting_on": "none"}
            elif kind == "status":
                if iid not in seen:
                    problems.append(f"status event for unknown {iid!r}")
                    continue
                to = ev.get("to")
                if to not in STATUSES:
                    problems.append(f"W1: illegal status {to!r} for {iid!r}")
                seen[iid]["status"] = to
            elif kind == "waiter":
                to = ev.get("to")
                if to not in WAITERS:
                    problems.append(f"W5: illegal waiter {to!r} for {iid!r}")
                if iid in seen:
                    seen[iid]["waiting_on"] = to
            else:
                problems.append(f"unknown history event {kind!r}")
        # W3: snapshot must equal replay
        for iid, item in self._items.items():
            if iid not in seen:
                problems.append(f"W3/W4: snapshot item {iid!r} has no history")
            elif seen[iid]["status"] != item["status"]:
                problems.append(
                    f"W3: snapshot/replay mismatch for {iid!r}: "
                    f"{item['status']!r} != {seen[iid]['status']!r}"
                )
            if item["status"] not in STATUSES:
                problems.append(f"W1: snapshot illegal status for {iid!r}")
            if item.get("waiting_on") not in WAITERS:
                problems.append(f"W5: snapshot illegal waiter for {iid!r}")
        for iid in seen:
            if iid not in self._items:
                problems.append(f"W4: history item {iid!r} missing from snapshot")
        return {"ok": not problems, "laws": list(LAWS), "problems": problems}


# ---------------------------------------------------------------------------
# seed (W6: reflects MAP_OF_EVERYTHING.md §6 + standing list, 2026-09-23)

# (name, area, status, waiting_on, note)
STANDING_SEED = [
    # -- open threads ----------------------------------------------------
    ("780 staged deletions in repo", "thread", "held", "him",
     "awaiting his ruling: keep vs restore; worktree intact, nothing lost"),
    ("Vault re-key", "thread", "blocked", "him",
     "needs his current passphrase via local interactive entry, never chat"),
    ("Phone alerter install", "thread", "blocked", "him",
     "Termux:API + setup-alerter.sh + 30-min job on the Moto G; slice is in his files"),
    ("Sheets/WhatsApp push routes", "thread", "held", "him",
     "his move; Void Box relay now the preferred route per his word"),
    ("archive.org cold-storage upload", "thread", "held", "him",
     "outer zip chauncey-parked-all-2026-09-23.7z in his files; upload on his word"),
    ("Free-core creed resolution", "thread", "held", "him",
     "code still says free-core-forever; live law is paid-but-tiny; his word settles it"),
    ("God program original pull", "thread", "blocked", "him",
     "originals-first: pull his Grok original before drafting; no seat build per his ruling"),
    ("Pulse canon cleanup", "thread", "held", "him",
     "CyberPulse/Omnipulse stubs vs three-level model + DemandPulse Prime; needs his ruling"),
    # -- systems ----------------------------------------------------------
    ("DemandPulse", "system", "complete", "none",
     "engine/app/persona, operator overall; SMS alerter + YES/NO approvals live"),
    ("NeighborOS", "system", "complete", "none",
     "live; nudges flow to the SMS alerter"),
    ("LEVI native brain", "system", "complete", "none",
     "weights trained, loss 5.28→2.11"),
    ("Device alerter", "system", "complete", "none",
     "Termux SMS drain + approvals built; phone install pending (see thread)"),
    ("Alpha", "system", "complete", "none", "founder seat built"),
    ("Omega", "system", "complete", "none",
     "built; god-program title Divine; no seat per his ruling"),
    ("Nexus/Echo", "system", "complete", "none", "origin seat built"),
    ("Hicomb", "system", "in_progress", "me",
     "from-scratch code editor; goal active"),
    ("Cybrus", "system", "complete", "none",
     "watchdog barks flow to the alerter; shield goal active"),
    ("Void Box", "system", "complete", "none",
     "messenger + channels + relay built; relay push build queued"),
    ("Echoverse", "system", "complete", "none",
     "rebuilt on his originals 2026-09-22"),
    ("UniForge", "system", "complete", "none", "built"),
    ("King", "system", "complete", "none", "control plane built"),
    ("Finance", "system", "complete", "none",
     "paper-only; live trading structurally disabled"),
    ("CyberPulse", "system", "held", "him",
     "stub; canon cleanup ruling needed"),
    ("Omnipulse", "system", "held", "him",
     "stub; canon cleanup ruling needed"),
    ("Vault", "system", "blocked", "him",
     "stub; re-key blocked on his passphrase"),
    ("Dynasty", "system", "complete", "none",
     "built; eyes-only, never public"),
    # -- builds ------------------------------------------------------------
    ("Void Box relay push channel", "build", "queued", "me",
     "alerts land in Void Box messenger rooms; SMS stays personal fallback"),
    ("SMS done-ping on build completions", "build", "queued", "me",
     "text names the file, file attached in chat; no fake hyperlinks"),
    ("DemandPulse Watch tracker", "build", "in_progress", "me",
     "this build: live status board for everything"),
    # -- goals ---------------------------------------------------------------
    ("28 goal workspaces", "goal", "in_progress", "me",
     "all active per map; no ATTENTION flags; goal↔module index still owed"),
]


def seed(reg: Optional[WatchRegistry] = None) -> WatchRegistry:
    """Seed a fresh registry from the standing list. Idempotent: seeding a
    non-empty registry is a no-op."""
    reg = reg or WatchRegistry()
    if reg.items():
        return reg
    for name, area, status, waiting_on, note in STANDING_SEED:
        reg.add(name, area, status=status, note=note, waiting_on=waiting_on)
    return reg


# ---------------------------------------------------------------------------
# board rendering (plain speech for Chauncey)

def render_board(b: Dict[str, Any]) -> str:
    lines = []
    counts = b["counts"]
    lines.append("DemandPulse Watch — everything, one board")
    lines.append(
        "  complete={complete}  in_progress={in_progress}  queued={queued}  "
        "blocked={blocked}  held={held}  (total {total})".format(
            total=b["total"], **counts
        )
    )
    waiter_of = {"him": "his move", "me": "my move", "none": "—"}
    for status in STATUSES:
        items = b["groups"][status]
        if not items:
            continue
        lines.append(f"\n[{status}] ({len(items)})")
        for it in items:
            w = waiter_of.get(it["waiting_on"], "?")
            lines.append(f"  • {it['id']}: {it['name']} [{it['area']}] — {w}")
            if it.get("note"):
                lines.append(f"      {it['note']}")
    return "\n".join(lines)
