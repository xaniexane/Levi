"""LEVI SQLite skill library: a real database of skills, not stub registrations.

Chauncey rejected registry stubs outright (2026-09-25: "no stubs"). The live
SkillRegistry holds only the 1,233 real, working skills. This module is the
durable library underneath: every real skill plus every Omega archive entry
as a refinement candidate, queryable at runtime.

Location: ``~/.levi/skills/skills.db`` (same convention as the memory store's
``~/.levi/memory``), overridable with ``LEVI_SKILLDB_PATH``. The DB file is
runtime data — it is NOT tracked in git and never sits on the import path.
Stdlib ``sqlite3`` only: local-first, single file, no server.

Schema
------
``skills`` table: id (PK), name, description, category, status
(``real`` | ``candidate`` | ``refining``), instructions, source, tags (JSON),
priority (0/1), family, notes, created_at, updated_at.
Indexes on id (PK), status, category, source, priority.
``skills_fts``: FTS5 (porter) over id/name/description/instructions, kept in
sync by triggers on every write.

Dedupe decision (recorded, deterministic)
-----------------------------------------
The parked Omega archive (``~/workspace/parked/reference-zips/omega-complete.zip``,
md5 ``680855ca2f4e08951cddfb45d7816390``) holds 258,355 entries with unique
names. 233,355 carry unique instruction blocks; exactly one block
(md5 ``0f9e45ea…``) is shared byte-identical by 25,000 entries. Storing 25,000
identical rows adds nothing, so the seed keeps 250 stride-sampled
representatives (name-sorted, even stride) with a notes field recording the
true 25,000 count. Final candidate rows: 233,605. The 10,000 entries triaged
by the earlier 📦 selection (ids in
``stored/2026-09-25-omega-bulk-stubs/omega_bulk_data.jsonl``) are flagged
``priority=1`` — the refinement backlog, best first.

Invariants
----------
- The live registry is untouched by this module except for the single
  ``skilldb.search`` INFO-risk query skill wired in ``registry.py``.
- Candidate rows are honestly labeled: ``status='candidate'``,
  ``source='omega-bulk'`` — unrefined catalog entries, never implementations.
- ``promote()`` only moves candidate -> refining -> real (or candidate ->
  real directly); downgrading a real skill requires ``force=True``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from levi.skill.registry import Skill, SkillRisk

# ── paths ────────────────────────────────────────────────────────────────

DEFAULT_DB_DIR = Path.home() / ".levi" / "skills"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "skills.db"
DEFAULT_ZIP_PATH = (
    Path.home() / "workspace" / "parked" / "reference-zips" / "omega-complete.zip"
)
PRIORITY_JSONL = (
    Path(__file__).resolve().parents[3]
    / "stored"
    / "2026-09-25-omega-bulk-stubs"
    / "omega_bulk_data.jsonl"
)

STATUSES = ("real", "candidate", "refining")
# md5 prefix of the single instruction block shared by 25,000 archive entries.
CLONE_BLOCK_MD5_PREFIX = "0f9e45ea"
CLONE_BLOCK_COUNT = 25000
CLONE_REPS = 250  # stride-sampled representatives kept


def db_path() -> Path:
    override = os.environ.get("LEVI_SKILLDB_PATH")
    return Path(override).expanduser() if override else DEFAULT_DB_PATH


# ── schema ─────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT 'general',
    status       TEXT NOT NULL CHECK(status IN ('real','candidate','refining')),
    instructions TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',
    priority     INTEGER NOT NULL DEFAULT 0,
    family       TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skills_status   ON skills(status);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_source   ON skills(source);
CREATE INDEX IF NOT EXISTS idx_skills_priority ON skills(priority);
CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
    id, name, description, instructions, tokenize='porter'
);
CREATE TRIGGER IF NOT EXISTS skills_ai AFTER INSERT ON skills BEGIN
    INSERT INTO skills_fts(id, name, description, instructions)
    VALUES (new.id, new.name, new.description, new.instructions);
END;
CREATE TRIGGER IF NOT EXISTS skills_ad AFTER DELETE ON skills BEGIN
    DELETE FROM skills_fts WHERE id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS skills_au AFTER UPDATE ON skills BEGIN
    DELETE FROM skills_fts WHERE id = old.id;
    INSERT INTO skills_fts(id, name, description, instructions)
    VALUES (new.id, new.name, new.description, new.instructions);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextlib.contextmanager
def connect(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Yield a sqlite3 connection with Row rows. Does not create the schema."""
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(path: Optional[Path] = None) -> Path:
    p = Path(path) if path else db_path()
    with connect(p) as con:
        con.executescript(_SCHEMA)
    return p


