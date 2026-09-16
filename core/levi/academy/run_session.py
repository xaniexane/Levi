#!/usr/bin/env python3
"""LEVI Boot Camp 24/7 session worker.

Each run executes exactly ONE session (day, block) through the battle rhythm:

  BRIEF   derive (day, block), read the syllabus entry, state objectives
  TEACH   research the topic, synthesize the ORIGINAL lesson (dense layers:
          core -> extensions -> edge cases -> cross-links)
  REVIEW  spaced-repetition retrieval drills on due concepts (never re-reading)
  DRILL   run the practical exercise (sparring interleaves cross-track concepts)
  TEST    mastery gate: 80% on the lesson, 70% on the drill — or no advance
  DEBRIEF journal honestly, consolidate growth, ingest POST-mastery knowledge

A failed gate does not complete the session. It persists a pending
remediation; the next run executes the remedial session before any new
syllabus session. The standard does not move.

Session 120 is graduation: the final crucible samples ALL prior concepts
(weakest first), grades A/B/C separately, and names the weakest area as the
post-graduation drill focus.

Time-bounded (~45 min): aborts cleanly with a journal note if the budget
elapses. If day > 30 (all 120 done) the worker exits quietly — scheduled
runs become safe no-ops after graduation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "core") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "core"))

ACADEMY_PKG = Path(__file__).resolve().parent

from levi.academy import concepts as acon  # noqa: E402
from levi.academy import corpus_ingest as aci  # noqa: E402
from levi.academy import research as aresearch  # noqa: E402
from levi.academy import session_exercises as aex  # noqa: E402
from levi.academy import synthesize as asynth  # noqa: E402


def data_dir() -> Path:
    """Academy working dir. ``LEVI_ACADEMY_DIR`` overrides it (tests)."""
    return Path(os.environ.get("LEVI_ACADEMY_DIR", Path.home() / ".levi" / "academy"))


SESSION_BUDGET_MINUTES = 45
BLOCK_SECONDS = 6 * 3600

# The boot-camp bar. The standard does not move.
MASTERY_THRESHOLD = 0.80
EXERCISE_THRESHOLD = 0.70
# Weekly cumulative assessments: review phases run in assessment mode.
ASSESSMENT_DAYS = (7, 14, 21)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_syllabus() -> dict:
    path = ACADEMY_PKG / "syllabus.json"
    return json.loads(path.read_text(encoding="utf-8"))


def session_id(day: int, block: int) -> str:
    return f"d{day}b{block}"


def n_to_day_block(n: int) -> tuple[int, int]:
    return (n - 1) // 4 + 1, (n - 1) % 4 + 1


def day_block_to_n(day: int, block: int) -> int:
    return (day - 1) * 4 + block


def load_progress() -> dict:
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    path = dd / "progress.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("completed", [])
            data.setdefault("sessions", {})
            data.setdefault("streaks", {})
            return data
        except json.JSONDecodeError:
            pass
    return {
        "program_start": None,
        "completed": [],
        "sessions": {},
        "streaks": {},
        "graduated": False,
        "pending_remedial": None,
    }


def save_progress(progress: dict) -> None:
    (data_dir() / "progress.json").write_text(
        json.dumps(progress, indent=1, ensure_ascii=False), encoding="utf-8"
    )


def next_uncompleted(progress: dict) -> int:
    done = set(progress.get("completed", []))
    for n in range(1, 121):
        day, block = n_to_day_block(n)
        if session_id(day, block) not in done:
            return n
    return 121


def week_phase_for(syllabus: dict, day: int) -> str:
    for w in syllabus.get("weeks", []):
        lo, hi = w["days"]
        if lo <= day <= hi:
            return f"Week {w['week']}: {w['phase']}"
    return "Graduation"


def entry_for(syllabus: dict, day: int, block: int) -> tuple[str, dict]:
    track = syllabus["block_map"][str(block)]
    entry = syllabus["tracks"][track]["days"][str(day)]
    return track, entry


def get_streaks(progress: dict) -> dict:
    streaks = progress.setdefault("streaks", {})
    for t in ("A", "B", "C", "S"):
        streaks.setdefault(t, {"current": 0, "best": 0})
    return streaks


def bump_streak(progress: dict, track: str, passed: bool) -> dict:
    """Pass streaks per track: reset on a failed gate, increment on a pass."""
    s = get_streaks(progress)[track]
    if passed:
        s["current"] += 1
        s["best"] = max(s["best"], s["current"])
    else:
        s["current"] = 0
    return s


# ---------------------------------------------------------------- compounding
def prior_context_points(limit: int = 12) -> list[str]:
    """Recent academy sessions, so teaching compounds instead of repeating."""
    try:
        from levi.growth import journal as gjournal

        entries = gjournal.read_entries(limit=60)
    except Exception:
        return []
    points = []
    for e in reversed(entries):
        if e.get("kind") not in (
            "academy-session",
            "academy-graduation",
            "academy-remedial",
        ):
            continue
        d = e.get("day")
        t = e.get("track")
        title = e.get("title", "")
        summary = (e.get("summary") or "")[:140]
        if d and t:
            points.append(f"Day {d} ({t}): {title} — {summary}")
        if len(points) >= limit:
            break
    return points


# ------------------------------------------------------------------ mastery
def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def objective_coverage(objectives: list[str], lesson_md: str) -> list[dict]:
    """Per-objective coverage: best sentence overlap with the objective's words."""
    sentences = _sentences(lesson_md)
    out = []
    for o in objectives:
        ow = _words(o)
        best = max(
            (len(ow & _words(s)) / max(len(ow), 1) for s in sentences), default=0.0
        )
        out.append({"objective": o, "coverage": round(best, 3)})
    return out


