"""The hive index — distributed retention for the legion's learnings.

One write path, two views:
  * per-seat namespaced journals are the source of truth (provenance);
  * the hive index is a DERIVED, append-only, id-keyed registry that
    any seat can query.

They must never disagree: ``verify_consistency()`` checks every
journaled record and every growth-tagged memory entry has an index
entry, and every index entry traces back to a journal record or an
explicit registration carrying provenance.

The index lives at ``<growth_dir>/hive/index.jsonl`` (growth_dir
honors LEVI_GROWTH_DIR, so tests never touch the real hive).

Record shape:
  {"id", "kind", "ts", "seat", "track", "content", "tags",
   "provenance", "supersedes"}

kinds: "learned" (a consolidated learning), "raise" (a raising-cycle
journal record), "composted" (a REIM lesson), "genome-delta" (a RIEM
delta), "memory" (any other registered memory), "supplied" (pickup
protocol: this seat was given this memory), "miss" (honest miss,
journaled), "recovered-via-hive" (seat-side recovery note).

"The stone never forgets": append-only. No deletes, no edits —
supersede by a new entry whose "supersedes" names the old id.
Idempotent: registering an id that is already indexed is a no-op
(the first write wins; the stone's first telling stands).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from levi.founders import roster
from levi.growth import guards as _guards
from levi.growth import journal as _journal

try:
    from levi.growth.redact import redact_text
except Exception:  # pragma: no cover

    def redact_text(text):  # type: ignore
        return text or ""


KINDS = (
    "learned",
    "raise",
    "composted",
    "genome-delta",
    "memory",
    "supplied",
    "miss",
    "recovered-via-hive",
)

_WORD = __import__("re").compile(r"[a-z0-9]{3,}")


def hive_dir() -> Path:
    p = _journal.growth_dir() / "hive"
    p.mkdir(parents=True, exist_ok=True)
    return p


def index_path() -> Path:
    return hive_dir() / "index.jsonl"


def _now() -> str:
    return _journal.now_iso()


def _validate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(
            "hive register: record must be a dict, got %s" % type(record).__name__
        )
    rec = dict(record)
    rid = rec.get("id")
    if not isinstance(rid, str) or not rid.strip():
        raise ValueError("hive register: record needs a non-empty string id")
    kind = rec.get("kind")
    if kind not in KINDS:
        raise ValueError(
            "hive register: kind must be one of %r, got %r" % (KINDS, kind)
        )
    seat = rec.get("seat", "hive")
    if seat != "hive":
        roster.get_seat(seat)  # deny-open: provenance names real seats only
    content = rec.get("content", "")
    if not isinstance(content, str):
        raise ValueError("hive register: content must be a string")
    # Guards, absolute: secret-scrubbed, no sentience claims, ever.
    rec["content"] = redact_text(content)[:4000]
    _guards.assert_no_sentience_claim(rec["content"])
    rec.setdefault("ts", _now())
    rec.setdefault("track", "")
    tags = rec.get("tags") or []
    if not isinstance(tags, (list, tuple)):
        raise ValueError("hive register: tags must be a list")
    rec["tags"] = ["hive"] + [t for t in tags if isinstance(t, str) and t != "hive"]
    prov = rec.get("provenance") or {}
    if not isinstance(prov, dict):
        raise ValueError("hive register: provenance must be a dict")
    rec["provenance"] = prov
    rec["supersedes"] = rec.get("supersedes") or ""
    return rec


def known_ids() -> Set[str]:
    """Ids already in the index (idempotency set)."""
    ids: Set[str] = set()
    try:
        lines = index_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return ids
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            ids.add(str(rec["id"]))
    return ids


def register_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Register one record in the hive index. Idempotent on id.

    Returns {"registered": bool, "id": ...}. Raises ValueError on a bad
    record or a guard violation — the hive never stores a refusal
    silently: the caller gets the error and the failure stays visible.
    """
    rec = _validate_record(record)
    ids = known_ids()
    if rec["id"] in ids:
        return {"registered": False, "id": rec["id"], "reason": "already indexed"}
    with open(index_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"registered": True, "id": rec["id"]}


