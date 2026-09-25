"""ACE failure-lesson loop: one delta lesson per failure, append-only.

Append-only lesson playbook for the growth method (Chauncey, 2026-09-22):

* **Generator** — the agent (or automation) attempts the task.
* **Reflector** — on failure, extract ONE delta lesson: the smallest
  change that would have turned this failure into a success.
* **Curator** — deduplicate (content-addressed: sha256 of the normalized
  lesson text) and gate acceptance on measurable criteria. Rejected
  lessons get a rejection receipt; they are never silently dropped.
* **Playbook** — accepted lessons append to
  ``~/.levi/growth/lessons.jsonl``. Append-only: lessons are never
  edited in place, only superseded by newer lessons that cite them.

This sits alongside :mod:`levi.growth.consolidate` (which writes
learnings into the memory store with Jaccard dedup). The lesson
playbook is the failure-specific, proof-flavored counterpart: every
lesson carries its acceptance evidence and a content hash, so the
method can answer "what did we learn from failure X" without
re-deriving it.

Binding rails (same as the rest of growth):
  * lessons are functional ("when X, do Y"), never sentience claims —
    the blocklist in :mod:`levi.growth.guards` is enforced here too;
  * the playbook lives in the growth dir; nothing outside growth may
    write it, and growth writes nowhere else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from levi.growth import journal as _journal
from levi.growth.guards import check_no_sentience_claim


# ---------------------------------------------------------------------------
# Content addressing
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Canonical form for content addressing: lowercase, single spaces."""
    return _WS.sub(" ", (text or "").strip().lower())


def lesson_id(content: str) -> str:
    """Content address of a lesson: sha256 of the normalized text."""
    return "les-" + hashlib.sha256(normalize(content).encode("utf-8")).hexdigest()[:16]


def playbook_path() -> Path:
    return _journal.growth_dir() / "lessons.jsonl"


# ---------------------------------------------------------------------------
# Lesson record
# ---------------------------------------------------------------------------

DELTA_RE = re.compile(
    r"\b(instead|rather than|next time|change|avoid|prefer|before)\b", re.IGNORECASE
)
VERIFY_RE = re.compile(
    r"\b(verify|check|test|confirm|measure|watch for|acceptance)\b", re.IGNORECASE
)


@dataclass
class DeltaLesson:
    """One failure → one delta lesson (the Reflector's output)."""

    failure: str  # what failed, one line
    lesson: str  # the delta: smallest change that fixes it
    verification: str  # how to tell the fix worked (measurable)
    provenance: dict = field(default_factory=dict)  # source, cycle, ts, mode

    @property
    def id(self) -> str:
        return lesson_id(self.lesson)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        return d


@dataclass
class CuratorVerdict:
    accepted: bool
    reason: str
    lesson_id: str = ""


# ---------------------------------------------------------------------------
# Reflector: one delta lesson from a failure
# ---------------------------------------------------------------------------

_FAIL_HINT = re.compile(
    r"\b(failed|failure|error|exception|traceback|denied|timeout|"
    r"timed out|not found|blocked|already running|crashed|broke|"
    r"didn't work|not working)\b",
    re.IGNORECASE,
)


def is_failure_text(text: str) -> bool:
    """Whether a text describes a failure worth reflecting on."""
    return bool(_FAIL_HINT.search(text or ""))


def extract_delta_lesson(
    failure: str,
    *,
    context: str = "",
    provenance: dict | None = None,
) -> DeltaLesson | None:
    """Reflector: distill ONE delta lesson from a failure report.

    The delta is the smallest behavioral change that would have turned
    this failure into a success. Returns None when the failure text
    carries no actionable signal (or trips the sentience blocklist).
    """
    failure = (failure or "").strip()
    if len(failure) < 12 or not is_failure_text(failure):
        return None
    if check_no_sentience_claim(failure):
        return None

    # Failure-specific deltas (offline, deterministic). Each pattern
    # names the failure shape and the one change that fixes it.
    text = failure.lower()
    if "timeout" in text or "timed out" in text:
        delta = (
            "When a call times out, shrink the work unit or raise the "
            "timeout explicitly before retrying — never re-fire the same "
            "call with the same budget."
        )
        verify = "Check that the retried call completes inside the new budget."
    elif "denied" in text or "permission" in text or "not allowed" in text:
        delta = (
            "When an action is denied, stop and surface the denial to the "
            "owner instead of retrying or routing around it — a denial is "
            "a decision, not a transient error."
        )
        verify = "Verify no retry of the denied action occurs in the same run."
    elif "not found" in text or "no such" in text or "missing" in text:
        delta = (
            "When a path, file, or record is 'not found', re-list the "
            "parent scope before trying again — the reference is stale, "
            "not the world."
        )
        verify = "Check that the re-listed scope is consulted before any further access."
    elif "locked" in text or "already running" in text or "in use" in text:
        delta = (
            "When a resource reports locked/in-use, back off and poll or "
            "queue instead of forcing it — a sibling holds it; forcing "
            "corrupts both sides."
        )
        verify = "Verify no forced write occurs while the lock is held."
    else:
        delta = (
            "When a step fails, change exactly one thing (arguments, "
            "preconditions, or approach) before retrying — the blind "
            "repeat is what failed."
        )
        verify = "Check that the retry differs from the failed attempt in at least one input."
    if context:
        delta += " Context: %s" % _snip(context, 160)

    lesson = DeltaLesson(
        failure=_snip(failure, 200),
        lesson=delta,
        verification=verify,
        provenance=dict(provenance or {}),
    )
    if check_no_sentience_claim(lesson.lesson):
        return None
    return lesson


