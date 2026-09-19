"""LEVI job organ — ENGINE 5 / PREP. Interview prep, resume map, cover letters.

Prep owns four workbook tables: Prep Hub (STAR stories, skills to
highlight, company research, questions to ask), Resume Map (versions by
role type), Cover Letter Bank (templates by role type), and the
cover-letter factory that assembles a draft from a template + profile +
listing.

The factory drafts only. It never sends, never submits, never
pretends a draft was delivered. Drafts carry ``draft: True`` until a
human approves them at the Apply gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .profiles import Profile
from .store import Warehouse


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- Prep Hub ------------------------------------------------------------


def build_prep_packet(
    warehouse: Warehouse,
    job_title: str,
    company: str,
    interview_date: str = "",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Scaffold a prep-hub record with blank STAR slots and prompt fields.
    The human (or Prep chains) fill the substance; the engine only
    provides the shape."""
    existing = [
        r
        for r in warehouse.list_rows("prep_hub")
        if str(r.get("job_title") or "").lower() == job_title.lower()
        and str(r.get("company") or "").lower() == company.lower()
    ]
    packet = {
        "job_title": job_title,
        "company": company,
        "interview_date": interview_date,
        "star_story_1": "",
        "star_story_2": "",
        "star_story_3": "",
        "skills_to_highlight": "",
        "company_research_notes": "",
        "questions_to_ask": "",
        "prep_status": "scaffolded",
        "notes": "draft packet — fill STAR stories before the interview",
    }
    record = dict(packet)
    if not dry_run:
        if existing:
            record = warehouse.update_row(
                "prep_hub",
                existing[0]["id"],
                {
                    "prep_status": "scaffolded",
                    "interview_date": interview_date
                    or existing[0].get("interview_date", ""),
                },
            )
        else:
            record = warehouse.add_row("prep_hub", packet)
    record["dry_run"] = dry_run
    return record


def update_prep(warehouse: Warehouse, record_id: int, **fields: Any) -> Dict[str, Any]:
    allowed = {
        "star_story_1",
        "star_story_2",
        "star_story_3",
        "skills_to_highlight",
        "company_research_notes",
        "questions_to_ask",
        "prep_status",
        "interview_date",
        "notes",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown prep fields: {sorted(unknown)}")
    return warehouse.update_row("prep_hub", record_id, fields)


# -- Resume Map ----------------------------------------------------------


def add_resume_version(
    warehouse: Warehouse, version_name: str, target_role_type: str = "", **fields: Any
) -> Dict[str, Any]:
    if not version_name.strip():
        raise ValueError("version_name is required")
    row = {"version_name": version_name.strip(), "target_role_type": target_role_type}
    row.update(fields)
    return warehouse.add_row("resume_map", row)


def pick_resume_version(
    warehouse: Warehouse, job_title: str
) -> Optional[Dict[str, Any]]:
    """Best-effort resume pick: first version whose target role type
    appears in the job title, else the first version, else None."""
    versions = warehouse.list_rows("resume_map")
    if not versions:
        return None
    title = job_title.lower()
    for v in versions:
        target = str(v.get("target_role_type") or "").lower()
        if target and target in title:
            return v
    return versions[0]


# -- Cover Letter Bank + factory -----------------------------------------


def add_template(
    warehouse: Warehouse,
    template_name: str,
    target_role_type: str = "",
    opening_hook: str = "",
    core_value_prop: str = "",
    closing_line: str = "",
) -> Dict[str, Any]:
    if not template_name.strip():
        raise ValueError("template_name is required")
    return warehouse.add_row(
        "cover_letter_bank",
        {
            "template_id": template_name.strip().lower().replace(" ", "-"),
            "template_name": template_name.strip(),
            "target_role_type": target_role_type,
            "opening_hook": opening_hook,
            "core_value_prop": core_value_prop,
            "closing_line": closing_line,
            "times_used": 0,
        },
    )


def pick_template(warehouse: Warehouse, job_title: str) -> Optional[Dict[str, Any]]:
    templates = warehouse.list_rows("cover_letter_bank")
    if not templates:
        return None
    title = job_title.lower()
    for t in templates:
        target = str(t.get("target_role_type") or "").lower()
        if target and target in title:
            return t
    return templates[0]


def compose_cover_letter(
    profile: Profile,
    listing: Dict[str, Any],
    template: Dict[str, Any],
) -> Dict[str, Any]:
    """Assemble a cover-letter DRAFT from template + profile + listing.

    ``{placeholders}`` in the template resolve against profile fields and
    the listing; unknown placeholders are left visible (``[name]``) so a
    half-filled draft can never pass as finished. The result is always a
    draft — approval happens at the Apply gate, never here.
    """
    full_name = str(profile.get("full_name") or "[your name]")
    email = str(profile.get("email") or "[your email]")
    phone = str(profile.get("phone") or "[your phone]")
    job_title = str(listing.get("job_title") or "[role]")
    company = str(listing.get("company") or "[company]")
    skills = ", ".join(profile.get("top_skills") or []) or "[your skills]"

    values = {
        "name": full_name,
        "email": email,
        "phone": phone,
        "job_title": job_title,
        "company": company,
        "skills": skills,
    }

    def fill(text: str) -> str:
        for key, val in values.items():
            text = text.replace("{" + key + "}", val)
        # anything still in braces was unknown — mark it visibly
        import re

        return re.sub(r"\{([^}]+)\}", r"[\1]", text)

    body = "\n\n".join(
        part
        for part in (
            fill(str(template.get("opening_hook") or "")),
            fill(str(template.get("core_value_prop") or "")),
            fill(str(template.get("closing_line") or "")),
        )
        if part
    )
    header = f"{full_name} | {email} | {phone}"
    letter = f"{header}\n\nRe: {job_title} at {company}\n\n{body}".strip()
    return {
        "draft": True,
        "template_id": template.get("template_id"),
        "template_name": template.get("template_name"),
        "job_title": job_title,
        "company": company,
        "text": letter,
        "composed_at": _utcnow(),
    }