def read_index(limit: int = 200000) -> List[Dict[str, Any]]:
    """All index records, oldest-first (tolerates corrupt lines)."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("read_index: limit must be a positive int")
    try:
        lines = index_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[:limit]


def query_index(
    query: str = "",
    *,
    kind: Optional[str] = None,
    seat: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Mechanical keyword search over the index (rules, no model).

    Scores by content-word overlap with the query; exact id match
    always ranks first. Returns records newest-first among matches.
    """
    recs = read_index()
    q = (query or "").strip()
    qwords = set(_WORD.findall(q.lower()))
    scored = []
    for rec in recs:
        if kind is not None and rec.get("kind") != kind:
            continue
        if seat is not None and rec.get("seat") != seat:
            continue
        if not q:
            scored.append((0, rec))
            continue
        if q == rec.get("id"):
            scored.append((10**9, rec))
            continue
        cwords = set(_WORD.findall(str(rec.get("content", "")).lower()))
        overlap = len(qwords & cwords)
        if overlap:
            scored.append((overlap, rec))
    scored.sort(key=lambda t: (t[0], str(t[1].get("ts", ""))), reverse=True)
    return [rec for _, rec in scored[:limit]]


# ---------------------------------------------------------------------------
# Derivation: journals + memory store -> index
# ---------------------------------------------------------------------------


def _seat_journal_files() -> List[Path]:
    base = _journal.growth_dir()
    files: List[Path] = []
    for sub in ("founders", "agents"):
        root = base / sub
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("journal.jsonl")):
            # skip the legion-wide journal (that's Levi's baby book, a
            # different view) — per-seat journals only
            if p == base / "journal.jsonl":
                continue
            files.append(p)
    return files


def _seat_of_journal(path: Path) -> str:
    # .../founders/<key>/journal.jsonl or .../agents/<wave>/<key>/journal.jsonl
    return path.parent.name