def _row_to_dict(row: sqlite3.Row) -> Dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    return d


# ── writes ─────────────────────────────────────────────────────────────────

_COLUMNS = (
    "id",
    "name",
    "description",
    "category",
    "status",
    "instructions",
    "source",
    "tags",
    "priority",
    "family",
    "notes",
    "created_at",
    "updated_at",
)


def upsert_skill(con: sqlite3.Connection, row: Dict) -> None:
    """Insert or replace one skill row (FTS sync handled by triggers)."""
    if row.get("status") not in STATUSES:
        raise ValueError(f"bad status: {row.get('status')!r}")
    tags = row.get("tags", [])
    values = [
        row["id"],
        row.get("name", ""),
        row.get("description", ""),
        row.get("category", "general"),
        row["status"],
        row.get("instructions", ""),
        row.get("source", ""),
        json.dumps(tags) if not isinstance(tags, str) else tags,
        int(row.get("priority", 0)),
        row.get("family", ""),
        row.get("notes", ""),
        row.get("created_at") or _now(),
        _now(),
    ]
    con.execute(
        f"INSERT OR REPLACE INTO skills ({','.join(_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(_COLUMNS))})",
        values,
    )


def bulk_upsert(con: sqlite3.Connection, rows: List[Dict]) -> int:
    for r in rows:
        upsert_skill(con, r)
    return len(rows)


_PROMOTE_OK = {
    ("candidate", "refining"),
    ("refining", "real"),
    ("candidate", "real"),
}


def promote(
    skill_id: str,
    to_status: str,
    note: Optional[str] = None,
    path: Optional[Path] = None,
    force: bool = False,
) -> Dict:
    """Move a skill along candidate -> refining -> real.

    Downgrading away from 'real' requires force=True. Records the transition
    in notes with a UTC timestamp.
    """
    if to_status not in STATUSES:
        raise ValueError(f"bad status: {to_status!r}")
    with connect(path) as con:
        cur = con.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"unknown skill id: {skill_id}")
        current = row["status"]
        if current == to_status:
            return _row_to_dict(row)
        if (current, to_status) not in _PROMOTE_OK and not force:
            raise ValueError(
                f"refusing transition {current!r} -> {to_status!r} "
                f"(use force=True to override)"
            )
        notes = row["notes"] or ""
        stamp = f"[{_now()} {current}->{to_status}]"
        notes = (
            f"{notes}\n{stamp} {note}".strip() if note else f"{notes}\n{stamp}".strip()
        )
        con.execute(
            "UPDATE skills SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
            (to_status, notes, _now(), skill_id),
        )
        cur = con.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        return _row_to_dict(cur.fetchone())


# ── reads ──────────────────────────────────────────────────────────────────


def get(skill_id: str, path: Optional[Path] = None) -> Optional[Dict]:
    with connect(path) as con:
        cur = con.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def _fts_query(query: str) -> str:
    # Quote each term so user input can't break MATCH syntax.
    return " ".join('"%s"' % t.replace('"', "") for t in query.split() if t)