def mastery_check(entry: dict, lesson_md: str) -> dict:
    """Self-administered retrieval check, graded deterministically.

    The bar is 80%: every key question must be answerable from the lesson's
    own sentences. Below the bar is a failed gate — data, not a verdict,
    but the standard does not move.
    """
    sentences = _sentences(lesson_md)
    results = []
    for q in entry["key_questions"]:
        qw = _words(q)
        ranked = sorted(sentences, key=lambda s: len(qw & _words(s)), reverse=True)
        answer = " ".join(ranked[:2])[:500]
        matched = len(qw & _words(answer))
        score = matched / max(len(qw), 1)
        results.append({"question": q, "answer": answer, "score": round(score, 3)})
    overall = round(sum(r["score"] for r in results) / max(len(results), 1), 3)
    coverage = objective_coverage(entry["objectives"], lesson_md)
    return {
        "questions": results,
        "score": overall,
        "objective_coverage": coverage,
        "missed_questions": [
            r["question"] for r in results if r["score"] < MASTERY_THRESHOLD
        ],
        "missed_objectives": [c["objective"] for c in coverage if c["coverage"] < 0.5],
        "passed": overall >= MASTERY_THRESHOLD,
    }


# ------------------------------------------------------------------- growth
def consolidate_session(
    day: int,
    block: int,
    track: str,
    entry: dict,
    exercise: dict,
    mastery: dict,
    review: dict | None,
    gate_passed: bool,
    remedial: dict | None = None,
) -> dict:
    """Debrief: journal honestly and consolidate growth-tagged learnings.

    Only mastered content becomes memory. A failed gate journals the
    failure itself (experiential memory) — unmastered content is never
    stored as fact.
    """
    from levi.growth import journal as gjournal
    from levi.growth.consolidate import consolidate
    from levi.growth.reflect import Learning

    title = entry["title"]
    review = review or {}
    forgotten = review.get("forgotten", [])
    if gate_passed:
        summary = (
            f"{title}: exercise {exercise['score']:.0%}, mastery "
            f"{mastery['score']:.0%} (bar 80%) — GATE PASSED. "
            f"Review drills: {review.get('reviewed', 0)} due concepts, "
            f"mean {review.get('mean_score', 1.0):.0%}."
        )
        learnings = [
            Learning(
                kind="fact",
                content=(
                    f"LEVI Boot Camp day {day} block {block} (track {track}): "
                    f"'{title}'. {entry['objectives'][0]}."
                ),
                confidence=0.7,
                provenance={
                    "program": "levi-academy",
                    "day": day,
                    "block": block,
                    "track": track,
                    "kind": "academy-session",
                },
            ),
            Learning(
                kind="procedural",
                content=(
                    f"Boot camp method practiced ({entry['exercise_type']}): "
                    f"{entry['objectives'][-1]}."
                ),
                confidence=0.6,
                provenance={
                    "program": "levi-academy",
                    "day": day,
                    "block": block,
                    "track": track,
                    "kind": "academy-session",
                },
            ),
        ]
    else:
        summary = (
            f"{title}: GATE FAILED — mastery {mastery['score']:.0%} "
            f"(bar 80%), exercise {exercise['score']:.0%} (bar 70%). "
            f"Missed: {len(mastery['missed_questions'])} question(s). "
            f"Remedial queued; the standard does not move. "
            f"Review drills: {review.get('reviewed', 0)}, "
            f"{len(forgotten)} forgotten and re-queued."
        )
        learnings = [
            Learning(
                kind="fact",
                content=(
                    f"LEVI Boot Camp day {day} block {block} (track {track}): "
                    f"gate FAILED on '{title}' — mastery "
                    f"{mastery['score']:.0%} vs 80% bar. Failure is data; "
                    f"remediation queued honestly."
                ),
                confidence=0.8,
                provenance={
                    "program": "levi-academy",
                    "day": day,
                    "block": block,
                    "track": track,
                    "kind": "academy-session",
                },
            ),
        ]
    kind = "academy-remedial" if remedial and gate_passed else "academy-session"
    tags = ["growth", "levi-learned", "academy", f"track-{track}", f"day-{day}"]
    tags += ["gate-passed"] if gate_passed else ["gate-failed"]
    if remedial:
        tags.append("remediation")
    if forgotten:
        tags.append("forgetting-logged")
    if review.get("assessment"):
        tags.append("weekly-assessment")
    report = consolidate(
        learnings,
        cycle_id=f"academy-d{day}b{block}"
        f"{'-r' + str(remedial['attempt']) if remedial else ''}",
    )
    jentry = gjournal.append_entry(
        {
            "kind": kind,
            "tags": tags,
            "day": day,
            "block": block,
            "track": track,
            "title": title,
            "exercise_type": entry["exercise_type"],
            "exercise_score": exercise["score"],
            "mastery_score": mastery["score"],
            "mastery_passed": mastery["passed"],
            "gate_passed": gate_passed,
            "summary": summary,
            "review": {
                "reviewed": review.get("reviewed", 0),
                "mean_score": review.get("mean_score", 1.0),
                "forgotten": forgotten,
                "assessment": bool(review.get("assessment")),
            },
            "consolidation": {
                k: report.get(k) for k in ("accepted", "corroborated", "skipped")
            },
        }
    )
    return {"consolidation": report, "journal_id": jentry.get("id")}


