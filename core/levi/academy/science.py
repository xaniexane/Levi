"""Learning science, wired into exercise formats.

Five principles from the science of learning, each an executable
instrument rather than a slogan:

- retrieval practice — free recall beats re-reading; the prompt hides
  the facts, the scoring measures what comes back unaided.
- elaboration — connect the concept outward; causal language required.
- dual coding — verbal channel plus structural/visual channel; both
  must carry weight.
- desirable difficulty — train harder than the field on purpose;
  tiers escalate guided → unassisted → degraded.
- metacognition — confidence ratings per answer, Brier-scored as a
  graded skill. Composes with the stake-under-fog drills: same
  :func:`brier_score` math
  (:mod:`levi.academy.differentiators.stakes`), different instrument.

Stdlib only. State under ``<LEVI_HOME>/academy/science/``, owner-only.
No network. Grading is pattern-based — a floor, not a human examiner.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators.stakes import brier_score


def _science_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (Path(home) if home is not None else Path(base).expanduser()) / "academy" / "science"
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
# Retrieval practice — recall, don't re-read
# ---------------------------------------------------------------------------

def create_retrieval_drill(learner_id: str, topic: str, facts: List[str],
                           home: Optional[Path] = None,
                           now: Optional[float] = None) -> Dict[str, Any]:
    """Build a free-recall drill. The prompt hides the facts; the answer key stays sealed in the record."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not topic or not topic.strip():
        raise ValueError("topic must be non-empty")
    if not facts or not isinstance(facts, list):
        raise ValueError("facts must be a non-empty list")
    facts = [str(f) for f in facts]
    if any(not f.strip() for f in facts):
        raise ValueError("facts must be non-empty strings")
    drill_id = uuid.uuid4().hex[:12]
    record = {
        "drill_id": drill_id, "learner_id": learner_id, "topic": topic,
        "facts": facts, "created_at": _utcnow(now),
    }
    _write_json(_science_dir(home) / "retrieval" / learner_id / f"{drill_id}.json", record)
    return {
        "drill_id": drill_id, "topic": topic,
        "prompt": (f"Free recall on '{topic}'. Write down everything you know "
                   f"about it — {len(facts)} key facts exist. No notes, no "
                   "peeking. Recognition is not recall."),
        "fact_count": len(facts),
    }