def sync_from_journals() -> Dict[str, Any]:
    """Index every per-seat journal record (idempotent).

    The journal record itself is registered (kind "raise"/its own
    kind) — the raising cycle's own account of what it did is a memory
    worth retaining hive-wide, with the seat as provenance.
    """
    registered = 0
    skipped = 0
    for path in _seat_journal_files():
        seat = _seat_of_journal(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if not isinstance(rec, dict) or not rec.get("id"):
                skipped += 1
                continue
            out = register_record(
                {
                    "id": "journal:%s:%s" % (seat, rec["id"]),
                    "kind": rec.get("kind", "raise"),
                    "ts": rec.get("ts", _now()),
                    "seat": seat,
                    "track": rec.get("track", ""),
                    "content": "Raising record %s (%s): %d experiences, %d "
                    "learnings proposed, %d accepted, mode=%s, quiet=%s."
                    % (
                        rec.get("id"),
                        rec.get("kind", "raise"),
                        rec.get("experiences", 0),
                        rec.get("learnings_proposed", 0),
                        rec.get("accepted", 0),
                        rec.get("mode", "?"),
                        rec.get("quiet", False),
                    ),
                    "tags": ["journal-record"],
                    "provenance": {"journal": str(path), "record": rec.get("id")},
                }
            )
            if out["registered"]:
                registered += 1
    return {"registered": registered, "skipped": skipped}


def sync_from_store(store: Any = None) -> Dict[str, Any]:
    """Index every growth-tagged memory entry (idempotent).

    The per-seat namespace tag is preserved — the index records which
    seat learned it and when. Levi's own (un-namespaced) learnings
    index under seat "levi" only when they carry no seat tag... no:
    honestly, they index under seat "hive" with provenance noting the
    legacy cycle. The seat's own tag is the authority; where none
    exists we say so instead of guessing.
    """
    if store is None:
        try:
            from levi.memory.store import MemoryStore

            store = MemoryStore()
        except Exception:
            return {"registered": 0, "skipped": 0, "error": "no memory store"}
    registered = 0
    for e in store.list(limit=5000):
        tags = set(getattr(e, "tags", []) or [])
        if "growth" not in tags:
            continue
        seat_tags = [t for t in tags if t.startswith("seat:")]
        seat = seat_tags[0][5:] if len(seat_tags) == 1 else "hive"
        md = getattr(e, "metadata", None) or {}
        prov = dict(md.get("provenance", {}) or {})
        prov.setdefault("memory_id", getattr(e, "id", "?"))
        if len(seat_tags) != 1:
            prov["seat_note"] = "no single seat tag; indexed as legion-common"
        out = register_record(
            {
                "id": "memory:%s" % getattr(e, "id", "?"),
                "kind": "learned",
                "ts": str(getattr(e, "created_at", "") or _now()),
                "seat": seat,
                "track": prov.get("track", ""),
                "content": str(getattr(e, "content", "") or ""),
                "tags": sorted(tags),
                "provenance": prov,
            }
        )
        if out["registered"]:
            registered += 1
    return {"registered": registered, "skipped": 0}


# ---------------------------------------------------------------------------
# REIM / RIEM integration — through their public APIs only
# ---------------------------------------------------------------------------


def register_compost(
    lessons: List[Dict[str, Any]], *, seat: str = "hive"
) -> Dict[str, Any]:
    """Register REIM-composted lessons (data from REIM.compost()).

    The caller runs the public REIM API and hands the lessons here;
    the hive only registers — it never composts, never edits.
    """
    if not isinstance(lessons, list):
        raise ValueError("register_compost: lessons must be a list")
    registered = 0
    for i, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            continue
        lid = str(lesson.get("id") or "compost-%d" % i)
        out = register_record(
            {
                "id": "compost:%s" % lid,
                "kind": "composted",
                "seat": seat,
                "content": "Composted lesson: %s"
                % json.dumps(lesson, ensure_ascii=False)[:2000],
                "tags": ["reim", "compost"],
                "provenance": {"reim_lesson_id": lid, "seat": seat},
            }
        )
        if out["registered"]:
            registered += 1
    return {"registered": registered, "lessons": len(lessons)}


def register_genome_deltas(
    deltas: List[Dict[str, Any]], *, seat: str = "hive"
) -> Dict[str, Any]:
    """Register RIEM genome deltas (data from RIEM.compress()).

    Same contract as register_compost: the caller compresses via the
    public RIEM API; the hive only registers.
    """
    if not isinstance(deltas, list):
        raise ValueError("register_genome_deltas: deltas must be a list")
    registered = 0
    for i, delta in enumerate(deltas):
        if not isinstance(delta, dict):
            continue
        did = str(delta.get("id") or "delta-%d" % i)
        out = register_record(
            {
                "id": "genome:%s" % did,
                "kind": "genome-delta",
                "seat": seat,
                "content": "Genome delta: %s"
                % json.dumps(delta, ensure_ascii=False)[:2000],
                "tags": ["riem", "genome"],
                "provenance": {"riem_delta_id": did, "seat": seat},
            }
        )
        if out["registered"]:
            registered += 1
    return {"registered": registered, "deltas": len(deltas)}


# ---------------------------------------------------------------------------
# Consistency: the index is derived — it must never disagree
# ---------------------------------------------------------------------------


def verify_consistency(store: Any = None) -> Dict[str, Any]:
    """Check index vs sources agree. Returns {"ok", "problems"}.

    Problems (any one fails the check):
      * a per-seat journal record with no index entry;
      * a growth-tagged memory entry with no index entry;
      * an index entry whose provenance names a journal record that no
        longer exists (the stone is append-only — this should never
        happen; if it does, something edited history and we say so).
    """
    problems: List[str] = []
    ids = known_ids()
    # journals -> index
    for path in _seat_journal_files():
        seat = _seat_of_journal(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("id"):
                want = "journal:%s:%s" % (seat, rec["id"])
                if want not in ids:
                    problems.append("journal record %s not indexed" % want)
    # memory -> index
    if store is None:
        try:
            from levi.memory.store import MemoryStore

            store = MemoryStore()
        except Exception:
            store = None
    if store is not None:
        for e in store.list(limit=5000):
            tags = set(getattr(e, "tags", []) or [])
            if "growth" not in tags:
                continue
            want = "memory:%s" % getattr(e, "id", "?")
            if want not in ids:
                problems.append("memory entry %s not indexed" % want)
    # index -> journals (reverse: provenance must resolve)
    journal_ids: Set[str] = set()
    for path in _seat_journal_files():
        seat = _seat_of_journal(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("id"):
                journal_ids.add("journal:%s:%s" % (seat, rec["id"]))
    for rec in read_index():
        if (
            str(rec.get("id", "")).startswith("journal:")
            and rec["id"] not in journal_ids
        ):
            problems.append(
                "index entry %s has no journal record — history was edited" % rec["id"]
            )
    return {"ok": not problems, "problems": problems}
