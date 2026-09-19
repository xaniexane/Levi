"""Sidewinder course schema — stdlib only.

Every course entry is one JSON object per line (JSONL). Required keys::

    {
      "id": "sw-plumbing-001",          # ^sw-[a-z0-9-]+-\\d{3}$, echoes domain
      "title": "Remove a bathtub spout without a strap wrench",
      "domain": "plumbing",             # one of sidewinder.DOMAINS
      "tracks": ["restore", "improvise"],  # >=1 of sidewinder.TRACKS
      "level": "applied",               # foundation | applied | mastery
      "prerequisites": ["sw-foundations-007"],  # entry-id links (may be [])
      "difficulty": 2,                 # 1 = basic, 2 = care needed, 3 = stop-critical
      "mechanism_check": ["...", ...], # SEE THE MECHANISM (str or list of str)
      "improvised_tools": ["...", ...],# SUBSTITUTE FROM ON-HAND
      "steps": ["...", ...],           # ordered actions
      "stop_conditions": ["...", ...], # KNOW THE STOP
    }

Optional keys: "origin" (true for the originating case), "notes", "version".
"stub": true marks an unfilled writer stub — stubs never promote to the
corpus and are rejected by validation for promotion.

Crisis-domain law (non-negotiable): every crisis entry's FIRST stop
condition must call for professional help first, and at least one stop
condition must state an explicit "do not attempt if..." boundary.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from levi.sidewinder import DOMAINS, LEVELS, TRACKS

REQUIRED_KEYS = (
    "id",
    "title",
    "domain",
    "tracks",
    "level",
    "prerequisites",
    "difficulty",
    "mechanism_check",
    "improvised_tools",
    "steps",
    "stop_conditions",
)

OPTIONAL_KEYS = ("origin", "notes", "version")

_ID_RE = re.compile(r"\Asw-[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}\Z")

_DIFFICULTY_RANGE = (1, 2, 3)


def _as_list(value: Any) -> List[str]:
    """Accept a string or a list of strings; normalize to a stripped list."""
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        return []
    out = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with list-ish fields normalized to lists of strings."""
    norm = dict(entry)
    for key in ("tracks", "prerequisites", "mechanism_check", "improvised_tools", "steps", "stop_conditions"):
        if key in norm:
            norm[key] = _as_list(norm[key])
    return norm


def validate_entry(entry: Any) -> List[str]:
    """Return a list of schema violations; empty means the entry is valid.

    Stubs (``"stub": true``) are never valid for promotion — they are writer
    scaffolding, not corpus entries.
    """
    errors: List[str] = []
    if not isinstance(entry, dict):
        return ["entry is not a JSON object"]
    if entry.get("stub") is True:
        return ["entry is a stub (unfilled writer scaffolding)"]
    for key in REQUIRED_KEYS:
        if key not in entry:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors
    if not isinstance(entry["id"], str) or not _ID_RE.match(entry["id"]):
        errors.append(f"bad id (want sw-<domain-slug>-NNN): {entry.get('id')!r}")
    if not isinstance(entry["title"], str) or not entry["title"].strip():
        errors.append("title must be a non-empty string")
    if entry["domain"] not in DOMAINS:
        errors.append(f"bad domain {entry.get('domain')!r} (want one of {', '.join(DOMAINS)})")
    tracks = _as_list(entry["tracks"])
    if not tracks:
        errors.append("tracks must hold at least one track")
    else:
        bad = [t for t in tracks if t not in TRACKS]
        if bad:
            errors.append(f"bad track(s) {bad} (want from {', '.join(TRACKS)})")
    if entry["level"] not in LEVELS:
        errors.append(f"bad level {entry.get('level')!r} (want one of {', '.join(LEVELS)})")
    prereqs = entry["prerequisites"]
    if not isinstance(prereqs, (list, tuple)) or any(
        not isinstance(p, str) or not _ID_RE.match(p) for p in prereqs
    ):
        errors.append("prerequisites must be a list of entry ids (may be empty)")
    if entry["difficulty"] not in _DIFFICULTY_RANGE:
        errors.append(f"bad difficulty {entry.get('difficulty')!r} (want 1, 2, or 3)")
    for key in ("mechanism_check", "improvised_tools", "steps", "stop_conditions"):
        items = _as_list(entry[key])
        if not items:
            errors.append(f"{key} must hold at least one non-empty string")
        elif any(len(item) > 400 for item in items):
            errors.append(f"{key} has an over-long item (keep entries terse, <= 400 chars)")
    # Id slug should echo the domain so shards stay sortable.
    entry_id = str(entry["id"])
    domain_slug = str(entry["domain"]).replace("_", "-")
    if entry_id.startswith("sw-") and not entry_id.startswith(f"sw-{domain_slug}-"):
        errors.append(f"id {entry_id!r} does not start with sw-{domain_slug}-")
    # Crisis-domain law: help first, always; explicit do-not-attempt boundary.
    if entry["domain"] == "crisis" and not errors:
        stops = _as_list(entry["stop_conditions"])
        if not stops or "professional help" not in stops[0].lower():
            errors.append("crisis entry: first stop condition must call for professional help first")
        if not any("do not attempt" in s.lower() for s in stops):
            errors.append("crisis entry: need an explicit 'do not attempt if...' stop condition")
    return errors


def is_valid(entry: Any) -> bool:
    return not validate_entry(entry)


def check_batch(entries: List[Any]) -> Tuple[List[Dict[str, Any]], List[Tuple[Any, List[str]]]]:
    """Split a batch into (valid normalized entries, [(entry, errors)])."""
    valid: List[Dict[str, Any]] = []
    invalid: List[Tuple[Any, List[str]]] = []
    for entry in entries:
        errors = validate_entry(entry)
        if errors:
            invalid.append((entry, errors))
        else:
            valid.append(normalize_entry(entry))
    return valid, invalid