def _load_retrieval(learner_id: str, drill_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _science_dir(home) / "retrieval" / learner_id / f"{drill_id}.json"
    if not path.exists():
        raise KeyError(f"unknown retrieval drill {drill_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def score_recall(learner_id: str, drill_id: str, recalled_text: str,
                 home: Optional[Path] = None) -> Dict[str, Any]:
    """Score free recall: a fact counts when >= 40% of its keywords surface unaided."""
    record = _load_retrieval(learner_id, drill_id, home)
    if not isinstance(recalled_text, str) or not recalled_text.strip():
        raise ValueError("recalled_text must be non-empty")
    recalled = _words(recalled_text)
    per_fact = []
    for fact in record["facts"]:
        kw = _words(fact)
        coverage = (len(kw & recalled) / len(kw)) if kw else 1.0
        per_fact.append({"fact": fact, "coverage": round(coverage, 3),
                         "recalled": coverage >= 0.4})
    hits = sum(1 for p in per_fact if p["recalled"])
    coverage = round(hits / len(per_fact), 3) if per_fact else 0.0
    return {"drill_id": drill_id, "topic": record["topic"],
            "facts_recalled": hits, "facts_total": len(per_fact),
            "coverage": coverage, "passed": coverage >= 0.6,
            "per_fact": per_fact}


# ---------------------------------------------------------------------------
# Elaboration — connect it outward
# ---------------------------------------------------------------------------

_CAUSAL_MARKERS = ("because", "therefore", "leads to", "causes", "caused by",
                   "since", "as a result", "this means", "which means",
                   "in order to", "so that")


def elaboration_prompt(concept: str, related: str) -> Dict[str, Any]:
    """Prompt the learner to elaborate: connect concept → related, with mechanism."""
    if not concept or not concept.strip():
        raise ValueError("concept must be non-empty")
    if not related or not related.strip():
        raise ValueError("related must be non-empty")
    return {
        "concept": concept, "related": related,
        "prompt": (f"Elaborate: explain how '{concept}' connects to '{related}'. "
                   "Name the mechanism — not just that they relate, but *why* "
                   "the connection works. One paragraph, causal language."),
        "rubric": "concept named, related named, causal mechanism stated",
    }


def score_elaboration(response: str, concept: str, related: str) -> Dict[str, Any]:
    """Score elaboration: both terms present plus causal language."""
    if not isinstance(response, str) or not response.strip():
        raise ValueError("response must be non-empty")
    lowered = response.lower()
    concept_hit = concept.lower() in lowered
    related_hit = related.lower() in lowered
    causal_hit = any(m in lowered for m in _CAUSAL_MARKERS)
    checks = [("concept named", concept_hit), ("related named", related_hit),
              ("causal mechanism", causal_hit)]
    score = round(sum(1 for _, ok in checks if ok) / len(checks), 3)
    return {"score": score, "passed": score >= 2 / 3,
            "checks": [{"name": n, "passed": bool(ok)} for n, ok in checks]}


# ---------------------------------------------------------------------------
# Dual coding — two channels, both carrying weight
# ---------------------------------------------------------------------------

_CONNECTORS = ("->", "-->", "=>", "<-", "|", "+--", "`--", "[", "]", "===")


def dual_code_prompt(concept: str) -> Dict[str, Any]:
    """Prompt for dual-coded work: verbal explanation plus a structural map."""
    if not concept or not concept.strip():
        raise ValueError("concept must be non-empty")
    return {
        "concept": concept,
        "prompt": (f"Dual-code '{concept}': (1) a verbal explanation in your own "
                   "words, at least two sentences; (2) a structural map — an "
                   "ASCII diagram with labeled parts and connectors "
                   "(->, |, +--, [boxes]). The map must stand alone: a reader "
                   "should get the structure without the prose."),
        "rubric": "verbal channel substantive; diagram has >= 2 labeled nodes "
                  "joined by connectors",
    }


def score_dual_code(verbal: str, diagram: str) -> Dict[str, Any]:
    """Score dual coding: verbal substance plus a real structural diagram."""
    verbal_ok = isinstance(verbal, str) and len(verbal.strip()) >= 40
    lines = [ln for ln in str(diagram or "").splitlines() if ln.strip()]
    labeled = [ln for ln in lines
               if re.search(r"[A-Za-z]{2,}", ln)
               and any(c in ln for c in _CONNECTORS)]
    diagram_ok = len(labeled) >= 2
    checks = [("verbal channel substantive", verbal_ok),
              ("diagram has >= 2 labeled connected nodes", diagram_ok)]
    score = round(sum(1 for _, ok in checks if ok) / len(checks), 3)
    return {"score": score, "passed": verbal_ok and diagram_ok,
            "checks": [{"name": n, "passed": bool(ok)} for n, ok in checks],
            "labeled_lines": len(labeled)}


# ---------------------------------------------------------------------------
# Desirable difficulty — train harder than the field, on purpose
# ---------------------------------------------------------------------------

TIERS = ("guided", "unassisted", "degraded")

_TIER_DESCRIPTIONS = {
    "guided": "Worked example beside you: reference material open, hints allowed.",
    "unassisted": "No references, no hints — the field conditions.",
    "degraded": "Harder than the field: partial information, a twist, or a "
                "distractor. If you can do it degraded, the field feels easy.",
}


def difficulty_tiers(topic: str) -> Dict[str, Any]:
    """The three difficulty tiers for a topic, easiest first."""
    if not topic or not topic.strip():
        raise ValueError("topic must be non-empty")
    return {"topic": topic,
            "tiers": [{"tier": t, "description": _TIER_DESCRIPTIONS[t]} for t in TIERS],
            "doctrine": "train harder than the field on purpose — desirable difficulty"}


def record_tier_attempt(learner_id: str, topic: str, tier: str, passed: bool,
                        home: Optional[Path] = None,
                        now: Optional[float] = None) -> Dict[str, Any]:
    """Record one attempt at a difficulty tier."""
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    path = _science_dir(home) / "difficulty" / learner_id / "tiers.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    history = record.setdefault(topic, [])
    history.append({"tier": tier, "passed": bool(passed), "ts": _utcnow(now)})
    _write_json(path, record)
    return {"learner_id": learner_id, "topic": topic, "tier": tier,
            "passed": bool(passed), "recommended": recommend_tier(learner_id, topic, home)}


def recommend_tier(learner_id: str, topic: str,
                   home: Optional[Path] = None) -> str:
    """Recommend the next tier: two passes escalate, any fail steps down."""
    path = _science_dir(home) / "difficulty" / learner_id / "tiers.json"
    history = (json.loads(path.read_text(encoding="utf-8")).get(topic, [])
               if path.exists() else [])
    if not history:
        return "guided"
    # Walk the history: track current tier by consecutive outcomes.
    current = "guided"
    streak = 0
    for attempt in history:
        tier, ok = attempt["tier"], attempt["passed"]
        idx = TIERS.index(tier)
        if ok:
            if tier == current:
                streak += 1
            else:
                current, streak = tier, 1
            if streak >= 2 and idx < len(TIERS) - 1:
                current, streak = TIERS[idx + 1], 0
        else:
            current, streak = (TIERS[max(idx - 1, 0)], 0)
    return current


# ---------------------------------------------------------------------------
# Metacognition — calibration as a graded skill
# ---------------------------------------------------------------------------

def rate_confidence(learner_id: str, answer_id: str, confidence: float,
                    home: Optional[Path] = None,
                    now: Optional[float] = None) -> Dict[str, Any]:
    """Record a confidence rating (0..1) for an answer, before it is resolved."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not answer_id or not answer_id.strip():
        raise ValueError("answer_id must be non-empty")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be 0..1")
    path = _science_dir(home) / "metacognition" / learner_id / "ratings.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if answer_id in record and record[answer_id].get("outcome") is None:
        raise ValueError(f"answer {answer_id!r} already has an open rating")
    record[answer_id] = {"confidence": confidence, "outcome": None,
                         "rated_at": _utcnow(now)}
    _write_json(path, record)
    return {"learner_id": learner_id, "answer_id": answer_id,
            "confidence": confidence}


def resolve_answer(learner_id: str, answer_id: str, correct: bool,
                   home: Optional[Path] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """Resolve a rated answer: was the confidence earned?"""
    path = _science_dir(home) / "metacognition" / learner_id / "ratings.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if answer_id not in record:
        raise KeyError(f"no confidence rating for answer {answer_id!r}")
    if record[answer_id]["outcome"] is not None:
        raise ValueError(f"answer {answer_id!r} is already resolved")
    record[answer_id]["outcome"] = 1 if bool(correct) else 0
    record[answer_id]["resolved_at"] = _utcnow(now)
    _write_json(path, record)
    return {"learner_id": learner_id, "answer_id": answer_id,
            "confidence": record[answer_id]["confidence"],
            "correct": bool(correct)}


def metacognition_report(learner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Grade calibration as a skill: Brier score mapped to a letter grade.

    Same Brier math as the stake-under-fog drills — calibration is one
    skill with two instruments.
    """
    path = _science_dir(home) / "metacognition" / learner_id / "ratings.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    events = [{"confidence": r["confidence"], "outcome": r["outcome"]}
              for r in record.values() if r["outcome"] is not None]
    brier = brier_score(events)
    if brier is None:
        return {"learner_id": learner_id, "n": 0, "brier": None,
                "grade": None, "label": "no resolved ratings yet"}
    if brier <= 0.10:
        grade = "A"
    elif brier <= 0.16:
        grade = "B"
    elif brier <= 0.25:
        grade = "C"
    elif brier <= 0.35:
        grade = "D"
    else:
        grade = "F"
    return {"learner_id": learner_id, "n": len(events), "brier": brier,
            "grade": grade,
            "label": f"calibration grade {grade} — "
                     f"{'knows what they know' if grade in 'AB' else 'confidence needs work'}"}