def search(
    query: str,
    path: Optional[Path] = None,
    limit: int = 20,
    status: Optional[str] = None,
) -> List[Dict]:
    """Full-text search over name/description/instructions, bm25 ranked."""
    query = query.strip()
    if not query:
        return []
    with connect(path) as con:
        tables = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        filt = "AND s.status = ?" if status else ""
        params: List = [_fts_query(query)]
        if status:
            params.append(status)
        params.append(limit)
        if "skills_fts" in tables:
            try:
                cur = con.execute(
                    "SELECT s.*, bm25(skills_fts) AS _rank FROM skills_fts "
                    "JOIN skills s ON s.id = skills_fts.id "
                    f"WHERE skills_fts MATCH ? {filt} "
                    "ORDER BY _rank LIMIT ?",
                    params,
                )
                return [_row_to_dict(r) for r in cur.fetchall()]
            except sqlite3.OperationalError:
                pass  # fall through to LIKE
        like = f"%{query}%"
        lparams: List = [like, like, like]
        if status:
            lparams.append(status)
        lparams.append(limit)
        cur = con.execute(
            "SELECT * FROM skills WHERE (name LIKE ? OR description LIKE ? "
            f"OR instructions LIKE ?) {filt} LIMIT ?",
            lparams,
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def list_by_status(
    status: str, path: Optional[Path] = None, limit: Optional[int] = None
) -> List[Dict]:
    if status not in STATUSES:
        raise ValueError(f"bad status: {status!r}")
    sql = "SELECT * FROM skills WHERE status = ? ORDER BY priority DESC, id"
    params: List = [status]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with connect(path) as con:
        return [_row_to_dict(r) for r in con.execute(sql, params).fetchall()]


def list_by_category(
    category: str, path: Optional[Path] = None, limit: Optional[int] = None
) -> List[Dict]:
    sql = "SELECT * FROM skills WHERE category = ? ORDER BY priority DESC, id"
    params: List = [category]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with connect(path) as con:
        return [_row_to_dict(r) for r in con.execute(sql, params).fetchall()]


def stats(path: Optional[Path] = None) -> Dict:
    with connect(path) as con:
        total = con.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        by_status = {
            r[0]: r[1]
            for r in con.execute("SELECT status, COUNT(*) FROM skills GROUP BY status")
        }
        by_source = {
            r[0]: r[1]
            for r in con.execute("SELECT source, COUNT(*) FROM skills GROUP BY source")
        }
        prio = con.execute("SELECT COUNT(*) FROM skills WHERE priority = 1").fetchone()[
            0
        ]
    return {
        "total": total,
        "by_status": by_status,
        "by_source": by_source,
        "priority_candidates": prio,
        "db_path": str(Path(path) if path else db_path()),
    }


# ── seeding ────────────────────────────────────────────────────────────────


def seed_real_skills(path: Optional[Path] = None) -> int:
    """Seed every live-registry skill as status='real'. Lazy registry import."""
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    rows = []
    for s in reg.list():
        rows.append(
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "status": "real",
                "instructions": "",
                "source": "levi-registry",
                "tags": list(s.tags),
                "priority": 0,
                "family": "",
                "notes": f"risk={s.risk_level.name}; live SkillRegistry skill",
            }
        )
    with connect(path) as con:
        return bulk_upsert(con, rows)


def _iter_omega_entries(zip_path: Path) -> Iterator[Dict]:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("omega/skills_bulk.json") as fh:
            entries = json.load(fh)
    for e in entries:
        yield e


def _select_candidates(
    entries: List[Dict],
    expected_clone_count: int = CLONE_BLOCK_COUNT,
    expected_reps: int = CLONE_REPS,
    check_prefix: bool = True,
) -> List[Dict]:
    """Apply the recorded dedupe rule; return candidate row dicts.

    - Entries whose instruction block is unique are kept whole.
    - The single block shared by expected_clone_count entries is reduced to
      expected_reps stride-sampled representatives (name-sorted, evenly
      strided), each carrying the true count in notes.
    """
    counts: Dict[str, int] = {}
    for e in entries:
        h = hashlib.md5(e["instructions"].encode("utf-8")).hexdigest()
        counts[h] = counts.get(h, 0) + 1
    big = [h for h, c in counts.items() if c > 1]
    assert len(big) == 1, f"expected exactly one shared block, found {len(big)}"
    big_h = big[0]
    if check_prefix:
        assert big_h.startswith(CLONE_BLOCK_MD5_PREFIX), "shared block md5 changed"
    assert counts[big_h] == expected_clone_count, (
        f"shared block count changed: {counts[big_h]}"
    )

    rows: List[Dict] = []
    clone_names: List[str] = []
    for e in entries:
        h = hashlib.md5(e["instructions"].encode("utf-8")).hexdigest()
        if h == big_h:
            clone_names.append(e["name"])
            continue
        rows.append(
            {
                "id": f"omega-bulk.{e['name']}",
                "name": e["name"],
                "description": e["description"],
                "category": "omega-bulk",
                "status": "candidate",
                "instructions": e["instructions"],
                "source": "omega-bulk",
                "tags": [],
                "priority": 0,
                "family": "",
                "notes": (
                    "Omega catalog entry (unrefined — not an implementation). "
                    f"Archive path: {e.get('path', '')}."
                ),
            }
        )
    clone_names.sort()
    stride = expected_clone_count // expected_reps
    reps = clone_names[::stride]
    assert len(reps) == expected_reps, f"expected {expected_reps} reps, got {len(reps)}"
    # Recover the shared instruction text from any one clone entry.
    shared_instructions = next(
        e["instructions"]
        for e in entries
        if hashlib.md5(e["instructions"].encode("utf-8")).hexdigest() == big_h
    )
    shared_description = next(
        e["description"]
        for e in entries
        if hashlib.md5(e["instructions"].encode("utf-8")).hexdigest() == big_h
    )
    for i, name in enumerate(reps, 1):
        rows.append(
            {
                "id": f"omega-bulk.{name}",
                "name": name,
                "description": shared_description,
                "category": "omega-bulk",
                "status": "candidate",
                "instructions": shared_instructions,
                "source": "omega-bulk",
                "tags": [],
                "priority": 0,
                "family": f"clone-block-{big_h[:8]}",
                "notes": (
                    f"Representative {i} of {expected_reps} for the "
                    f"{expected_clone_count:,}-entry identical-instruction "
                    f"block (md5 {big_h[:8]}…). Omega catalog entry "
                    "(unrefined — not an implementation)."
                ),
            }
        )
    return rows


