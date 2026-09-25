"""LEVI job organ — ENGINE 1 / SOURCING. Intake for the Review Buffer.

Sourcing takes listing dicts (from local files, the workbook, or the
human pasting them in) and stages them in ``review_buffer``. It does
three things before a listing earns a place in the buffer:

1. Dedupe: same URL, or same (title, company) pair, is refreshed in
   place — never duplicated.
2. Blacklist screen (via Intel): blacklisted company/role/board never
   enters the buffer; it is recorded as rejected with the reason.
3. Hard-restriction screen: listings that trip a hard restriction are
   parked as rejected, not scored.

Everything ingested is labeled ``hypothesis: True`` until a human or a
later engine verifies it — the organ never presents market data as fact.

Honest gap: the organ does NOT scrape job boards. Board rows in the
warehouse hold search queries and cadence; the actual fetching is the
human's browser or a browser agent's job. Sourcing consumes what those
produce.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import intel as intel_engine
from .store import Warehouse

LISTING_FIELDS = (
    "job_title",
    "company",
    "source_board",
    "url",
    "pay_range",
    "location_remote",
    "equipment_provided",
    "felony_friendly",
    "notes",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_listing(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce a raw listing dict onto the review_buffer column shape."""
    row: Dict[str, Any] = {}
    for key in LISTING_FIELDS:
        value = raw.get(key, "")
        row[key] = (
            value.strip()
            if isinstance(value, str)
            else (value if value is not None else "")
        )
    if not row["job_title"]:
        raise ValueError("listing needs a job_title")
    row["date_added"] = raw.get("date_added") or _utcnow()[:10]
    row["hypothesis"] = True
    return row


def _fingerprint(row: Dict[str, Any]) -> Optional[str]:
    url = str(row.get("url") or "").strip().lower()
    if url:
        return f"url:{url}"
    title = str(row.get("job_title") or "").strip().lower()
    company = str(row.get("company") or "").strip().lower()
    if title:
        return f"tc:{title}|{company}"
    return None


def ingest_listings(
    warehouse: Warehouse,
    listings: List[Dict[str, Any]],
    source_board: str = "manual",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Stage listings into the Review Buffer. Dry-run default: reports
    what would happen, writes nothing."""
    report: Dict[str, Any] = {
        "dry_run": dry_run,
        "staged": 0,
        "refreshed": 0,
        "rejected_blacklist": 0,
        "rejected_restriction": 0,
        "rejections": [],
        "items": [],
    }
    existing = {_fingerprint(r): r for r in warehouse.list_rows("review_buffer")}
    for raw in listings:
        try:
            row = normalize_listing(raw)
        except ValueError as exc:
            report["rejections"].append({"listing": raw, "reason": str(exc)})
            continue
        row["source_board"] = row.get("source_board") or source_board

        blocked, reason = intel_engine.check_blacklist(
            warehouse, company=row["company"], role=row["job_title"]
        )
        if blocked:
            report["rejected_blacklist"] += 1
            report["rejections"].append({"listing": row["job_title"], "reason": reason})
            continue

        hits = intel_engine.check_restrictions(warehouse, row)
        hard = [h for h in hits if h["severity"] == "hard"]
        if hard:
            report["rejected_restriction"] += 1
            detail = "; ".join(h["detail"] for h in hard)
            report["rejections"].append(
                {"listing": row["job_title"], "reason": f"hard restriction: {detail}"}
            )
            continue

        fp = _fingerprint(row)
        if fp and fp in existing:
            if not dry_run:
                prior = existing[fp]
                warehouse.update_row(
                    "review_buffer",
                    prior["id"],
                    {
                        "notes": (
                            str(prior.get("notes") or "")
                            + f" | refreshed {_utcnow()[:10]}"
                        ).strip(" |"),
                        "hypothesis": True,
                    },
                )
            report["refreshed"] += 1
            report["items"].append({"title": row["job_title"], "action": "refreshed"})
            continue

        if not dry_run:
            warehouse.add_row("review_buffer", row)
        report["staged"] += 1
        report["items"].append({"title": row["job_title"], "action": "staged"})

    return report