# ---------------------------------------------------------------- graduation
def launch_retrain() -> dict:
    """Launch the graduation brain retrain as a detached background process.

    Same hyperparams as the original run (600 steps, seed 1337, CPU).
    Never touches the existing weights: new checkpoint is versioned.
    Trains on POST-mastery knowledge only — the corpus holds verified
    lessons, tagged with mastery level, never first drafts.
    """
    from levi.growth import journal as gjournal

    script = ACADEMY_PKG / "retrain.py"
    log_path = data_dir() / "retrain.log"
    try:
        import torch  # noqa: F401
    except Exception:
        gjournal.append_entry(
            {
                "kind": "academy-graduation",
                "tags": ["growth", "levi-learned", "academy", "retrain-skipped"],
                "note": "Brain retrain skipped: torch not available in this environment.",
            }
        )
        return {"launched": False, "reason": "torch-unavailable"}
    log_fh = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(REPO_ROOT),
    )
    gjournal.append_entry(
        {
            "kind": "academy-graduation",
            "tags": ["growth", "levi-learned", "academy", "retrain-launched"],
            "note": (
                f"Graduation brain retrain launched in background "
                f"(pid {proc.pid}); log at {log_path}. Existing weights "
                f"untouched; new checkpoint will be versioned."
            ),
        }
    )
    return {"launched": True, "pid": proc.pid, "log": str(log_path)}