def _load_priority_ids(jsonl_path: Path) -> set:
    ids = set()
    if not jsonl_path.exists():
        return ids
    with open(jsonl_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["id"])
    return ids


def seed_omega_candidates(
    path: Optional[Path] = None,
    zip_path: Optional[Path] = None,
    priority_jsonl: Optional[Path] = None,
    expected_clone_count: int = CLONE_BLOCK_COUNT,
    expected_reps: int = CLONE_REPS,
    check_prefix: bool = True,
) -> Dict:
    """Seed Omega archive entries as status='candidate' (dedupe rule applied)."""
    zp = Path(zip_path) if zip_path else DEFAULT_ZIP_PATH
    entries = list(_iter_omega_entries(zp))
    rows = _select_candidates(
        entries,
        expected_clone_count=expected_clone_count,
        expected_reps=expected_reps,
        check_prefix=check_prefix,
    )
    prio = _load_priority_ids(
        Path(priority_jsonl) if priority_jsonl else PRIORITY_JSONL
    )
    for r in rows:
        if r["id"] in prio:
            r["priority"] = 1
    matched = sum(1 for r in rows if r["priority"] == 1)
    missing = sorted(prio - {r["id"] for r in rows})
    with connect(path) as con:
        bulk_upsert(con, rows)
    return {
        "archive_entries": len(entries),
        "candidate_rows": len(rows),
        "priority_matched": matched,
        "priority_missing": missing,
    }


def seed_all(
    path: Optional[Path] = None,
    zip_path: Optional[Path] = None,
    priority_jsonl: Optional[Path] = None,
) -> Dict:
    """init_db + seed real skills + seed Omega candidates. Returns a report."""
    import time

    t0 = time.time()
    p = init_db(path)
    n_real = seed_real_skills(p)
    omega = seed_omega_candidates(p, zip_path, priority_jsonl)
    elapsed = time.time() - t0
    size = p.stat().st_size if p.exists() else 0
    return {
        "db_path": str(p),
        "real_skills": n_real,
        **omega,
        "elapsed_seconds": round(elapsed, 1),
        "db_bytes": size,
    }


# ── the one live-registry query skill ──────────────────────────────────────


def _skill_skilldb_search(args: Optional[Dict] = None) -> str:
    args = args or {}
    q = (args.get("query") or args.get("text") or "").strip()
    if not q:
        return "Provide query text to search the skill library."
    p = db_path()
    if not p.exists():
        return (
            "Skill library not seeded yet "
            f"(no database at {p}). Seed it before searching."
        )
    try:
        limit = max(1, min(25, int(args.get("limit", 8))))
    except (TypeError, ValueError):
        limit = 8
    status = args.get("status")
    if status not in (None, *STATUSES):
        return f"Bad status filter: {status!r} (real|candidate|refining)."
    hits = search(q, limit=limit, status=status)
    if not hits:
        return f"No skill-library hits for {q!r}."
    lines = [f"Skill library: {len(hits)} hit(s) for {q!r}"]
    for h in hits:
        lines.append(
            f"  [{h['status']}] {h['id']} — {h['name']}: {h['description'][:110]}"
        )
    return "\n".join(lines)


SKILLDB_SKILLS: List[Skill] = [
    Skill(
        id="skilldb.search",
        name="Skill Library Search",
        description=(
            "Search LEVI's SQLite skill library: real skills plus Omega "
            "refinement candidates."
        ),
        category="meta",
        risk_level=SkillRisk.INFO,
        handler=_skill_skilldb_search,
        tags=["skilldb", "library", "search"],
    ),
]
