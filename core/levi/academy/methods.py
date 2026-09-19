"""Boot camp methods — how the academy teaches, not just what.

Six methods, each a deterministic, hermetic instrument:

- spaced repetition — reviews scheduled just before forgetting,
  layered on the decay model (:mod:`levi.academy.differentiators.decay`).
- interleaving — mixed-subject sessions, round-robin, never blocked chapters.
- Feynman drills — the trainee teaches it back; the explanation is graded
  on key-point coverage.
- shadow mode — shadow a graduate's live work, then take over mid-task
  through the nursery workload router.
- pressure drills — incident response under a real clock; overtime fails.
- Socratic interrogation — cross-examine reasoning, not recall, with
  deterministic question templates.

Failures in shadow mode and pressure drills auto-compost into
remediation drills (:mod:`levi.academy.differentiators.compost`).

Stdlib only. State under ``<LEVI_HOME>/academy/methods/``, owner-only.
No network. Honest limits are stated per method: grading is
pattern-based coverage, a floor — not a human examiner.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import compost as _compost
from levi.academy.differentiators import decay as _decay
from levi.academy.differentiators import receipts as _receipts


def _methods_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (Path(home) if home is not None else Path(base).expanduser()) / "academy" / "methods"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _words(text: str) -> set:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


# ---------------------------------------------------------------------------
# Spaced repetition — layered on the decay model
# ---------------------------------------------------------------------------

def next_review(learner_id: str, skill_id: str, threshold: float = 0.8,
                home: Optional[Path] = None,
                now: Optional[float] = None) -> Dict[str, Any]:
    """When to review a skill so the review lands just before forgetting.

    The decay model gives strength = 0.5^(days/30); solving for the day
    strength would cross ``threshold`` yields
    ``days = 30 * log2(1/threshold)``. A skill already below threshold
    (or never touched) is due now.
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be in (0, 1)")
    ts = now if now is not None else time.time()
    current = _decay.skill_strength(learner_id, skill_id, home=home, now=ts)
    if current < threshold:
        review_in_days = 0.0
        note = "due now — unseen or already decayed below threshold"
    else:
        review_in_days = round(_decay.HALF_LIFE_DAYS * math.log2(1.0 / threshold), 2)
        note = "scheduled just before the strength would cross threshold"
    review_at = ts + review_in_days * 86400.0
    return {
        "learner_id": learner_id,
        "skill_id": skill_id,
        "current_strength": current,
        "threshold": threshold,
        "review_in_days": review_in_days,
        "review_at": review_at,
        "review_on": time.strftime("%Y-%m-%d", time.gmtime(review_at)),
        "note": note,
    }


# ---------------------------------------------------------------------------
# Interleaving — mixed subjects per session
# ---------------------------------------------------------------------------

def interleave(subjects: List[Dict[str, Any]], per_subject: int = 2) -> List[Dict[str, Any]]:
    """Round-robin interleave of subject items into one mixed session.

    ``subjects``: [{"subject_id": str, "items": [str, ...]}, ...].
    Blocked chapters are the enemy; the session alternates subjects so
    the learner practices *choosing* the right tool, not just using it.
    """
    if not subjects or not isinstance(subjects, list):
        raise ValueError("subjects must be a non-empty list")
    if per_subject < 1:
        raise ValueError("per_subject must be >= 1")
    queues = []
    for i, s in enumerate(subjects):
        if not isinstance(s, dict) or "subject_id" not in s or "items" not in s:
            raise ValueError(f"subjects[{i}] needs 'subject_id' and 'items'")
        items = list(s["items"])[:per_subject]
        if not items:
            raise ValueError(f"subjects[{i}] has no items")
        queues.append((str(s["subject_id"]), items))
    out: List[Dict[str, Any]] = []
    position = 0
    active = True
    while active:
        active = False
        for subject_id, items in queues:
            if items:
                out.append({"position": position, "subject_id": subject_id,
                            "item": items.pop(0)})
                position += 1
                active = True
    return out


