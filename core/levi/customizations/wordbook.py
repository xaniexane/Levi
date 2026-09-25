"""LEVI customizations — the wordbook: his words, kept verbatim.

Chauncey's words are the spec — the wordbook is where his phrasing
lives so the machine speaks his way. A term maps to his preferred
phrasing plus an optional note; lookups are case-insensitive so
"Plumb Line" and "plumb line" never become silent duplicates.

Retirement honors the nothing-thrown-away law: retiring a term moves it
— with its phrasing, note, timestamp, and reason — into the ``retired``
ledger. Nothing is ever deleted; the history of his words stays whole.

Storage is local-first: ``~/.levi/customizations/wordbook.json``.
Everything is deny-closed: empty terms, over-long phrasing, duplicates,
and retiring what isn't there are refused with a named error.

Usage::

    from levi.customizations import wordbook

    wordbook.add_term("the plumb line", "hang the law, read the evidence",
                      note="verification pattern, not decoration")
    wordbook.get("THE PLUMB LINE")["phrasing"]
    wordbook.retire("the plumb line", reason="renamed by his word")

Run it: ``python -m levi.customizations.wordbook list``
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "WordbookError",
    "DEFAULT_ROOT",
    "add_term",
    "get",
    "retire",
    "restore",
    "list_terms",
    "find",
]


class WordbookError(ValueError):
    """Raised when a wordbook operation fails validation or the store."""


#: Where the wordbook lives unless a caller says otherwise.
DEFAULT_ROOT = Path.home() / ".levi" / "customizations"

_WORDBOOK_FILE = "wordbook.json"
_MAX_TERM_LEN = 64
_MAX_PHRASING_LEN = 500
_MAX_NOTE_LEN = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_term(term: object) -> str:
    if not isinstance(term, str) or not term.strip():
        raise WordbookError(f"term must be a non-empty string, got {term!r}")
    cleaned = " ".join(term.split())
    if len(cleaned) > _MAX_TERM_LEN:
        raise WordbookError(f"term exceeds {_MAX_TERM_LEN} chars: {cleaned[:40]!r}...")
    return cleaned


def _clean_text(value: object, field: str, max_len: int, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise WordbookError(f"{field} must be a string, got {type(value).__name__}")
    cleaned = " ".join(value.split())
    if not allow_empty and not cleaned:
        raise WordbookError(f"{field} must be non-empty")
    if len(cleaned) > max_len:
        raise WordbookError(f"{field} exceeds {max_len} chars")
    return cleaned


def _root(path: Optional[Path]) -> Path:
    root = Path(path) if path is not None else DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _store_path(root: Optional[Path]) -> Path:
    return _root(root) / _WORDBOOK_FILE


def _blank() -> Dict:
    return {"terms": {}, "retired": []}


def _load(root: Optional[Path]) -> Dict:
    target = _store_path(root)
    if not target.exists():
        return _blank()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WordbookError(f"wordbook is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WordbookError("wordbook must be a JSON object")
    terms = data.get("terms", {})
    retired = data.get("retired", [])
    if not isinstance(terms, dict) or not isinstance(retired, list):
        raise WordbookError("wordbook 'terms' must be an object, 'retired' a list")
    return {"terms": terms, "retired": retired}


def _save(data: Dict, root: Optional[Path]) -> Path:
    target = _store_path(root)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def _key(term: str) -> str:
    """Case-insensitive identity: one term, one key."""
    return term.casefold()


def add_term(
    term: object,
    phrasing: object,
    note: object = "",
    root: Optional[Path] = None,
) -> Dict:
    """Add a term. Duplicates (any case) are refused, never merged."""
    clean = _clean_term(term)
    clean_phrasing = _clean_text(phrasing, "phrasing", _MAX_PHRASING_LEN, False)
    clean_note = _clean_text(note, "note", _MAX_NOTE_LEN, True)
    data = _load(root)
    key = _key(clean)
    if key in data["terms"]:
        raise WordbookError(
            f"term '{clean}' is already worded — retire or restore it instead"
        )
    entry = {
        "term": clean,
        "phrasing": clean_phrasing,
        "note": clean_note,
        "added": _now_iso(),
    }
    data["terms"][key] = entry
    _save(data, root)
    return entry


def get(term: object, root: Optional[Path] = None) -> Optional[Dict]:
    """Look up a term (case-insensitive); None when absent."""
    clean = _clean_term(term)
    return _load(root)["terms"].get(_key(clean))


def retire(term: object, reason: object = "", root: Optional[Path] = None) -> Dict:
    """Retire a term into the ledger with provenance. Nothing is deleted."""
    clean = _clean_term(term)
    clean_reason = _clean_text(reason, "reason", _MAX_NOTE_LEN, True)
    data = _load(root)
    key = _key(clean)
    entry = data["terms"].pop(key, None)
    if entry is None:
        raise WordbookError(f"term '{clean}' is not in the wordbook")
    record = dict(entry)
    record["retired_at"] = _now_iso()
    record["reason"] = clean_reason
    data["retired"].append(record)
    _save(data, root)
    return record


def restore(term: object, root: Optional[Path] = None) -> Dict:
    """Bring the most recently retired matching term back into use."""
    clean = _clean_term(term)
    data = _load(root)
    key = _key(clean)
    if key in data["terms"]:
        raise WordbookError(f"term '{clean}' is already active")
    for idx in range(len(data["retired"]) - 1, -1, -1):
        if _key(data["retired"][idx]["term"]) == key:
            record = data["retired"].pop(idx)
            entry = {
                "term": record["term"],
                "phrasing": record["phrasing"],
                "note": record.get("note", ""),
                "added": record.get("added", _now_iso()),
                "restored": _now_iso(),
            }
            data["terms"][key] = entry
            _save(data, root)
            return entry
    raise WordbookError(f"term '{clean}' has no retired record to restore")


def list_terms(root: Optional[Path] = None) -> List[Dict]:
    """All active terms, sorted by term — deterministic."""
    terms = _load(root)["terms"].values()
    return sorted(terms, key=lambda e: e["term"].casefold())


def find(query: object, root: Optional[Path] = None) -> List[Dict]:
    """Substring search over terms and phrasings, case-insensitive."""
    if not isinstance(query, str) or not query.strip():
        raise WordbookError(f"query must be a non-empty string, got {query!r}")
    needle = query.casefold()
    hits = [
        entry
        for entry in _load(root)["terms"].values()
        if needle in entry["term"].casefold() or needle in entry["phrasing"].casefold()
    ]
    return sorted(hits, key=lambda e: e["term"].casefold())


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "customizations-wordbook",
            provides=(
                "customizations.wordbook.term",
                "customizations.wordbook.retire",
            ),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.customizations.wordbook",
        description="The wordbook: his words, kept verbatim.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add a term with his phrasing")
    add.add_argument("term")
    add.add_argument("phrasing")
    add.add_argument("--note", default="")
    get_p = sub.add_parser("get", help="look up a term")
    get_p.add_argument("term")
    ret = sub.add_parser("retire", help="retire a term (kept in the ledger)")
    ret.add_argument("term")
    ret.add_argument("--reason", default="")
    rst = sub.add_parser("restore", help="restore a retired term")
    rst.add_argument("term")
    sub.add_parser("list", help="list active terms")
    fnd = sub.add_parser("find", help="search terms and phrasings")
    fnd.add_argument("query")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "add":
            entry = add_term(args.term, args.phrasing, note=args.note)
            print(json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "get":
            entry = get(args.term)
            if entry is None:
                print(f"no such term: {args.term}")
                return 1
            print(json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "retire":
            record = retire(args.term, reason=args.reason)
            print(f"retired '{record['term']}' — kept in the ledger")
        elif args.cmd == "restore":
            entry = restore(args.term)
            print(f"restored '{entry['term']}'")
        elif args.cmd == "list":
            for entry in list_terms():
                print(f"{entry['term']} → {entry['phrasing']}")
        elif args.cmd == "find":
            for entry in find(args.query):
                print(f"{entry['term']} → {entry['phrasing']}")
    except WordbookError as exc:
        ap.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