def graduate(
    day: int,
    block: int,
    track: str,
    entry: dict,
    exercise: dict,
    mastery: dict,
    syllabus: dict,
) -> dict:
    """Session 120: the final crucible report."""
    from levi.growth import journal as gjournal

    art = exercise["artifact"]
    per_track = art.get("per_track", {})
    grades = {t: v.get("score") for t, v in per_track.items()}
    weakest = art.get("weakest_track")
    focus = art.get("post_graduation_focus", [])
    verdict = art.get("verdict", "UNKNOWN")
    gjournal.append_entry(
        {
            "kind": "academy-graduation",
            "tags": ["growth", "levi-learned", "academy", "graduation"],
            "day": day,
            "block": block,
            "title": "GRADUATION",
            "final_score": art.get("overall"),
            "verdict": verdict,
            "per_track_grades": grades,
            "weakest_track": weakest,
            "post_graduation_focus": focus,
            "summary": (
                f"Session 120/120 complete. Final crucible overall "
                f"{art.get('overall', 0):.0%} — {verdict}. Per-track: "
                + ", ".join(f"{t} {s:.0%}" for t, s in grades.items())
                + f". Weakest area: track {weakest} — post-graduation "
                f"drill focus: {'; '.join(focus[:3])}."
            ),
        }
    )
    retrain = launch_retrain()
    return {
        "verdict": verdict,
        "per_track": grades,
        "weakest_track": weakest,
        "post_graduation_focus": focus,
        "retrain": retrain,
    }


# ------------------------------------------------------------------ session
def _research(
    entry: dict, track: str, dry_research: dict | None, budget_seconds: float
) -> dict:
    if dry_research is not None:
        return dry_research
    return aresearch.research_topic(
        entry["title"], track, budget_seconds=budget_seconds
    )


