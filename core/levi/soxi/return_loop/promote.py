"""Local promotion into the knowledge store (R1, R3, R6).

Only lessons from a PASS or PASS_WITH_CORRECTIONS verdict promote
(R1 — promote() cross-checks the verdict receipt, no back door). Each
lesson lands in a SQLite store with full provenance: source, teacher
frame, batch, date. Corrections promote as new versioned lessons
referencing their originals. Every promotion carries a promotion_id;
revert_promotion(promotion_id) rolls it back (R6) with a chained
receipt — nothing is ever deleted, reverted rows are marked.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .common import (
    append_receipt,
    base_dir,
    check_batch_id,
    lesson_content_hash,
    read_chain,
    utcnow,
)
from .verify import verdicts_path


def store_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "store.db"


def _conn(base: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(store_path(base)))
    c.execute(
        """CREATE TABLE IF NOT EXISTS lessons (
             lesson_id   TEXT PRIMARY KEY,
             kind        TEXT,
             subject     TEXT,
             persona_id  TEXT,
             text        TEXT,
             version     INTEGER,
             correction_of TEXT,
             batch_id    TEXT,
             teacher     TEXT,
             promoted_ts TEXT,
             promotion_id TEXT,
             reverted    INTEGER DEFAULT 0
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS promotions (
             promotion_id TEXT PRIMARY KEY,
             ts           TEXT,
             batch_id     TEXT,
             lesson_count INTEGER,
             verdict_ref  TEXT
           )"""
    )
    return c


def _raw_lessons(batch_id: str, base: Path) -> list[dict]:
    raw_path = base / "raw" / (batch_id + ".jsonl")
    return [json.loads(l) for l in raw_path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def _correction_lessons(batch_id: str, base: Path) -> list[dict]:
    cpath = base / "corrections" / (batch_id + ".jsonl")
    if not cpath.exists():
        return []
    return [json.loads(l) for l in cpath.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def promote_batch(batch_id: str, base: Path | None = None) -> dict[str, Any]:
    """Promote verified lessons of one batch into the local store.

    Raises if the batch lacks a PASS/PASS_WITH_CORRECTIONS verdict
    (R1). Duplicates already in the store are skipped, not
    re-inserted (R4). Corrections promote as versioned new lessons.
    """
    base = base or base_dir()
    batch_id = check_batch_id(batch_id)

    verdict = None
    for rec in read_chain(verdicts_path(base)):
        if rec.get("batch_id") == batch_id:
            verdict = rec
            break
    if verdict is None or verdict["verdict"] not in (
        "PASS", "PASS_WITH_CORRECTIONS"
    ):
        raise ValueError(
            "promote_batch: %s has no promotable verdict (R1)" % batch_id
        )

    bad_indexes = {c["index"] for c in verdict.get("corrections_needed", [])}
    lessons: list[dict[str, Any]] = []
    for i, raw in enumerate(_raw_lessons(batch_id, base)):
        if i in bad_indexes:
            continue  # the flawed version never promotes; its correction does
        lessons.append(
            {
                "lesson_id": raw.get("topic_id") or lesson_content_hash(raw),
                "kind": raw["kind"],
                "subject": raw["topic"],
                "persona_id": raw["persona_condition"]["persona_id"],
                "text": raw["text"],
                "version": 1,
                "correction_of": None,
            }
        )
    for corr in _correction_lessons(batch_id, base):
        lessons.append(
            {
                "lesson_id": corr["topic_id"],
                "kind": "correction",
                "subject": corr["topic"],
                "persona_id": corr["persona_condition"]["persona_id"],
                "text": corr["text"],
                "version": corr.get("version", 2),
                "correction_of": corr.get("correction_of"),
            }
        )

    arrival = next(
        (r for r in read_chain(base / "arrivals.jsonl")
         if r.get("batch_id") == batch_id),
        {},
    )
    promotion_id = "promo-" + utcnow().replace(":", "").replace("+", "z")
    conn = _conn(base)
    cur = conn.cursor()
    inserted = 0
    for l in lessons:
        cur.execute("SELECT 1 FROM lessons WHERE lesson_id = ?", (l["lesson_id"],))
        if cur.fetchone():
            continue  # R4: already promoted, skip — never re-teach
        cur.execute(
            """INSERT INTO lessons
               (lesson_id, kind, subject, persona_id, text, version,
                correction_of, batch_id, teacher, promoted_ts,
                promotion_id, reverted)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                l["lesson_id"], l["kind"], l["subject"], l["persona_id"],
                l["text"], l["version"], l["correction_of"], batch_id,
                arrival.get("teacher", "grok"), utcnow(), promotion_id,
            ),
        )
        inserted += 1
    cur.execute(
        "INSERT INTO promotions (promotion_id, ts, batch_id, lesson_count, verdict_ref)"
        " VALUES (?,?,?,?,?)",
        (promotion_id, utcnow(), batch_id, inserted, verdict["hash"]),
    )
    conn.commit()
    conn.close()

    append_receipt(
        base / "promotions.jsonl",
        {
            "ts": utcnow(),
            "promotion_id": promotion_id,
            "batch_id": batch_id,
            "verdict": verdict["verdict"],
            "lessons_promoted": inserted,
            "lessons_skipped_dup": len(lessons) - inserted,
        },
    )
    return {"promotion_id": promotion_id, "batch_id": batch_id,
            "lessons_promoted": inserted}


def revert_promotion(promotion_id: str, base: Path | None = None) -> dict[str, Any]:
    """Roll back one promotion (R6): rows marked reverted, receipt written."""
    base = base or base_dir()
    conn = _conn(base)
    cur = conn.cursor()
    cur.execute(
        "UPDATE lessons SET reverted = 1 WHERE promotion_id = ? AND reverted = 0",
        (promotion_id,),
    )
    n = cur.rowcount
    if n == 0:
        conn.close()
        raise ValueError("revert_promotion: %s not found or already reverted"
                         % promotion_id)
    conn.commit()
    conn.close()
    rec = append_receipt(
        base / "promotions.jsonl",
        {"ts": utcnow(), "promotion_id": promotion_id,
         "reverted": True, "lessons_reverted": n},
    )
    return {"promotion_id": promotion_id, "lessons_reverted": n,
            "receipt": rec}


def store_count(base: Path | None = None) -> dict[str, int]:
    base = base or base_dir()
    conn = _conn(base)
    cur = conn.cursor()
    active = cur.execute("SELECT COUNT(*) FROM lessons WHERE reverted = 0").fetchone()[0]
    reverted = cur.execute("SELECT COUNT(*) FROM lessons WHERE reverted = 1").fetchone()[0]
    conn.close()
    return {"active": active, "reverted": reverted}
