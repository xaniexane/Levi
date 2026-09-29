"""LEVI customizations — command shortcuts: his abbreviations, kept verbatim.

Chauncey drives everything from terse commands; shortcuts let him name
the ones he types most. A shortcut maps a short name to a command-line
expansion — ``status`` → ``daemon heartbeat --force`` — and ``expand()``
rewrites a typed line before anything runs.

Expansion only, never execution: this module rewrites text. Whatever
runs the expanded line owns the consequences; the shortcut store never
executes anything itself.

Retirement honors the nothing-thrown-away law: removing a shortcut moves
it — with its expansion, timestamp, and reason — into the ``retired``
ledger. Nothing is ever deleted.

Storage is local-first: ``~/.levi/customizations/shortcuts.json``,
owner-only (0o600), written atomically. Everything is deny-closed:
bad names, shell metacharacters in expansions (``;|&$()`` backticks,
``><``, newlines — an expansion must be one plain command line),
duplicates, expansion cycles, and removing what isn't there are all
refused with a named error, never coerced.

Usage::

    from levi.customizations import shortcuts

    shortcuts.add_shortcut("hb", "daemon heartbeat --force")
    shortcuts.expand("hb --json")
    # -> "daemon heartbeat --force --json"

Run it: ``python -m levi.customizations.shortcuts list``
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "ShortcutError",
    "DEFAULT_ROOT",
    "NAME_RE",
    "MAX_EXPANSION_CHARS",
    "MAX_CHAIN_DEPTH",
    "add_shortcut",
    "remove_shortcut",
    "restore_shortcut",
    "get_shortcut",
    "list_shortcuts",
    "find",
    "expand",
]


class ShortcutError(ValueError):
    """Raised when a shortcut fails validation or the store misbehaves."""


#: Shortcut names: lowercase, short, token-friendly.
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")

#: One plain command line — no shell metacharacters, ever.
_FORBIDDEN = set(";&|$()><`\n")

#: An expansion may itself name another shortcut; chains deeper than
#: this are refused rather than followed forever.
MAX_CHAIN_DEPTH = 8

MAX_EXPANSION_CHARS = 500

#: Where the store lives unless a caller says otherwise.
DEFAULT_ROOT = Path.home() / ".levi" / "customizations"

_STORE_FILE = "shortcuts.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(root: Path) -> Path:
    return Path(root) / _STORE_FILE


def _load(root: Path) -> Dict[str, List[Dict[str, str]]]:
    path = _store_path(Path(root))
    if not path.exists():
        return {"shortcuts": [], "retired": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ShortcutError(f"shortcuts: store unreadable: {exc}") from exc
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("shortcuts"), list)
        or not isinstance(data.get("retired"), list)
    ):
        raise ShortcutError("shortcuts: store malformed — refused, never defaulted")
    return data


def _save(root: Path, data: Dict[str, List[Dict[str, str]]]) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    tmp = _store_path(root).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(_store_path(root))


def _check_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ShortcutError("shortcuts: name must match ^[a-z][a-z0-9_-]{0,39}$")
    return name


def _check_expansion(expansion: str) -> str:
    if not isinstance(expansion, str) or not expansion.strip():
        raise ShortcutError("shortcuts: expansion must be a non-empty str")
    if len(expansion) > MAX_EXPANSION_CHARS:
        raise ShortcutError(f"shortcuts: expansion exceeds {MAX_EXPANSION_CHARS} chars")
    bad = sorted(set(expansion) & _FORBIDDEN)
    if bad:
        raise ShortcutError(
            "shortcuts: expansion must be one plain command line; "
            f"refused characters: {' '.join(bad)}"
        )
    return expansion.strip()


def _by_name(
    data: Dict[str, List[Dict[str, str]]], name: str
) -> Optional[Dict[str, str]]:
    for entry in data["shortcuts"]:
        if entry["name"] == name:
            return entry
    return None


def add_shortcut(
    name: str, expansion: str, root: Optional[Path] = None
) -> Dict[str, str]:
    """Register a shortcut. Duplicates are refused — remove, then re-add."""
    name = _check_name(name)
    expansion = _check_expansion(expansion)
    root = Path(root) if root is not None else DEFAULT_ROOT
    data = _load(root)
    if _by_name(data, name) is not None:
        raise ShortcutError(f"shortcuts: '{name}' already exists")
    record = {"name": name, "expansion": expansion, "added_at": _utcnow_iso()}
    data["shortcuts"].append(record)
    data["shortcuts"].sort(key=lambda e: e["name"])
    _save(root, data)
    return record


def remove_shortcut(
    name: str, reason: str = "", root: Optional[Path] = None
) -> Dict[str, str]:
    """Retire a shortcut to the ledger — moved, never deleted."""
    name = _check_name(name)
    root = Path(root) if root is not None else DEFAULT_ROOT
    data = _load(root)
    record = _by_name(data, name)
    if record is None:
        raise ShortcutError(f"shortcuts: no shortcut named '{name}'")
    data["shortcuts"] = [e for e in data["shortcuts"] if e["name"] != name]
    retired = dict(record)
    retired["removed_at"] = _utcnow_iso()
    retired["reason"] = reason
    data["retired"].append(retired)
    _save(root, data)
    return retired


def restore_shortcut(name: str, root: Optional[Path] = None) -> Dict[str, str]:
    """Bring a retired shortcut back."""
    name = _check_name(name)
    root = Path(root) if root is not None else DEFAULT_ROOT
    data = _load(root)
    if _by_name(data, name) is not None:
        raise ShortcutError(f"shortcuts: '{name}' is already active")
    for i, entry in enumerate(data["retired"]):
        if entry["name"] == name:
            record = {
                "name": name,
                "expansion": entry["expansion"],
                "added_at": _utcnow_iso(),
            }
            del data["retired"][i]
            data["shortcuts"].append(record)
            data["shortcuts"].sort(key=lambda e: e["name"])
            _save(root, data)
            return record
    raise ShortcutError(f"shortcuts: no retired shortcut named '{name}'")


def get_shortcut(name: str, root: Optional[Path] = None) -> Dict[str, str]:
    name = _check_name(name)
    root = Path(root) if root is not None else DEFAULT_ROOT
    record = _by_name(_load(root), name)
    if record is None:
        raise ShortcutError(f"shortcuts: no shortcut named '{name}'")
    return record


def list_shortcuts(root: Optional[Path] = None) -> List[Dict[str, str]]:
    root = Path(root) if root is not None else DEFAULT_ROOT
    return list(_load(root)["shortcuts"])


def find(prefix: str, root: Optional[Path] = None) -> List[Dict[str, str]]:
    """Case-insensitive prefix search over names and expansions."""
    if not isinstance(prefix, str) or not prefix:
        raise ShortcutError("shortcuts: find needs a non-empty prefix")
    needle = prefix.casefold()
    return [
        s
        for s in list_shortcuts(root)
        if s["name"].casefold().startswith(needle)
        or needle in s["expansion"].casefold()
    ]


def expand(line: str, root: Optional[Path] = None) -> str:
    """Rewrite a leading shortcut token; anything else passes through.

    Chains (an expansion naming another shortcut) are followed up to
    ``MAX_CHAIN_DEPTH``; a cycle is refused with a named error.
    """
    if not isinstance(line, str) or not line.strip():
        raise ShortcutError("shortcuts: expand needs a non-empty line")
    root = Path(root) if root is not None else DEFAULT_ROOT
    table = {s["name"]: s["expansion"] for s in list_shortcuts(root)}
    seen: List[str] = []
    current = line.strip()
    for _depth in range(MAX_CHAIN_DEPTH):
        head, _, rest = current.partition(" ")
        head = head.strip()
        if head not in table:
            return current
        if head in seen:
            raise ShortcutError(
                "shortcuts: expansion cycle: " + " -> ".join(seen + [head])
            )
        seen.append(head)
        expansion = table[head]
        current = expansion + (" " + rest.strip() if rest.strip() else "")
    # One more step would exceed the chain budget — check honestly.
    head = current.partition(" ")[0].strip()
    if head in table:
        raise ShortcutError(
            f"shortcuts: expansion chain deeper than {MAX_CHAIN_DEPTH} — refused"
        )
    return current


def _cli(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m levi.customizations.shortcuts")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List active shortcuts.")
    p_add = sub.add_parser("add", help="Add a shortcut.")
    p_add.add_argument("name")
    p_add.add_argument("expansion")
    p_remove = sub.add_parser("remove", help="Retire a shortcut.")
    p_remove.add_argument("name")
    p_remove.add_argument("--reason", default="")
    p_restore = sub.add_parser("restore", help="Restore a retired shortcut.")
    p_restore.add_argument("name")
    p_get = sub.add_parser("get", help="Show one shortcut.")
    p_get.add_argument("name")
    p_find = sub.add_parser("find", help="Search shortcuts.")
    p_find.add_argument("prefix")
    p_expand = sub.add_parser("expand", help="Expand a command line.")
    p_expand.add_argument("line")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "list":
            for s in list_shortcuts():
                print(f"{s['name']}\t{s['expansion']}")
        elif args.cmd == "add":
            rec = add_shortcut(args.name, args.expansion)
            print(f"added {rec['name']} -> {rec['expansion']}")
        elif args.cmd == "remove":
            rec = remove_shortcut(args.name, reason=args.reason)
            print(f"retired {rec['name']}")
        elif args.cmd == "restore":
            rec = restore_shortcut(args.name)
            print(f"restored {rec['name']} -> {rec['expansion']}")
        elif args.cmd == "get":
            rec = get_shortcut(args.name)
            print(f"{rec['name']}\t{rec['expansion']}")
        elif args.cmd == "find":
            for s in find(args.prefix):
                print(f"{s['name']}\t{s['expansion']}")
        elif args.cmd == "expand":
            print(expand(args.line))
    except ShortcutError as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