# ---------------------------------------------------------------------------
# Feynman drills — teach it back
# ---------------------------------------------------------------------------

def feynman_drill(topic: str, key_points: List[str]) -> Dict[str, Any]:
    """Build a Feynman drill: explain the topic simply, covering each key point."""
    if not topic or not topic.strip():
        raise ValueError("topic must be non-empty")
    if not key_points or not isinstance(key_points, list):
        raise ValueError("key_points must be a non-empty list")
    points = [str(kp) for kp in key_points]
    return {
        "topic": topic,
        "prompt": (
            f"Teach '{topic}' back as if to a smart newcomer. No jargon "
            "without defining it. Your explanation must cover each key point: "
            + "; ".join(f"({i+1}) {kp}" for i, kp in enumerate(points)) + "."
        ),
        "key_points": points,
        "rubric": "each key point needs >= 50% word coverage; overall >= 60% to pass",
    }


def grade_explanation(explanation: str, key_points: List[str]) -> Dict[str, Any]:
    """Grade a Feynman explanation by key-point word coverage.

    Pattern-based floor: measures whether the vocabulary of each key
    point shows up, not whether the reasoning is sound.
    """
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("explanation must be non-empty")
    exp_words = _words(explanation)
    per_point = []
    for kp in key_points:
        kp_words = _words(str(kp))
        coverage = (len(kp_words & exp_words) / len(kp_words)) if kp_words else 1.0
        per_point.append({"key_point": str(kp), "coverage": round(coverage, 3),
                          "passed": coverage >= 0.5})
    overall = round(sum(p["coverage"] for p in per_point) / len(per_point), 3) if per_point else 0.0
    passed = overall >= 0.6 and all(p["passed"] for p in per_point)
    return {"score": overall, "passed": passed, "per_point": per_point,
            "note": "coverage-graded; a human examiner would judge the reasoning"}


# ---------------------------------------------------------------------------
# Shadow mode — observe, then take over mid-task
# ---------------------------------------------------------------------------

SHADOW_TASK = "sort_lines"