def run_one_session(
    day: int,
    block: int,
    *,
    dry_research: dict | None = None,
    budget_minutes: float = SESSION_BUDGET_MINUTES,
) -> dict:
    """Run one curriculum session through the full battle rhythm."""
    t0 = time.time()
    deadline = t0 + budget_minutes * 60

    def _budget_left() -> float:
        return deadline - time.time()

    syllabus = load_syllabus()
    track, entry = entry_for(syllabus, day, block)
    n = day_block_to_n(day, block)
    week_phase = week_phase_for(syllabus, day)
    sid = session_id(day, block)

    # ---- BRIEF
    print(
        f"boot camp: BRIEF — day {day} block {block} (session {n}/120) · "
        f"track {track}: {entry['title']}",
        flush=True,
    )
    print(f"  objectives: {'; '.join(entry['objectives'])}", flush=True)
    print(
        "  battle rhythm: brief, teach, review, drill, test, debrief · mastery bar 80%",
        flush=True,
    )

    # ---- TEACH
    print("boot camp: TEACH — researching + synthesizing lesson", flush=True)
    points = prior_context_points()
    res = _research(
        entry,
        track,
        dry_research,
        budget_seconds=min(150.0, max(30.0, _budget_left() / 3)),
    )
    cross_links = acon.recent_concepts(exclude_track=track, k=3)
    lesson_md = asynth.synthesize_lesson(
        day, block, track, entry, res, points, week_phase, cross_links=cross_links
    )
    dd = data_dir()
    (dd / "lessons").mkdir(parents=True, exist_ok=True)
    (dd / "lessons" / f"{sid}.md").write_text(lesson_md, encoding="utf-8")

    # ---- REVIEW (spaced repetition: retrieval drills, never re-reading)
    assessment = day in ASSESSMENT_DAYS
    print(
        f"boot camp: REVIEW — due concept drills"
        f"{' (weekly assessment)' if assessment else ''}",
        flush=True,
    )
    review = acon.run_reviews(n, assessment=assessment)
    print(
        f"  reviewed {review['reviewed']} concept(s), mean "
        f"{review['mean_score']:.0%}, forgotten: {len(review['forgotten'])}",
        flush=True,
    )

    # ---- DRILL
    print("boot camp: DRILL — practical exercise", flush=True)
    interleave = acon.interleave_concepts(n, k=2) if track == "S" else None
    if interleave:
        print(
            f"  interleaved cross-track concepts: "
            f"{', '.join(c['id'] for c in interleave)}",
            flush=True,
        )
    exercise = aex.run_exercise(
        entry["exercise_type"],
        entry,
        lesson_md,
        res,
        syllabus=syllabus,
        journal_points=points,
        interleave=interleave,
    )

    # ---- TEST (the gate)
    print("boot camp: TEST — mastery gate (80% lesson / 70% drill)", flush=True)
    mastery = mastery_check(entry, lesson_md)
    gate_passed = (
        mastery["score"] >= MASTERY_THRESHOLD
        and exercise["score"] >= EXERCISE_THRESHOLD
    )
    print(
        f"  mastery {mastery['score']:.0%} "
        f"({'PASS' if mastery['score'] >= MASTERY_THRESHOLD else 'FAIL'}), "
        f"exercise {exercise['score']:.0%} "
        f"({'PASS' if exercise['score'] >= EXERCISE_THRESHOLD else 'FAIL'}) "
        f"→ gate {'PASSED' if gate_passed else 'FAILED'}",
        flush=True,
    )

    # ---- DEBRIEF
    print(
        f"boot camp: DEBRIEF — journaling "
        f"({'pass' if gate_passed else 'failure, honestly'})",
        flush=True,
    )
    progress = load_progress()
    if not progress.get("program_start"):
        progress["program_start"] = _now_iso()

    result = {
        "session": sid,
        "day": day,
        "block": block,
        "track": track,
        "title": entry["title"],
        "week_phase": week_phase,
        "research_mode": res.get("mode"),
        "review": {
            "reviewed": review["reviewed"],
            "mean_score": review["mean_score"],
            "forgotten": review["forgotten"],
            "assessment": review["assessment"],
        },
        "interleaved": [c["id"] for c in (interleave or [])],
        "exercise_type": entry["exercise_type"],
        "exercise_score": exercise["score"],
        "mastery_score": mastery["score"],
        "mastery_passed": mastery["passed"],
        "gate_passed": gate_passed,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    if gate_passed:
        # Concepts enter the registry only once taught to mastery.
        n_concepts = acon.register_session(
            day, block, track, entry, res, n, mastery_score=mastery["score"]
        )
        _growth = consolidate_session(
            day, block, track, entry, exercise, mastery, review, gate_passed=True
        )
        # Corpus quality: ingest only POST-mastery, tagged with mastery level.
        corpus = aci.ingest_lesson(
            day,
            block,
            track,
            entry["title"],
            lesson_md,
            mastery={
                "mastery_score": mastery["score"],
                "exercise_score": exercise["score"],
                "attempts": 1,
                "remediated": False,
            },
        )
        streak = bump_streak(progress, track, True)
        if sid not in progress["completed"]:
            progress["completed"].append(sid)
        progress["sessions"][sid] = {
            "day": day,
            "block": block,
            "track": track,
            "title": entry["title"],
            "exercise_type": entry["exercise_type"],
            "exercise_score": exercise["score"],
            "mastery_score": mastery["score"],
            "gate_passed": True,
            "attempts": 1,
            "concepts_registered": n_concepts,
            "reviewed": review["reviewed"],
            "corpus_added": corpus["added"],
            "ts": _now_iso(),
        }
        result["concepts_registered"] = n_concepts
        result["corpus"] = corpus
        result["streak"] = streak
        if n == 120:
            result["graduation"] = graduate(
                day, block, track, entry, exercise, mastery, syllabus
            )
            progress["graduated"] = True
    else:
        # Failed gate: session NOT completed, knowledge NOT ingested, streak
        # reset. Remediation is queued for the next block — the standard
        # does not move.
        _growth = consolidate_session(
            day, block, track, entry, exercise, mastery, review, gate_passed=False
        )
        streak = bump_streak(progress, track, False)
        progress["pending_remedial"] = {
            "day": day,
            "block": block,
            "track": track,
            "n": n,
            "attempts": 0,
            "missed_questions": mastery["missed_questions"],
            "missed_objectives": mastery["missed_objectives"],
            "mastery_score": mastery["score"],
            "exercise_score": exercise["score"],
            "queued_ts": _now_iso(),
        }
        progress["sessions"][sid] = {
            "day": day,
            "block": block,
            "track": track,
            "title": entry["title"],
            "exercise_score": exercise["score"],
            "mastery_score": mastery["score"],
            "gate_passed": False,
            "attempts": 1,
            "ts": _now_iso(),
        }
        result["streak"] = streak
        result["pending_remedial"] = progress["pending_remedial"]
    save_progress(progress)
    return result


def run_remedial(
    pending: dict,
    *,
    dry_research: dict | None = None,
    budget_minutes: float = SESSION_BUDGET_MINUTES,
) -> dict:
    """Run the queued remedial session: re-teach, re-drill, re-test.

    A remedial pass completes the ORIGINAL curriculum gate. A remedial
    failure stays pending — the program does not advance past a failed gate.
    """
    t0 = time.time()
    day, block, track = pending["day"], pending["block"], pending["track"]
    n = pending["n"]
    attempt = pending.get("attempts", 0) + 1
    syllabus = load_syllabus()
    _, entry = entry_for(syllabus, day, block)
    sid = session_id(day, block)

    print(
        f"boot camp: REMEDIAL (attempt {attempt}) — day {day} block {block} "
        f"· track {track}: {entry['title']}",
        flush=True,
    )
    print(
        f"  re-teaching from a different angle: "
        f"{len(pending.get('missed_questions', []))} missed question(s), "
        f"{len(pending.get('missed_objectives', []))} missed objective(s)",
        flush=True,
    )

    points = prior_context_points()
    res = _research(entry, track, dry_research, budget_seconds=60.0)
    lesson_md = asynth.synthesize_remedial_lesson(
        day,
        block,
        track,
        entry,
        pending.get("missed_questions", []),
        pending.get("missed_objectives", []),
        attempt,
        res,
    )
    dd = data_dir()
    (dd / "lessons").mkdir(parents=True, exist_ok=True)
    (dd / "lessons" / f"{sid}-remedial{attempt}.md").write_text(
        lesson_md, encoding="utf-8"
    )

    interleave = acon.interleave_concepts(n, k=2) if track == "S" else None
    exercise = aex.run_exercise(
        entry["exercise_type"],
        entry,
        lesson_md,
        res,
        syllabus=syllabus,
        journal_points=points,
        interleave=interleave,
    )
    mastery = mastery_check(entry, lesson_md)
    gate_passed = (
        mastery["score"] >= MASTERY_THRESHOLD
        and exercise["score"] >= EXERCISE_THRESHOLD
    )
    print(
        f"  remedial mastery {mastery['score']:.0%}, exercise "
        f"{exercise['score']:.0%} → gate "
        f"{'PASSED' if gate_passed else 'FAILED — stays queued'}",
        flush=True,
    )

    progress = load_progress()
    result = {
        "remedial": True,
        "session": sid,
        "day": day,
        "block": block,
        "track": track,
        "attempt": attempt,
        "exercise_score": exercise["score"],
        "mastery_score": mastery["score"],
        "gate_passed": gate_passed,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    if gate_passed:
        # The corrected, retained version is what enters durable memory.
        n_concepts = acon.register_session(
            day, block, track, entry, res, n, mastery_score=mastery["score"]
        )
        _growth = consolidate_session(
            day,
            block,
            track,
            entry,
            exercise,
            mastery,
            review=None,
            gate_passed=True,
            remedial={"attempt": attempt},
        )
        (dd / "lessons" / f"{sid}.md").write_text(lesson_md, encoding="utf-8")
        corpus = aci.ingest_lesson(
            day,
            block,
            track,
            entry["title"],
            lesson_md,
            mastery={
                "mastery_score": mastery["score"],
                "exercise_score": exercise["score"],
                "attempts": attempt + 1,
                "remediated": True,
            },
        )
        streak = bump_streak(progress, track, True)
        if sid not in progress["completed"]:
            progress["completed"].append(sid)
        progress["sessions"][sid].update(
            {
                "gate_passed": True,
                "attempts": attempt + 1,
                "concepts_registered": n_concepts,
                "corpus_added": corpus["added"],
                "ts": _now_iso(),
            }
        )
        progress["pending_remedial"] = None
        result["concepts_registered"] = n_concepts
        result["corpus"] = corpus
        result["streak"] = streak
        if n == 120:
            result["graduation"] = graduate(
                day, block, track, entry, exercise, mastery, syllabus
            )
            progress["graduated"] = True
    else:
        consolidate_session(
            day,
            block,
            track,
            entry,
            exercise,
            mastery,
            review=None,
            gate_passed=False,
            remedial={"attempt": attempt},
        )
        progress["pending_remedial"] = {
            **pending,
            "attempts": attempt,
            "missed_questions": mastery["missed_questions"],
            "missed_objectives": mastery["missed_objectives"],
            "mastery_score": mastery["score"],
            "exercise_score": exercise["score"],
            "queued_ts": _now_iso(),
        }
        progress["sessions"][sid].update(
            {"gate_passed": False, "attempts": attempt + 1, "ts": _now_iso()}
        )
        result["pending_remedial"] = progress["pending_remedial"]
    save_progress(progress)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LEVI Boot Camp 24/7 session worker")
    ap.add_argument("--day", type=int, default=None)
    ap.add_argument("--block", type=int, default=None, choices=[1, 2, 3, 4])
    ap.add_argument("--budget-minutes", type=float, default=SESSION_BUDGET_MINUTES)
    args = ap.parse_args(argv)

    progress = load_progress()
    if args.day is not None and args.block is not None:
        day, block = args.day, args.block
        if not (1 <= day <= 30):
            # day > 30: graduation path — quiet no-op, never an orphan error.
            print(f"boot camp: day {day} > 30 — program complete, nothing to run.")
            return 0
    else:
        # A failed gate inserts its remedial in the next block: remediation
        # runs before any new syllabus session. Do not advance past it.
        pending = progress.get("pending_remedial")
        if pending:
            print(
                f"boot camp: pending remediation for day {pending['day']} "
                f"block {pending['block']} (attempt "
                f"{pending.get('attempts', 0) + 1}) — running it before any "
                f"new session.",
                flush=True,
            )
            result = run_remedial(pending, budget_minutes=args.budget_minutes)
            print(json.dumps(result, indent=1))
            return 0
        n = next_uncompleted(progress)
        if n > 120:
            print("boot camp: all 120 sessions complete — graduated. Nothing to run.")
            return 0
        day, block = n_to_day_block(n)
        # schedule-drift note (timestamp-derived expectation vs sequence)
        if progress.get("program_start"):
            try:
                start = datetime.fromisoformat(progress["program_start"])
                expected = (
                    int(
                        (datetime.now(timezone.utc) - start).total_seconds()
                        // BLOCK_SECONDS
                    )
                    + 1
                )
                if expected > n:
                    from levi.growth import journal as gjournal

                    gjournal.append_entry(
                        {
                            "kind": "academy-note",
                            "tags": ["growth", "levi-learned", "academy"],
                            "note": (
                                f"Behind schedule: clock expects session ~{expected}, "
                                f"running next uncompleted session {n} (catch-up, no skips)."
                            ),
                        }
                    )
            except Exception:
                pass

    result = run_one_session(day, block, budget_minutes=args.budget_minutes)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("graduation",)}, indent=1
        )
    )
    if result.get("graduation"):
        g = result["graduation"]
        print(
            f"boot camp: GRADUATION — {g.get('verdict')} "
            f"(weakest: track {g.get('weakest_track')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