def _snip(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit]


# ---------------------------------------------------------------------------
# Curator: dedup + acceptance gate
# ---------------------------------------------------------------------------

# Acceptance criteria (measurable, checked per lesson):
#   A1. the lesson names a delta change (instead/rather than/next time/…)
#   A2. the lesson states a verification check (verify/check/test/…)
#   A3. the lesson is self-contained (>= 24 chars, one clear directive)
ACCEPTANCE = ("A1-delta-named", "A2-verification-stated", "A3-self-contained")


def acceptance_check(lesson: DeltaLesson) -> list[str]:
    """Return the list of acceptance criteria the lesson FAILS (empty = pass)."""
    failed: list[str] = []
    text = lesson.lesson or ""
    if not DELTA_RE.search(text):
        failed.append("A1-delta-named")
    if not (VERIFY_RE.search(text) or VERIFY_RE.search(lesson.verification or "")):
        failed.append("A2-verification-stated")
    if len(text.strip()) < 24:
        failed.append("A3-self-contained")
    return failed


def read_playbook(limit: int = 10000) -> list[dict[str, Any]]:
    """Read accepted lessons (tolerates corrupt lines)."""
    try:
        lines = playbook_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
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
    return out[-limit:]


def curate(
    lesson: DeltaLesson,
    *,
    existing_ids: set[str] | None = None,
) -> CuratorVerdict:
    """Curator: dedup by content hash, then gate on acceptance criteria.

    Rejections carry a receipt (which criteria failed) — nothing is
    silently dropped.
    """
    if not isinstance(lesson, DeltaLesson):
        return CuratorVerdict(False, "not-a-lesson")
    ids = existing_ids
    if ids is None:
        ids = {str(r.get("id", "")) for r in read_playbook()}
    if lesson.id in ids:
        return CuratorVerdict(
            False, "duplicate: content hash %s already in playbook" % lesson.id,
            lesson_id=lesson.id,
        )
    failed = acceptance_check(lesson)
    if failed:
        return CuratorVerdict(
            False,
            "acceptance gate: failed %s" % ",".join(failed),
            lesson_id=lesson.id,
        )
    return CuratorVerdict(True, "accepted: %s" % ",".join(ACCEPTANCE),
                          lesson_id=lesson.id)


def append_lesson(lesson: DeltaLesson, *, cycle_id: str = "") -> dict[str, Any]:
    """Append one accepted lesson to the playbook. Returns the record.

    Raises ValueError when the lesson is not a DeltaLesson. The caller
    is expected to run :func:`curate` first; this function re-checks
    the gate defensively (belt and suspenders).
    """
    if not isinstance(lesson, DeltaLesson):
        raise ValueError(
            "append_lesson: lesson must be a DeltaLesson, got %s"
            % type(lesson).__name__
        )
    verdict = curate(lesson)
    if not verdict.accepted:
        raise ValueError("append_lesson: lesson rejected (%s)" % verdict.reason)
    rec = lesson.to_dict()
    rec["ts"] = _journal.now_iso()
    rec["cycle_id"] = cycle_id
    rec["kind"] = "lesson"
    rec["status"] = "accepted"
    with open(playbook_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ---------------------------------------------------------------------------
# ACE loop driver: run over a cycle's experiences
# ---------------------------------------------------------------------------

def ace_cycle(
    experiences: list,
    *,
    cycle_id: str = "",
    dry_run: bool = False,
    max_lessons: int = 5,
) -> dict[str, Any]:
    """Run the ACE loop over one batch of experiences.

    Generator = whatever produced the experiences. Reflector extracts
    one delta lesson per qualifying failure. Curator dedups + gates.
    Accepted lessons append to the playbook (unless dry_run).

    Returns ``{proposed, accepted, duplicates, rejected, lessons}``.
    """
    report: dict[str, Any] = {
        "proposed": 0,
        "accepted": 0,
        "duplicates": 0,
        "rejected": 0,
        "lessons": [],
        "rejections": [],
    }
    existing_ids = {str(r.get("id", "")) for r in read_playbook()}
    seen_this_run: set[str] = set()
    for exp in experiences or []:
        if report["proposed"] >= max_lessons:
            break
        content = getattr(exp, "content", "") or ""
        if not is_failure_text(content):
            continue
        source = getattr(exp, "source", "") or ""
        # One lesson per failure source per run: the Reflector's "one
        # delta per failure" rule, kept cheap.
        if source in seen_this_run:
            continue
        seen_this_run.add(source)
        lesson = extract_delta_lesson(
            content,
            provenance={
                "mode": "ace",
                "source": source,
                "experience_id": getattr(exp, "id", ""),
                "ts": getattr(exp, "ts", ""),
                "cycle_id": cycle_id,
            },
        )
        if lesson is None:
            continue
        report["proposed"] += 1
        verdict = curate(lesson, existing_ids=existing_ids)
        entry = {
            "id": lesson.id,
            "failure": lesson.failure,
            "lesson": lesson.lesson,
            "verification": lesson.verification,
            "verdict": verdict.reason,
        }
        if not verdict.accepted:
            if verdict.reason.startswith("duplicate"):
                report["duplicates"] += 1
            else:
                report["rejected"] += 1
            report["rejections"].append(entry)
            continue
        if not dry_run:
            append_lesson(lesson, cycle_id=cycle_id)
            existing_ids.add(lesson.id)
        report["accepted"] += 1
        report["lessons"].append(entry)
    return report
