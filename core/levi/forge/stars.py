"""Stars — portable favorites. GitHub keeps stars hostage on its servers;
Forge keeps them in a plain JSON file that rides along in every export,
so reputation travels with the repo."""

from __future__ import annotations

from datetime import datetime, timezone

from .home import forge_home, validate_name
from .jsonl import read_json, write_json


def _stars_path(home) -> "object":
    return forge_home(home) / "stars.json"


def star(home, name) -> dict:
    name = validate_name(name)
    stars = read_json(_stars_path(home), {})
    stars[name] = {
        "starred": True,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(_stars_path(home), stars)
    return stars[name]


def unstar(home, name) -> bool:
    name = validate_name(name)
    stars = read_json(_stars_path(home), {})
    if name in stars:
        del stars[name]
        write_json(_stars_path(home), stars)
        return True
    return False


def is_starred(home, name) -> bool:
    return validate_name(name) in read_json(_stars_path(home), {})


def starred(home):
    """Return {name: record} of starred repos."""
    return read_json(_stars_path(home), {})
