"""Stake-under-fog drills — put reputation where your answer is.

The learner stakes reputation points on an answer BEFORE the reveal.
A right answer with a big stake beats a right answer with a shrug;
a wrong answer with a big stake costs. Scoring is by calibration,
not just correctness: the stake is an implicit confidence claim
(``stake / 100``), and the calibration report tracks the Brier score
of those claims over time.

Mandella lineage: stake under fog. The fog is the unrevealed answer;
the stake is the learner's honest confidence, priced in points.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import _seal

START_BALANCE = 100
MAX_STAKE = 100


def _stakes_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "stakes" / learner_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
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


def _state_path(learner_id: str, home: Optional[Path] = None) -> Path:
    return _stakes_dir(learner_id, home) / "state.json"


def _load_state(learner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    p = _state_path(learner_id, home)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"learner_id": learner_id, "balance": START_BALANCE,
            "open_stakes": {}, "calibration": []}


def _save_state(state: Dict[str, Any], learner_id: str, home: Optional[Path] = None) -> None:
    _write_json(_state_path(learner_id, home), state)


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def balance(learner_id: str, home: Optional[Path] = None) -> int:
    return int(_load_state(learner_id, home)["balance"])


def place_stake(
    learner_id: str,
    drill_id: str,
    question_id: str,
    answer: str,
    stake: int,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Stake points on an answer before the reveal. Deducts the stake."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    stake = int(stake)
    state = _load_state(learner_id, home)
    key = f"{drill_id}:{question_id}"
    if key in state["open_stakes"]:
        raise ValueError(f"question {question_id!r} already has an open stake — reveal it first")
    if stake < 1:
        raise ValueError("stake must be at least 1 point")
    if stake > MAX_STAKE:
        raise ValueError(f"stake may not exceed {MAX_STAKE} points")
    if stake > state["balance"]:
        raise ValueError(
            f"stake {stake} exceeds balance {state['balance']} — stake what you have")
    state["balance"] -= stake
    state["open_stakes"][key] = {
        "drill_id": drill_id, "question_id": question_id,
        "answer": str(answer), "stake": stake, "placed_at": _utcnow(now),
    }
    _save_state(state, learner_id, home)
    return {"learner_id": learner_id, "question_id": question_id, "stake": stake,
            "balance": state["balance"],
            "implicit_confidence": round(stake / MAX_STAKE, 3)}


def reveal(
    learner_id: str,
    drill_id: str,
    question_id: str,
    correct: bool,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Reveal the answer. Correct: stake back plus equal reward. Wrong: stake lost."""
    state = _load_state(learner_id, home)
    key = f"{drill_id}:{question_id}"
    if key not in state["open_stakes"]:
        raise KeyError(f"no open stake for question {question_id!r}")
    open_stake = state["open_stakes"].pop(key)
    stake = open_stake["stake"]
    correct = bool(correct)
    payout = 2 * stake if correct else 0
    state["balance"] += payout
    confidence = stake / MAX_STAKE
    state["calibration"].append({
        "question_id": question_id, "confidence": round(confidence, 3),
        "outcome": 1 if correct else 0, "revealed_at": _utcnow(now),
    })
    _save_state(state, learner_id, home)
    return {"learner_id": learner_id, "question_id": question_id,
            "correct": correct, "stake": stake, "payout": payout,
            "balance": state["balance"]}


def brier_score(events) -> "float | None":
    """Mean squared error of (confidence, outcome) pairs. None when empty.

    Shared by stake-under-fog drills and metacognition scoring — one
    math, two instruments.
    """
    events = list(events)
    if not events:
        return None
    return round(
        sum((float(e["confidence"]) - float(e["outcome"])) ** 2 for e in events)
        / len(events),
        3,
    )


def calibration_report(learner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Brier-scored calibration of the learner's stake-confidence claims."""
    events = _load_state(learner_id, home)["calibration"]
    brier = brier_score(events)
    if brier is None:
        return {"learner_id": learner_id, "n": 0, "brier": None,
                "label": "no data — stake something first"}
    if brier < 0.10:
        label = "well calibrated — stakes match outcomes"
    elif brier < 0.20:
        label = "roughly calibrated"
    else:
        label = "poorly calibrated — stakes do not match outcomes"
    return {"learner_id": learner_id, "n": len(events), "brier": brier, "label": label}
