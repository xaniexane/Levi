"""Verification gate (R1, R3, R4, R5).

Every returned batch gets exactly one verdict — PASS,
PASS_WITH_CORRECTIONS, or QUARANTINE — recorded as a hash-chained
verdict receipt carrying the full reason set. What "verified" means:

  schema        — each line is a lesson dict with persona_condition
                  (persona_id/role/tone), kind, topic, text
  ascii         — text is plain ASCII (teacher brief)
  hype          — no hype words (teacher brief)
  sentience     — no feelings/consciousness/alive claims (teacher brief)
  frame         — persona_id is one of the four provisional frames
  subject       — topic is one of the 11 SOXI subjects
  arithmetic    — qa lessons matching a strict arithmetic pattern get
                  their answer mechanically re-checked
  duplicates    — content hash / teacher topic_id already seen ->
                  re-teach flagged (R4)

Verdict rule (fail-closed): any malformed line quarantines the WHOLE
batch (R5 — the arrival is still receipted; the bytes sit in
quarantine/, never dropped). Correctable findings (bad arithmetic,
hype, duplicates, sentience claims, unknown frame) make the batch
PASS_WITH_CORRECTIONS. Clean batches PASS.

Honest limit: only arithmetic of the strict Q/A form is machine-
checkable here. History, government, grammar, civics, and the rest
are beyond an offline check — those lessons pass schema/style and are
filed in the spot-check queue for Chauncey; the verdict records that
their facts were NOT machine-verified.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .common import (
    FRAMES,
    HYPE_WORDS,
    KINDS,
    SENTIENCE_WORDS,
    append_receipt,
    base_dir,
    check_batch_id,
    lesson_content_hash,
    normalize_subject,
    read_chain,
    utcnow,
)

_ARITH_RE = re.compile(
    r"[Qq]:\s*(?:what is\s+)?(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*"
    r"(-?\d+(?:\.\d+)?)[^?]*\?\s*.*?[Aa]:\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def check_ascii(text: str) -> bool:
    return all(ord(c) < 128 for c in text)


def find_hype(text: str) -> list[str]:
    low = text.lower()
    return sorted({w for w in HYPE_WORDS
                   if re.search(r"\b" + re.escape(w) + r"\b", low)})


def find_sentience_claims(text: str) -> list[str]:
    low = text.lower()
    return sorted({w for w in SENTIENCE_WORDS
                   if re.search(r"\b" + re.escape(w) + r"\b", low)})


def check_arithmetic(text: str) -> tuple[str, str]:
    """Strict arithmetic Q/A re-check.

    Returns ("ok"/"wrong"/"not_checkable", detail). Only fires on
    lessons that match the strict pattern; everything else is
    honestly marked not_checkable.
    """
    m = _ARITH_RE.search(text)
    if not m:
        return "not_checkable", "no strict arithmetic pattern found"
    a, op, b, given = float(m.group(1)), m.group(2), float(m.group(3)), float(m.group(4))
    truth = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else None}[op]
    if truth is None:
        return "not_checkable", "division by zero in question"
    if abs(given - truth) < 1e-9:
        return "ok", f"{a:g}{op}{b:g}={truth:g}"
    return "wrong", f"claims {given:g}, computes {truth:g}"


def topics_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "topics.json"


def load_seen(base: Path | None = None) -> dict[str, list[str]]:
    """Seen lesson identities per subject: {subject: [content_hashes]}."""
    base = base or base_dir()
    p = topics_path(base)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_seen(seen: dict[str, list[str]], base: Path | None = None) -> None:
    base = base or base_dir()
    topics_path(base).write_text(json.dumps(seen, indent=2), encoding="utf-8")


def verdicts_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "verdicts.jsonl"


def _validate_schema(obj: Any) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "line is not a JSON object"
    pc = obj.get("persona_condition")
    if not isinstance(pc, dict):
        return False, "missing persona_condition object"
    for k in ("persona_id", "role", "tone"):
        if not isinstance(pc.get(k), str) or not pc[k]:
            return False, f"persona_condition missing {k}"
    if obj.get("kind") not in KINDS:
        return False, "kind must be one of %s" % (KINDS,)
    if not isinstance(obj.get("topic"), str) or not obj["topic"]:
        return False, "missing topic"
    if not isinstance(obj.get("text"), str) or not obj["text"]:
        return False, "missing text"
    return True, ""


def verify_batch(batch_id: str, base: Path | None = None) -> dict[str, Any]:
    """Verify one intake batch. Writes exactly one verdict receipt."""
    base = base or base_dir()
    batch_id = check_batch_id(batch_id)

    # already-verified batches are not re-verified (one verdict each)
    for rec in read_chain(verdicts_path(base)):
        if rec.get("batch_id") == batch_id:
            raise ValueError("verify_batch: %s already has a verdict" % batch_id)

    raw_path = base / "raw" / (batch_id + ".jsonl")
    if not raw_path.exists():
        raise ValueError("verify_batch: raw batch not found for %s" % batch_id)

    lines = raw_path.read_text(encoding="utf-8").splitlines()
    seen = load_seen(base)
    lessons: list[dict] = []
    corrections_needed: list[dict] = []  # {index, reasons, lesson}
    malformed: list[dict] = []           # {index, reason}
    spotcheck: list[dict] = []           # {index, lesson_id, reason}

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            malformed.append({"index": i, "reason": f"json parse error: {e}"})
            continue
        ok, reason = _validate_schema(obj)
        if not ok:
            malformed.append({"index": i, "reason": reason})
            continue

        lid = obj.get("topic_id") or lesson_content_hash(obj)
        reasons: list[str] = []
        subject = normalize_subject(obj["topic"])
        if subject is None:
            reasons.append("topic not one of the 11 SOXI subjects: %r" % obj["topic"])

        text = obj["text"]
        if not check_ascii(text):
            reasons.append("non-ASCII characters present")
        hype = find_hype(text)
        if hype:
            reasons.append("hype words: %s" % ", ".join(hype))
        sent = find_sentience_claims(text)
        if sent:
            reasons.append("sentience claims: %s" % ", ".join(sent))
        if obj["persona_condition"]["persona_id"] not in FRAMES:
            reasons.append("unknown persona frame: %r" % obj["persona_condition"]["persona_id"])

        if subject == "arithmetic" and obj["kind"] == "qa":
            status, detail = check_arithmetic(text)
            if status == "wrong":
                reasons.append("arithmetic answer wrong (%s)" % detail)

        subj_key = subject or obj["topic"]
        if lid in seen.get(subj_key, []):
            reasons.append("re-teach: lesson identity already seen")

        lessons.append({"index": i, "lesson": obj, "lesson_id": lid,
                        "subject": subject})
        if reasons:
            corrections_needed.append({"index": i, "lesson_id": lid,
                                       "reasons": reasons})
        elif subject and subject != "arithmetic":
            spotcheck.append({"index": i, "lesson_id": lid,
                              "reason": "facts not machine-verifiable; human spot-check"})

    if malformed:
        # R5: malformed quarantines the whole batch; bytes preserved.
        qdir = base / "quarantine"
        qdir.mkdir(parents=True, exist_ok=True)
        qpath = qdir / (batch_id + ".jsonl")
        if not qpath.exists():
            shutil.copy2(raw_path, qpath)
        verdict = "QUARANTINE"
        notes = ["malformed lines: %d" % len(malformed)]
    elif corrections_needed:
        verdict = "PASS_WITH_CORRECTIONS"
        notes = [f"line {c['index']}: " + "; ".join(c["reasons"])
                 for c in corrections_needed]
    else:
        verdict = "PASS"
        notes = ["clean"]

    rec = append_receipt(
        verdicts_path(base),
        {
            "ts": utcnow(),
            "batch_id": batch_id,
            "verdict": verdict,
            "lesson_count": len(lessons),
            "clean_count": len(lessons) - len(corrections_needed),
            "corrections_needed": corrections_needed,
            "malformed": malformed,
            "spotcheck": spotcheck,
            "notes": notes,
        },
    )
    # mark good+corrected lessons as seen so re-teaches are caught (R4)
    if verdict in ("PASS", "PASS_WITH_CORRECTIONS"):
        for e in lessons:
            seen.setdefault(e["subject"] or e["lesson"]["topic"], [])
            if e["lesson_id"] not in seen[e["subject"] or e["lesson"]["topic"]]:
                seen[e["subject"] or e["lesson"]["topic"]].append(e["lesson_id"])
        save_seen(seen, base)
    return rec
