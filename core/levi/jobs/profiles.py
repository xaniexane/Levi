"""LEVI job organ — user profiles. The universal engine never hardcodes a person.

One profile per human. Chauncey's information is ONE profile record —
never a literal in engine code, never a default. The organ reads only
the profile it is told to use; fields not set are simply absent and the
engines degrade honestly (scoring notes the missing signal instead of
inventing it).

Profile fields mirror the workbook's "User Profile" sheet so the
warehouse and the organ speak the same schema.

State lives under ``<jobs_dir>/profiles/<name>.json`` with owner-only
permissions (dir 0700, file 0600). Schema is deny-closed: setting an
unknown field raises instead of silently storing it.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROFILE_FIELDS = (
    "full_name",
    "email",
    "phone",
    "mailing_address",
    "city_state_zip",
    "devices",
    "equipment_status",
    "driver_license",
    "felony_on_record",
    "target_pay_min",
    "target_pay_max",
    "target_hours",
    "remote_preference",
    "willing_to_relocate",
    "top_skills",
    "job_types_target",
    "job_types_avoid",
    "notes",
)

_LIST_FIELDS = {"top_skills", "job_types_target", "job_types_avoid"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_profiles_dir(jobs_dir: Optional[Path] = None) -> Path:
    base = jobs_dir or (Path.home() / ".levi" / "jobs")
    return base / "profiles"


@dataclass
class Profile:
    """One human's job-search profile. Engine code must never construct
    this with literal personal data — it is loaded from the store."""

    name: str
    fields: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "fields": self.fields,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProfileStore:
    """CRUD over per-person profile JSON files. Deny-closed schema."""

    def __init__(self, jobs_dir: Optional[Path] = None) -> None:
        self.dir = default_profiles_dir(jobs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)

    def _path(self, name: str) -> Path:
        safe = "".join(
            c for c in name.strip().lower() if c.isalnum() or c in ("-", "_")
        )
        if not safe:
            raise ValueError("profile name must contain at least one alnum character")
        return self.dir / f"{safe}.json"

    def create(self, name: str) -> Profile:
        path = self._path(name)
        if path.exists():
            raise ValueError(f"profile {name!r} already exists")
        profile = Profile(
            name=name.strip(),
            fields={},
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        self._write(path, profile)
        return profile

    def get(self, name: str) -> Profile:
        path = self._path(name)
        if not path.exists():
            raise KeyError(f"no such profile: {name!r}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile(
            name=data.get("name", name),
            fields=data.get("fields", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def list(self) -> List[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def set_field(self, name: str, key: str, value: Any) -> Profile:
        """Set one schema field. Unknown keys raise — never silently stored."""
        if key not in PROFILE_FIELDS:
            raise ValueError(
                f"unknown profile field {key!r}; allowed: {', '.join(PROFILE_FIELDS)}"
            )
        if key in _LIST_FIELDS and isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        profile = self.get(name)
        profile.fields[key] = value
        profile.updated_at = _utcnow()
        self._write(self._path(name), profile)
        return profile

    def scaffold(self, name: str) -> Profile:
        """Create an empty, fully-schematized profile (all fields blank)."""
        profile = self.create(name)
        profile.fields = {k: ([] if k in _LIST_FIELDS else "") for k in PROFILE_FIELDS}
        profile.updated_at = _utcnow()
        self._write(self._path(name), profile)
        return profile

    def _write(self, path: Path, profile: Profile) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(profile.to_dict(), fh, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
