"""The Chooser — accountless local service directory (AppleTalk NBP, revived).

AppleTalk's Name Binding Protocol let a service register a human name in
the form ``object:type@zone`` ("Moe's printer:printer@Bldg. 1"), with the
local names table conflict-checked and the name broadcast to the zone.
The Chooser then showed every user a browsable list of named services by
type and zone — no server, no account, no configuration.

This is that, for LEVI nodes on a trusted local directory:

- ``register(name, kind, zone, node, address)`` — claim a name. Same
  name+kind+zone claimed by a *different* node is a conflict: refused,
  never overwritten (the NBP rule). Re-registering your own name updates
  the entry.
- ``lookup(name, kind, zone)`` — resolve one name.
- ``browse(kind=None, zone=None)`` — list what is here, the Chooser view.
- ``unregister(...)`` — release a name you own.

Names are case-insensitive for conflict purposes (AppleTalk was too).
Persistence is plain JSON, owner-only. This directory is local and
human-scale by design: it replaces accounts with visibility.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import HOME_DIRNAME

_VALID = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ .'")


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _names_path(home: Optional[Path] = None) -> Path:
    p = (home or _home()) / HOME_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    path = p / "names.json"
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
        os.chmod(path, 0o600)
    return path


def _load(home: Optional[Path]) -> List[Dict[str, Any]]:
    path = _names_path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = []
    return data if isinstance(data, list) else []


def _save(home: Optional[Path], data: List[Dict[str, Any]]) -> None:
    path = _names_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _check(field: str, value: str) -> str:
    value = value.strip()
    if not value or len(value) > 64:
        raise ValueError("%s required, max 64 chars" % field)
    if any(c not in _VALID for c in value):
        raise ValueError("%s has illegal characters: %r" % (field, value))
    return value


def _key(name: str, kind: str, zone: str) -> str:
    return "%s\x00%s\x00%s" % (name.lower(), kind.lower(), zone.lower())


def register(
    name: str,
    kind: str,
    zone: str,
    node: str,
    address: str = "",
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Register ``name:kind@zone`` for a node. Raises ValueError on conflict."""
    name = _check("name", name)
    kind = _check("kind", kind)
    zone = _check("zone", zone)
    node = _check("node", node)
    key = _key(name, kind, zone)
    entries = _load(home)
    for e in entries:
        if _key(e["name"], e["kind"], e["zone"]) == key:
            if e["node"] != node:
                raise ValueError(
                    "name conflict: %s:%s@%s is already registered by node "
                    "%r — refusing to overwrite" % (name, kind, zone, e["node"])
                )
            e.update({"address": address.strip(), "registered_ts": int(time.time())})
            _save(home, entries)
            return e
    entry = {
        "name": name,
        "kind": kind,
        "zone": zone,
        "node": node,
        "address": address.strip(),
        "registered_ts": int(time.time()),
    }
    entries.append(entry)
    _save(home, entries)
    return entry


def lookup(
    name: str, kind: str = "", zone: str = "", home: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Resolve one registered name. Empty kind/zone act as wildcards."""
    name = name.strip().lower()
    entries = _load(home)
    for e in entries:
        if e["name"].lower() != name:
            continue
        if kind and e["kind"].lower() != kind.strip().lower():
            continue
        if zone and e["zone"].lower() != zone.strip().lower():
            continue
        return e
    return None


def browse(
    kind: str = "", zone: str = "", home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The Chooser view: all registrations, optionally filtered."""
    entries = _load(home)
    out = []
    for e in entries:
        if kind and e["kind"].lower() != kind.strip().lower():
            continue
        if zone and e["zone"].lower() != zone.strip().lower():
            continue
        out.append(e)
    out.sort(key=lambda e: (e["zone"].lower(), e["kind"].lower(), e["name"].lower()))
    return out


def unregister(
    name: str, kind: str, zone: str, node: str, home: Optional[Path] = None
) -> bool:
    """Release a name registered by your own node. True if removed."""
    key = _key(_check("name", name), _check("kind", kind), _check("zone", zone))
    node = _check("node", node)
    entries = _load(home)
    kept = [
        e
        for e in entries
        if not (_key(e["name"], e["kind"], e["zone"]) == key and e["node"] == node)
    ]
    if len(kept) == len(entries):
        return False
    _save(home, kept)
    return True
