"""Plaiground companion creator — define a companion persona per owner.

A companion is a persona definition: name, traits, boundaries. Stored as
JSON under the Plaiground directory (owner-only, alongside the gate
record). Content is user-driven at runtime; this module ships no persona
content of its own — only the plumbing to create, read, list, and delete
definitions. Defaults are deliberately neutral.

Every public function calls :func:`levi.plaiground.gate.require_adult`
first: with the gate off, no persona can even be defined.
"""

from __future__ import annotations

import json
import os
import re
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.plaiground.gate import gate_dir, require_adult

_COMPANIONS_SUBDIR = "companions"

_MAX_NAME_LEN = 48
_MAX_TRAIT_LEN = 120
_MAX_BOUNDARY_LEN = 240
_MAX_TRAITS = 24
_MAX_BOUNDARIES = 24

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.'-]{0,47}$")

# Printable-only fields; companion content stays user-driven, but control
# characters and pathological input are rejected as input hygiene.
_ALLOWED_CHARS = set(string.printable) - set("\x0b\x0c")


def _companions_dir(home: Optional[Path] = None) -> Path:
    return gate_dir(home) / _COMPANIONS_SUBDIR


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "companion"


def _validate_text(value: str, label: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise ValueError("%s must be a string, got %s" % (label, type(value).__name__))
    value = value.strip()
    if not value:
        raise ValueError("%s must not be empty" % label)
    if len(value) > max_len:
        raise ValueError("%s must be at most %d characters" % (label, max_len))
    if any(ch not in _ALLOWED_CHARS for ch in value):
        raise ValueError("%s contains disallowed characters" % label)
    return value


def _validate_name(name: str) -> str:
    name = _validate_text(name, "name", _MAX_NAME_LEN)
    if not _NAME_RE.match(name):
        raise ValueError(
            "name must start with a letter/digit and use only letters, "
            "digits, spaces, and _ . ' -"
        )
    return name


def create_companion(
    name: str,
    traits: Optional[List[str]] = None,
    boundaries: Optional[List[str]] = None,
    home: Optional[Path] = None,
) -> Dict:
    """Define (or redefine) a companion persona. Gate-checked first.

    ``traits`` describe how the companion comes across; ``boundaries``
    are the companion's limits, honored by the simulator and chat.
    Defaults are neutral: no traits beyond "steady", and a single
    standing boundary to keep things respectful.
    """
    require_adult(home)
    name = _validate_name(name)
    traits = traits if traits is not None else ["steady"]
    boundaries = boundaries if boundaries is not None else ["keep it respectful"]
    if not isinstance(traits, list) or len(traits) > _MAX_TRAITS:
        raise ValueError("traits must be a list of at most %d strings" % _MAX_TRAITS)
    if not isinstance(boundaries, list) or len(boundaries) > _MAX_BOUNDARIES:
        raise ValueError(
            "boundaries must be a list of at most %d strings" % _MAX_BOUNDARIES
        )
    traits = [_validate_text(t, "trait", _MAX_TRAIT_LEN) for t in traits]
    boundaries = [_validate_text(b, "boundary", _MAX_BOUNDARY_LEN) for b in boundaries]

    record = {
        "name": name,
        "traits": traits,
        "boundaries": boundaries,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "zone": "plaiground",
    }
    d = _companions_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / (_slugify(name) + ".json")
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return record


def get_companion(name: str, home: Optional[Path] = None) -> Dict:
    """Load a companion definition. Gate-checked first."""
    require_adult(home)
    path = _companions_dir(home) / (_slugify(name) + ".json")
    if not path.is_file():
        raise KeyError("no companion named %r" % name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("zone") != "plaiground":
        raise ValueError("companion record for %r is malformed" % name)
    return record


def list_companions(home: Optional[Path] = None) -> List[str]:
    """Names of defined companions. Gate-checked first."""
    require_adult(home)
    d = _companions_dir(home)
    if not d.is_dir():
        return []
    names = []
    for path in sorted(d.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(record, dict) and record.get("zone") == "plaiground":
                names.append(str(record.get("name", path.stem)))
        except (OSError, ValueError):
            continue
    return names


def delete_companion(name: str, home: Optional[Path] = None) -> bool:
    """Remove a companion definition. Gate-checked first."""
    require_adult(home)
    path = _companions_dir(home) / (_slugify(name) + ".json")
    if path.is_file():
        path.unlink()
        return True
    return False
