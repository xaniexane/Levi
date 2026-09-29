# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shared base for the DDD daily income daemons (PROVISIONAL names throughout).

LAWS — declared in plain words, enforced in code below:
  L1 DRAFT-ONLY: every output is a DRAFT-labeled markdown file written to
     the local inbox dir (``~/workspace/ddd-inbox/``). Nothing is sent,
     published, posted, or charged. Ever.
  L2 NO PAYMENT: no daemon accepts, charges, or processes payment, ever.
  L3 NO OUTBOUND: any task shaped like send/publish/post/charge/pay/
     outreach/contact is refused loudly via ``refuse_outbound``.
  L4 HONEST ZERO-STATE: queues start empty and stay Chauncey's to fill.
     A missing or empty queue yields an honest "nothing to work" receipt.
     Rows are never invented — not one business, item, or lead.
  L5 MULTI-RUN IDEMPOTENT: runs up to 3x/day (08:00/13:00/18:00
     America/Chicago). Row-level dedupe: a queue row drafted once is never
     drafted again the same day — drafted row signatures are tracked in
     the daily ledger, and each run drafts only the NEXT undrafted rows.
  L6 NAMED INPUT ONLY: daemons work only rows Chauncey himself queued.

Machine-checkable flags: ``advisory_only=True``, ``draft_only=True``,
``outbound_actions=()``, ``allowed_wares=()`` (zero outward capability).

NAMING: all display names are PROVISIONAL. Chauncey births every name;
final names await his word (naming sovereignty).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.ddd.agents.base import DDDOperatorAgent, DRAFT_BANNER
from levi.dynasty.dna import AgentError

__all__ = ["DDDDailyDaemon", "INBOX_DIR", "QUEUES_DIR", "RECEIPTS_DIR"]

#: Where draft outputs land. Local files only — never outbound.
INBOX_DIR = Path.home() / "workspace" / "ddd-inbox"
#: Where Chauncey's input queues live (read-only scans).
QUEUES_DIR = Path.home() / "workspace" / "ddd" / "queues"
#: Where per-day run receipts live (idempotency ledger).
RECEIPTS_DIR = QUEUES_DIR / ".receipts"


