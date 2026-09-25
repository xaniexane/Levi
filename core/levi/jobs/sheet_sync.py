"""HITL job-application pipeline — spreadsheet sync for the jobs tracker.

The original hunt finding was "HITL job-application prefill/submit +
**spreadsheet pipeline sync**". ``core/levi/jobs/tracker.py`` owns the
local-first pipeline (new → active → won/lost/dropped); this module is
the spreadsheet bridge: export the pipeline to CSV and import a CSV
back, so the pipeline can live in a real spreadsheet and stay in sync.

Direction of truth
------------------
The local tracker is the system of record; the CSV is a working copy.
Import never forces anything: rows whose status change would violate
the transition map are **skipped with a reason**, not forced.

LAWS
----
1. **Idempotent.** Export → import → export is a fixed point: no
   duplicates, no drift. Matching uses the tracker's identity key
   (title, company, source).
2. **Transitions stay lawful.** A CSV row can only move a job along
   allowed transitions; illegal moves are reported in ``skipped``.
3. **No silent invention.** Unknown statuses, missing titles, and
   malformed rows are skipped with reasons — never guessed into the
   pipeline.
4. **Local-first.** stdlib ``csv`` only; the "spreadsheet" is a CSV
   file, which every spreadsheet app reads and writes. (The warehouse's
   xlsx ``import_workbook`` covers the V2 workbook; this covers the
   live pipeline tracker.)

CSV columns: ``id,title,company,source,status,created_at,updated_at``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tracker import STATUSES, JobTracker

__all__ = ["COLUMNS", "export_csv", "import_csv", "SyncReport"]

COLUMNS = ("id", "title", "company", "source", "status", "created_at", "updated_at")


class SyncReport(Dict[str, Any]):
    """Plain-dict report: created / updated / skipped[(row, reason)]."""


def export_csv(tracker: JobTracker, path: "str | Path") -> int:
    """Write every tracked job to CSV. Returns the row count."""
    path = Path(path)
    rows = tracker.list()
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        writer.writeheader()
        for job in rows:
            writer.writerow(
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "source": job.source,
                    "status": job.status,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                }
            )
    return len(rows)


def import_csv(tracker: JobTracker, path: "str | Path") -> Dict[str, Any]:
    """Merge a CSV back into the tracker. Never forces transitions.

    Returns ``{"created": n, "updated": n, "skipped": [(row_no, reason)]}``.
    """
    path = Path(path)
    created = 0
    updated = 0
    skipped: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = [h for h in (reader.fieldnames or [])]
        missing = [c for c in ("title", "status") if c not in header]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
        for row_no, row in enumerate(reader, start=2):  # 1 = header
            title = (row.get("title") or "").strip()
            if not title:
                skipped.append({"row": row_no, "reason": "empty title"})
                continue
            status = (row.get("status") or "").strip()
            if status and status not in STATUSES:
                skipped.append({"row": row_no, "reason": f"unknown status {status!r}"})
                continue
            company = (row.get("company") or "").strip()
            source = (row.get("source") or "").strip() or "manual"
            # Match on (title, source): company is part of the identity key,
            # so a changed company is a different job — report, never merge.
            existing = next(
                (j for j in tracker.list()
                 if j.title.strip().casefold() == title.casefold()
                 and (j.source or "manual").strip().casefold() == source.casefold()),
                None,
            )
            if existing is None:
                tracker.add(title=title, company=company, source=source,
                            status=status or "new")
                created += 1
            else:
                if company.strip().casefold() != (existing.company or "").strip().casefold():
                    skipped.append({"row": row_no,
                                    "reason": "company differs from tracked job "
                                              "(identity key); not merged"})
                    continue
                if status and status != existing.status:
                    try:
                        tracker.move(existing.id, status)
                    except ValueError as exc:
                        skipped.append({"row": row_no, "reason": str(exc)})
                        continue
                    updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
