"""Shared paths, constants, and the generic hash-chained receipt writer.

One convention for both arrival receipts and verdict receipts: each
line of JSONL carries a sha256 that commits to the previous line's
hash (same detect-not-prevent posture as the rest of the repo —
detect, not tamper-proof, against disk access).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

GENESIS_PREV = "0" * 64

# The 11 SOXI subjects, canonical form (per the teacher brief).
SUBJECTS = (
    "arithmetic",
    "algebra",
    "geometry",
    "trigonometry",
    "english_grammar",
    "chemistry",
    "physics",
    "history",
    "government",
    "civics",
    "reasoning_puzzles",
)

SUBJECT_ALIASES = {
    "grammar": "english_grammar",
    "english grammar": "english_grammar",
    "reasoning": "reasoning_puzzles",
    "logic puzzles": "reasoning_puzzles",
    "reasoning/logic puzzles": "reasoning_puzzles",
    "reasoning_puzzles": "reasoning_puzzles",
}

# The four provisional persona frames (teacher brief: do not rename).
FRAMES = ("void", "strategist", "chaotic_good", "lens_terse_systems")

KINDS = ("qa", "reasoning", "correction")

# Teacher brief: plain ASCII, no hype words.
HYPE_WORDS = (
    "amazing",
    "incredible",
    "revolutionary",
    "game-changer",
    "gamechanger",
    "mind-blowing",
    "mindblowing",
    "unbelievable",
    "astonishing",
    "phenomenal",
)

# No sentience claims from a teacher (brief: never claim feelings,
# consciousness, or being alive).
SENTIENCE_WORDS = ("conscious", "consciousness", "i am alive", "i feel", "my feelings")


def base_dir() -> Path:
    """Storage root — ``~/.levi/soxi/return`` (override: LEVI_SOXI_RETURN_DIR)."""
    override = os.environ.get("LEVI_SOXI_RETURN_DIR")
    p = Path(override).expanduser() if override else (
        Path.home() / ".levi" / "soxi" / "return"
    )
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("inbox", "quarantine", "raw", "sync", "spotcheck"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_BATCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def check_batch_id(batch_id: str) -> str:
    if not isinstance(batch_id, str) or not _BATCH_RE.fullmatch(batch_id):
        raise ValueError("batch_id must be 1-128 chars of [A-Za-z0-9_.-]")
    return batch_id


def canonical_lesson(lesson: dict) -> bytes:
    body = {k: lesson[k] for k in sorted(lesson)}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def lesson_content_hash(lesson: dict) -> str:
    """Identity of a lesson: hash of its canonical form."""
    return hashlib.sha256(canonical_lesson(lesson)).hexdigest()


def normalize_subject(raw: str) -> str | None:
    key = (raw or "").strip().lower().replace("_", " ")
    if key in SUBJECTS:
        return key.replace(" ", "_") if " " in key else key
    return SUBJECT_ALIASES.get(key)


# ---------------------------------------------------------------------------
# Generic chained-receipt writer (arrivals.jsonl, verdicts.jsonl)
# ---------------------------------------------------------------------------

def _receipt_hash(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def read_chain(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
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
    return out


def verify_chain(path: Path) -> tuple[bool, list[str]]:
    recs = read_chain(path)
    errors: list[str] = []
    prev = GENESIS_PREV
    for i, rec in enumerate(recs):
        if rec.get("seq") != i + 1:
            errors.append(f"receipt {i}: seq {rec.get('seq')} != {i + 1}")
        if rec.get("prev_hash") != prev:
            errors.append(f"receipt {i}: prev_hash linkage broken")
        if _receipt_hash(rec) != rec.get("hash"):
            errors.append(f"receipt {i}: hash mismatch (tampered)")
        prev = rec.get("hash", "")
        if not isinstance(prev, str) or len(prev) != 64:
            errors.append(f"receipt {i}: malformed hash")
            prev = GENESIS_PREV
    return (not errors), errors


def append_receipt(path: Path, rec: dict) -> dict:
    recs = read_chain(path)
    ok, errors = verify_chain(path)
    if not ok:
        raise ValueError("chain broken on %s: %s" % (path, "; ".join(errors)))
    seq = len(recs) + 1
    prev = recs[-1]["hash"] if recs else GENESIS_PREV
    rec = dict(rec)
    rec["seq"] = seq
    rec["prev_hash"] = prev
    rec["hash"] = _receipt_hash(rec)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