class DDDDailyDaemon(DDDOperatorAgent):
    """Draft-only daily daemon. Reads its queue, drafts income plays.

    Subclasses set ``daemon_id``, ``queue_filename``, ``queue_columns``
    and implement ``draft_for_rows(rows)`` returning ``(stem, text)``.
    """

    #: L1/L2 machine flags — asserted by tests on every subclass.
    advisory_only: bool = True
    draft_only: bool = True
    #: L3 — no outbound actions exist on these daemons, by construction.
    outbound_actions: tuple = ()
    #: Zero outward capability: no ware shelves open.
    allowed_wares: tuple = ()

    generation = 2
    commissioned_by = "ddd-daily-daemons"

    #: Overridden per daemon.
    daemon_id: str = "base-daemon"
    display_name: str = "Base Daemon (provisional)"
    queue_filename: str = ""
    #: Required CSV columns (documentation + validation).
    queue_columns: tuple = ()
    #: Max queue rows consumed per daily run.
    max_rows_per_day: int = 3

    def __init__(
        self,
        home: Optional[Path] = None,
        queues_dir: Optional[Path] = None,
        inbox_dir: Optional[Path] = None,
        receipts_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(home=home)
        self._queues_dir = Path(queues_dir) if queues_dir else QUEUES_DIR
        self._inbox_dir = Path(inbox_dir) if inbox_dir else INBOX_DIR
        self._receipts_dir = Path(receipts_dir) if receipts_dir else RECEIPTS_DIR

    # ── L4: honest queue loading ────────────────────────────────────
    def queue_path(self) -> Path:
        return self._queues_dir / self.queue_filename

    def load_queue(self) -> List[Dict[str, str]]:
        """Read the queue. Missing/unreadable/empty → [] (L4). Never invents."""
        path = self.queue_path()
        if not path.is_file():
            return []
        return self._read_rows(path, limit=500)

    # ── L5: 3x-daily runs, row-level dedupe ──────────────────────────
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _ledger_path(self, day: str) -> Path:
        """Daily ledger tracking which queue rows were already drafted."""
        return self._receipts_dir / f"{self.daemon_id}-{day}.json"

    @staticmethod
    def _row_signature(row: Dict[str, str]) -> str:
        """Stable fingerprint of one queue row (L5 dedupe key)."""
        canonical = json.dumps(row, sort_keys=True, ensure_ascii=True)
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()

    def _load_ledger(self, day: str) -> Dict[str, Any]:
        path = self._ledger_path(day)
        if path.is_file():
            try:
                ledger = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(ledger.get("drafted"), list) and isinstance(
                    ledger.get("runs"), list
                ):
                    return ledger
            except (OSError, ValueError):
                pass  # corrupt ledger: start fresh below
        return {"daemon_id": self.daemon_id, "date": day, "drafted": [], "runs": []}

    def _save_ledger(self, ledger: Dict[str, Any]) -> None:
        self._receipts_dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path(ledger["date"]).write_text(
            json.dumps(ledger, indent=2), encoding="utf-8"
        )

    # kept for backward compatibility with older single-run receipts
    def _receipt_path(self, day: str) -> Path:
        return self._ledger_path(day)

    def _store_receipt(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        self._receipts_dir.mkdir(parents=True, exist_ok=True)
        path = self._receipt_path(receipt["date"])
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt

    # ── L1: inbox drafts ────────────────────────────────────────────
    def write_inbox(self, stem: str, text: str) -> Optional[str]:
        """Write one DRAFT-labeled file to the inbox dir (L1).

        One file per daemon per day per stem — if it already exists the
        write is skipped (L5) and None is returned.
        """
        safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in stem)
        safe = safe.strip("-")[:60] or "draft"
        self._inbox_dir.mkdir(parents=True, exist_ok=True)
        path = (
            self._inbox_dir / f"{self._today()}-{self.daemon_id}-{safe}.md"
        ).resolve()
        if self._inbox_dir.resolve() not in path.parents:
            raise AgentError("inbox path escapes the inbox dir — refused")
        if path.exists():
            return None
        path.write_text(f"{DRAFT_BANNER}\n\n{text.rstrip()}\n", encoding="utf-8")
        return str(path)

    # ── the run (3x/day: drafts the NEXT undrafted rows) ─────────────
    def run_daily(self) -> Dict[str, Any]:
        """One run of the day's three. Returns the receipt (L4/L5).

        Each run drafts only queue rows not yet drafted today (L5 row
        dedupe); a run with nothing fresh returns an honest
        "already-drafted" receipt and writes nothing new.
        """
        day = self._today()
        qpath = self.queue_path()

        if not qpath.is_file():
            return self._store_receipt(
                {
                    "daemon_id": self.daemon_id,
                    "date": day,
                    "queue": str(qpath),
                    "rows_seen": 0,
                    "drafts_written": [],
                    "status": "no-queue",
                    "note": (
                        "queue file not found — Chauncey has not filled it "
                        "yet. Nothing invented, nothing drafted."
                    ),
                    "checked_at": self._checked_at(),
                }
            )
        rows = self.load_queue()
        if not rows:
            return self._store_receipt(
                {
                    "daemon_id": self.daemon_id,
                    "date": day,
                    "queue": str(qpath),
                    "rows_seen": 0,
                    "drafts_written": [],
                    "status": "empty-queue",
                    "note": (
                        "queue is empty — nothing to work today. "
                        "Nothing invented, nothing drafted."
                    ),
                    "checked_at": self._checked_at(),
                }
            )

        ledger = self._load_ledger(day)
        drafted = set(ledger["drafted"])
        fresh = [r for r in rows if self._row_signature(r) not in drafted]
        run_no = len(ledger["runs"]) + 1

        if not fresh:
            receipt = {
                "daemon_id": self.daemon_id,
                "date": day,
                "queue": str(qpath),
                "rows_seen": len(rows),
                "rows_used": 0,
                "drafts_written": [],
                "status": "already-drafted",
                "note": (
                    "every queue row was already drafted today — nothing "
                    "new to draft (row-level dedupe). Nothing invented."
                ),
                "checked_at": self._checked_at(),
            }
            ledger["runs"].append(
                {
                    "run_no": run_no,
                    "rows_used": 0,
                    "status": "already-drafted",
                    "checked_at": receipt["checked_at"],
                }
            )
            self._save_ledger(ledger)
            return receipt

        taken = fresh[: self.max_rows_per_day]
        stem, text = self.draft_for_rows(taken)
        stem = f"{stem}-run{run_no}"
        written = self.write_inbox(stem, text)
        for r in taken:
            sig = self._row_signature(r)
            if sig not in drafted:
                drafted.add(sig)
                ledger["drafted"].append(sig)
        receipt = {
            "daemon_id": self.daemon_id,
            "date": day,
            "queue": str(qpath),
            "rows_seen": len(rows),
            "rows_used": len(taken),
            "drafts_written": [written] if written else [],
            "status": "ok",
            "note": (
                f"drafted from {len(taken)} queued row(s) — "
                "draft only, waits on Chauncey's word."
            ),
            "checked_at": self._checked_at(),
        }
        ledger["runs"].append(
            {
                "run_no": run_no,
                "rows_used": len(taken),
                "status": "ok",
                "checked_at": receipt["checked_at"],
            }
        )
        self._save_ledger(ledger)
        return receipt

    def draft_for_rows(self, rows: List[Dict[str, str]]) -> tuple:  # pragma: no cover
        raise NotImplementedError

    def watch(self) -> Dict[str, Any]:
        rows = self.load_queue()
        ledger = self._load_ledger(self._today())
        return {
            "daemon_id": self.daemon_id,
            "queue": str(self.queue_path()),
            "rows_queued": len(rows),
            "max_rows_per_day": self.max_rows_per_day,
            "runs_today": len(ledger["runs"]),
            "drafted_today": len(ledger["drafted"]),
            "checked_at": self._checked_at(),
        }

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "run":
            return self.run_daily()
        raise AgentError(f"{self.daemon_id}: unknown task kind {kind!r}")
