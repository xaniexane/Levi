"""LEVI job organ — warehouse store. The recovered 19-sheet V2 workbook is
the schema backbone: every table here mirrors one workbook sheet, column
for column, so the organ and the workbook speak one language.

Tables (workbook sheet -> store table):
  Review Buffer, Jobs Pipeline, Apply Queue, Application Log, Interviews,
  Offers and Decisions, Prep Hub, Resume Map, Cover Letter Bank,
  Skills Matrix, User Profile (profiles live in profiles.py instead),
  Job Boards, Company Intel, Restrictions and Filters, Blacklist,
  Automation Logs, Training and Courses, Job History Archive,
plus ``gig_offers`` and ``gig_income`` for the parallel fast-cash track.

State lives under ``<jobs_dir>/warehouse/<table>.json`` (dir 0700, file
0600). Rows are plain dicts with an autoincrement ``id`` per table.
``import_workbook`` reads the V2 xlsx into the warehouse.

Local only. No network, no scraping, no randomness.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# table -> (workbook sheet name, columns in sheet order)
TABLES: Dict[str, Tuple[str, List[str]]] = {
    "review_buffer": (
        "Review Buffer",
        [
            "date_added",
            "job_title",
            "company",
            "source_board",
            "url",
            "pay_range",
            "location_remote",
            "equipment_provided",
            "felony_friendly",
            "match_score",
            "action_taken",
            "priority",
            "notes",
        ],
    ),
    "jobs_pipeline": (
        "Jobs Pipeline",
        [
            "job_id",
            "job_title",
            "company",
            "source_board",
            "url",
            "location",
            "remote_type",
            "pay_range",
            "hours",
            "equipment_provided",
            "felony_friendly",
            "date_found",
            "status",
            "priority",
            "match_score",
            "days_open",
            "notes",
        ],
    ),
    "apply_queue": (
        "Apply Queue",
        [
            "priority_rank",
            "job_title",
            "company",
            "url",
            "apply_method",
            "resume_version",
            "cover_letter",
            "deadline",
            "assigned_to",
            "estimated_time_min",
            "status",
            "completed",
            "notes",
        ],
    ),
    "application_log": (
        "Application Log",
        [
            "app_no",
            "date_applied",
            "job_title",
            "company",
            "source",
            "url",
            "resume_version",
            "cover_letter_used",
            "apply_method",
            "confirmation_received",
            "follow_up_date",
            "response_received",
            "response_type",
            "current_status",
            "days_since_applied",
            "notes",
        ],
    ),
    "interviews": (
        "Interviews",
        [
            "interview_no",
            "date_scheduled",
            "time",
            "company",
            "job_title",
            "interview_type",
            "platform",
            "interviewer_name",
            "interviewer_email",
            "prep_completed",
            "outcome",
            "follow_up_sent",
            "next_step",
            "notes",
        ],
    ),
    "offers_decisions": (
        "Offers and Decisions",
        [
            "offer_no",
            "date_received",
            "company",
            "job_title",
            "offer_salary",
            "benefits_summary",
            "start_date",
            "response_deadline",
            "decision",
            "accepted_declined",
            "reason",
            "notes",
        ],
    ),
    "prep_hub": (
        "Prep Hub",
        [
            "job_title",
            "company",
            "interview_date",
            "star_story_1",
            "star_story_2",
            "star_story_3",
            "skills_to_highlight",
            "company_research_notes",
            "questions_to_ask",
            "prep_status",
            "notes",
        ],
    ),
    "resume_map": (
        "Resume Map",
        [
            "resume_version",
            "version_name",
            "target_role_type",
            "target_industry",
            "key_skills_highlighted",
            "last_updated",
            "file_location",
            "times_used",
            "success_rate",
            "notes",
        ],
    ),
    "cover_letter_bank": (
        "Cover Letter Bank",
        [
            "template_id",
            "template_name",
            "target_role_type",
            "opening_hook",
            "core_value_prop",
            "closing_line",
            "last_used",
            "times_used",
            "success_rate",
            "notes",
        ],
    ),
    "skills_matrix": (
        "Skills Matrix",
        [
            "skill_name",
            "category",
            "proficiency",
            "years_experience",
            "certified",
            "cert_name",
            "job_relevance",
            "in_resume",
            "notes",
        ],
    ),
    "job_boards": (
        "Job Boards",
        [
            "board_name",
            "url",
            "account_status",
            "search_query_1",
            "search_query_2",
            "search_query_3",
            "check_frequency",
            "last_checked",
            "avg_jobs_found",
            "rating",
            "auto_search_enabled",
            "notes",
        ],
    ),
    "company_intel": (
        "Company Intel",
        [
            "company_name",
            "industry",
            "size",
            "website",
            "glassdoor_rating",
            "felony_friendly",
            "remote_policy",
            "hiring_frequency",
            "key_contact",
            "watchlist",
            "notes",
        ],
    ),
    "restrictions_filters": (
        "Restrictions and Filters",
        [
            "restriction_type",
            "restriction_detail",
            "severity",
            "reason",
            "date_added",
            "active",
            "notes",
        ],
    ),
    "blacklist": (
        "Blacklist",
        [
            "entry_type",
            "name",
            "reason",
            "date_blacklisted",
            "severity",
            "active",
            "notes",
        ],
    ),
    "automation_logs": (
        "Automation Logs",
        [
            "log_no",
            "timestamp",
            "action_type",
            "tool_used",
            "target_platform",
            "job_title_processed",
            "result",
            "error_message",
            "retry_attempted",
            "notes",
        ],
    ),
    "training_courses": (
        "Training and Courses",
        [
            "course_name",
            "platform",
            "url",
            "category",
            "status",
            "start_date",
            "complete_date",
            "cert_earned",
            "cert_name",
            "job_search_relevance",
            "notes",
        ],
    ),
    "job_history_archive": (
        "Job History Archive",
        [
            "company",
            "job_title",
            "employment_type",
            "start_date",
            "end_date",
            "duration",
            "salary",
            "location",
            "reason_for_leaving",
            "use_as_reference",
            "reference_name",
            "reference_contact",
            "notes",
        ],
    ),
    # Parallel fast-cash track (organ-native tables, no workbook sheet).
    "gig_offers": (
        "",
        [
            "offer_id",
            "platform",
            "title",
            "pay",
            "pay_unit",
            "window_start",
            "window_end",
            "location",
            "distance_mi",
            "expires_at",
            "status",
            "rule_verdict",
            "notes",
        ],
    ),
    "gig_income": (
        "",
        [
            "income_id",
            "date",
            "platform",
            "description",
            "amount",
            "hours_worked",
            "notes",
        ],
    ),
}

_SEQ_FILE = "_seq.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_warehouse_dir(jobs_dir: Optional[Path] = None) -> Path:
    base = jobs_dir or (Path.home() / ".levi" / "jobs")
    return base / "warehouse"


class Warehouse:
    """JSON-per-table warehouse under ``<jobs_dir>/warehouse/``."""

    def __init__(self, jobs_dir: Optional[Path] = None) -> None:
        self.dir = default_warehouse_dir(jobs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self._seq_path = self.dir / _SEQ_FILE
        if not self._seq_path.exists():
            self._write_json(self._seq_path, {})

    # -- low-level ------------------------------------------------------
    def _table_path(self, table: str) -> Path:
        if table not in TABLES:
            raise ValueError(f"unknown warehouse table {table!r}")
        return self.dir / f"{table}.json"

    def _write_json(self, path: Path, data: Any) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _next_id(self, table: str) -> int:
        seq = self._read_json(self._seq_path, {})
        nxt = int(seq.get(table, 0)) + 1
        seq[table] = nxt
        self._write_json(self._seq_path, seq)
        return nxt

    # -- rows -----------------------------------------------------------
    def add_row(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.list_rows(table)
        record = dict(row)
        record["id"] = self._next_id(table)
        record.setdefault("created_at", _utcnow())
        record["updated_at"] = _utcnow()
        rows.append(record)
        self._write_json(self._table_path(table), rows)
        return record

    def list_rows(self, table: str) -> List[Dict[str, Any]]:
        return list(self._read_json(self._table_path(table), []))

    def get_row(self, table: str, row_id: int) -> Dict[str, Any]:
        for row in self.list_rows(table):
            if row.get("id") == row_id:
                return row
        raise KeyError(f"no row id={row_id} in {table}")

    def update_row(
        self, table: str, row_id: int, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        rows = self.list_rows(table)
        for i, row in enumerate(rows):
            if row.get("id") == row_id:
                row = dict(row)
                row.update(updates)
                row["updated_at"] = _utcnow()
                rows[i] = row
                self._write_json(self._table_path(table), rows)
                return row
        raise KeyError(f"no row id={row_id} in {table}")

    def remove_row(self, table: str, row_id: int) -> None:
        rows = self.list_rows(table)
        kept = [r for r in rows if r.get("id") != row_id]
        if len(kept) == len(rows):
            raise KeyError(f"no row id={row_id} in {table}")
        self._write_json(self._table_path(table), kept)

    def find(self, table: str, **match: Any) -> List[Dict[str, Any]]:
        return [
            r
            for r in self.list_rows(table)
            if all(r.get(k) == v for k, v in match.items())
        ]

    # -- automation log --------------------------------------------------
    def log_automation(
        self, action_type: str, result: str, **fields: Any
    ) -> Dict[str, Any]:
        rows = self.list_rows("automation_logs")
        record = {
            "log_no": len(rows) + 1,
            "timestamp": _utcnow(),
            "action_type": action_type,
            "result": result,
        }
        record.update(fields)
        return self.add_row("automation_logs", record)


def import_workbook(path: "str | Path", warehouse: Warehouse) -> Dict[str, int]:
    """Read the V2 xlsx (19 sheets) into the warehouse. Sheets map onto
    tables by header row 2; data rows start at row 3. Empty rows are
    skipped. Sheet names not in the schema are reported, not imported.

    Requires openpyxl (present in the sandbox; optional dependency here).
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("import_workbook needs openpyxl installed") from exc

    sheet_to_table = {sheet: table for table, (sheet, _cols) in TABLES.items() if sheet}
    counts: Dict[str, int] = {}
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    for sheet_name in wb.sheetnames:
        table = sheet_to_table.get(sheet_name)
        if table is None:
            counts[f"SKIPPED:{sheet_name}"] = 0
            continue
        _, columns = TABLES[table]
        ws = wb[sheet_name]
        header = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
        idx: Dict[str, int] = {}
        for i, h in enumerate(header):
            if not h:
                continue
            # "Equipment Provided (Y/N)" -> "equipment provided"
            # "Location/Remote"            -> "location remote"
            norm = str(h).split("(")[0].replace("/", " ").strip().lower()
            idx[norm] = i
        imported = 0
        for raw in ws.iter_rows(min_row=3, values_only=True):
            if not any(raw):
                continue
            row: Dict[str, Any] = {"source": "workbook"}
            for col in columns:
                pretty = col.replace("_", " ")
                pos = idx.get(pretty)
                if pos is not None and pos < len(raw) and raw[pos] not in (None, ""):
                    row[col] = raw[pos]
            if len(row) > 1:
                warehouse.add_row(table, row)
                imported += 1
        counts[table] = imported
    return counts