def _shadow_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _methods_dir(home) / "shadow" / learner_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def shadow_assignment(learner_id: str, graduate_ref: str,
                      task_kind: str = SHADOW_TASK,
                      home: Optional[Path] = None,
                      now: Optional[float] = None) -> Dict[str, Any]:
    """Begin shadowing a graduate's live work. Phase 1: observe."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not graduate_ref or not graduate_ref.strip():
        raise ValueError("graduate_ref must be non-empty")
    shadow_id = uuid.uuid4().hex[:12]
    record = {
        "shadow_id": shadow_id, "learner_id": learner_id,
        "graduate_ref": graduate_ref, "task_kind": task_kind,
        "phase": "observing", "observation_notes": "",
        "assigned_at": _utcnow(now), "takeover_at": "", "error": "",
        "receipt_id": "",
    }
    _write_json(_shadow_dir(learner_id, home) / f"{shadow_id}.json", record)
    return {"shadow_id": shadow_id, "learner_id": learner_id,
            "phase": "observing", "task_kind": task_kind}


def _load_shadow(learner_id: str, shadow_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _shadow_dir(learner_id, home) / f"{shadow_id}.json"
    if not path.exists():
        raise KeyError(f"unknown shadow {shadow_id!r} for learner {learner_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def complete_observation(learner_id: str, shadow_id: str, notes: str,
                         home: Optional[Path] = None,
                         now: Optional[float] = None) -> Dict[str, Any]:
    """Finish the observe phase with notes. Unlocks the takeover."""
    record = _load_shadow(learner_id, shadow_id, home)
    if record["phase"] != "observing":
        raise ValueError(f"shadow {shadow_id!r} is in phase {record['phase']!r}")
    if not isinstance(notes, str) or len(notes.strip()) < 20:
        raise ValueError("observation notes must be at least 20 characters — "
                         "watch closely, then write what you saw")
    record["phase"] = "ready_for_takeover"
    record["observation_notes"] = notes.strip()
    _write_json(_shadow_dir(learner_id, home) / f"{shadow_id}.json", record)
    return {"shadow_id": shadow_id, "phase": "ready_for_takeover"}


def takeover(learner_id: str, shadow_id: str, payload: Dict[str, Any],
             home: Optional[Path] = None,
             now: Optional[float] = None) -> Dict[str, Any]:
    """Take over mid-task: run the supervised nursery-router task yourself.

    A verified result passes and mints a sealed receipt; a failure is
    recorded and auto-composted into a remediation drill.
    """
    from levi.nursery.router import Refusal, VerificationFailure, execute_task

    record = _load_shadow(learner_id, shadow_id, home)
    if record["phase"] != "ready_for_takeover":
        raise ValueError(f"shadow {shadow_id!r} is in phase {record['phase']!r} — "
                         "complete the observation first")
    try:
        executed = execute_task(record["task_kind"], payload)
    except (Refusal, VerificationFailure) as exc:
        record["phase"] = "takeover_failed"
        record["takeover_at"] = _utcnow(now)
        record["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(_shadow_dir(learner_id, home) / f"{shadow_id}.json", record)
        drill = _compost.compost_failure(
            learner_id, "shadow-mode", shadow_id,
            [{"name": record["task_kind"],
              "hint": f"Takeover failed: {exc}. Re-study the task contract."}],
            home=home, now=now)
        return {"shadow_id": shadow_id, "phase": "takeover_failed",
                "error": record["error"], "compost_drill_id": drill["drill_id"]}
    record["phase"] = "takeover_passed"
    record["takeover_at"] = _utcnow(now)
    receipt = _receipts.mint_receipt(
        learner_id, "shadow-mode", 1.0,
        [{"name": f"takeover {record['task_kind']}", "passed": True}],
        home=home, now=now)
    record["receipt_id"] = receipt["receipt_id"]
    _write_json(_shadow_dir(learner_id, home) / f"{shadow_id}.json", record)
    return {"shadow_id": shadow_id, "phase": "takeover_passed",
            "detail": executed.get("detail", ""),
            "receipt_id": receipt["receipt_id"]}


# ---------------------------------------------------------------------------
# Pressure drills — incident response under a real clock
# ---------------------------------------------------------------------------

def _pressure_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _methods_dir(home) / "pressure" / learner_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def pressure_drill(scenario_id: str, prompt: str, time_limit_s: float,
                   expected_keywords: List[str],
                   home: Optional[Path] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """Create a timed pressure drill. The clock is real; overtime fails."""
    if not scenario_id or not scenario_id.strip():
        raise ValueError("scenario_id must be non-empty")
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be non-empty")
    time_limit_s = float(time_limit_s)
    if time_limit_s <= 0:
        raise ValueError("time_limit_s must be positive")
    if not expected_keywords or not isinstance(expected_keywords, list):
        raise ValueError("expected_keywords must be a non-empty list")
    drill_id = uuid.uuid4().hex[:12]
    record = {
        "drill_id": drill_id, "scenario_id": scenario_id, "prompt": prompt,
        "time_limit_s": time_limit_s,
        "expected_keywords": [str(k).lower() for k in expected_keywords],
        "status": "open", "created_at": _utcnow(now),
    }
    _write_json(_pressure_dir("__bank__", home) / f"{drill_id}.json", record)
    return {"drill_id": drill_id, "scenario_id": scenario_id,
            "prompt": prompt, "time_limit_s": time_limit_s, "status": "open"}


def _load_pressure(drill_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _methods_dir(home) / "pressure" / "__bank__" / f"{drill_id}.json"
    if not path.exists():
        raise KeyError(f"unknown pressure drill {drill_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def submit_pressure(learner_id: str, drill_id: str, answer: str,
                    elapsed_s: float, home: Optional[Path] = None,
                    now: Optional[float] = None) -> Dict[str, Any]:
    """Submit a pressure-drill answer. Correct AND on time passes.

    A miss — wrong or overtime — auto-composts into a remediation drill.
    """
    record = _load_pressure(drill_id, home)
    elapsed_s = float(elapsed_s)
    if elapsed_s < 0:
        raise ValueError("elapsed_s cannot be negative")
    on_time = elapsed_s <= record["time_limit_s"]
    answer_words = _words(str(answer or ""))
    keywords = record["expected_keywords"]
    hits = sum(1 for k in keywords if k in answer_words or
               any(k in w for w in answer_words))
    coverage = hits / len(keywords) if keywords else 0.0
    correct = coverage >= 0.5
    passed = correct and on_time
    result: Dict[str, Any] = {
        "drill_id": drill_id, "scenario_id": record["scenario_id"],
        "elapsed_s": elapsed_s, "time_limit_s": record["time_limit_s"],
        "on_time": on_time, "coverage": round(coverage, 3),
        "passed": passed,
    }
    if not passed:
        reason = ("overtime — the clock is part of the test"
                  if not on_time else "missed the expected response elements")
        result["reason"] = reason
        drill = _compost.compost_failure(
            learner_id, "pressure-drills", record["scenario_id"],
            [{"name": f"pressure:{record['scenario_id']}",
              "hint": f"{reason}. Expected elements: "
                      f"{', '.join(record['expected_keywords'])}."}],
            home=home, now=now)
        result["compost_drill_id"] = drill["drill_id"]
    return result


# ---------------------------------------------------------------------------
# Socratic interrogation — cross-examine reasoning, not recall
# ---------------------------------------------------------------------------

_SOCRATIC_TEMPLATES = [
    "Define your terms: what exactly do you mean by '{claim}'?",
    "Steelman the opposite: what is the strongest case against '{claim}'?",
    "What evidence would change your mind about '{claim}'?",
    "Edge case: where does '{claim}' break down?",
    "Hidden assumption: what must be true for '{claim}' to hold?",
]

_SOCRATIC_STOPWORDS = {
    "what", "why", "how", "the", "a", "an", "of", "to", "in", "is", "it",
    "you", "your", "do", "does", "and", "or", "for", "would", "what",
    "by", "be", "are", "as", "at", "on",
}


def interrogate(topic: str, claims: List[str]) -> Dict[str, Any]:
    """Generate a Socratic cross-examination: 5 questions per claim."""
    if not topic or not topic.strip():
        raise ValueError("topic must be non-empty")
    if not claims or not isinstance(claims, list):
        raise ValueError("claims must be a non-empty list")
    rounds = []
    for claim in claims:
        claim = str(claim)
        if not claim.strip():
            raise ValueError("claims must be non-empty strings")
        for template in _SOCRATIC_TEMPLATES:
            rounds.append({"claim": claim,
                           "question": template.format(claim=claim)})
    return {"topic": topic, "claims": [str(c) for c in claims], "rounds": rounds,
            "note": "answer the reasoning, not the recall — 'I don't know' "
                    "is an honorable answer, evasion is not"}


def grade_cross_examination(question: str, response: str) -> Dict[str, Any]:
    """Grade one Socratic round: does the response engage the question?

    Pattern-based floor — keyword engagement plus substance length.
    """
    if not isinstance(response, str) or not response.strip():
        raise ValueError("response must be non-empty")
    q_words = _words(str(question)) - _SOCRATIC_STOPWORDS
    r_words = _words(response)
    coverage = (len(q_words & r_words) / len(q_words)) if q_words else 1.0
    substantive = len(response.strip()) >= 40
    score = round(0.7 * coverage + 0.3 * (1.0 if substantive else 0.0), 3)
    passed = coverage >= 0.4 and substantive
    return {"score": score, "passed": passed,
            "keyword_coverage": round(coverage, 3), "substantive": substantive,
            "note": "engagement-graded; a human examiner would judge the argument"}
