"""SUNDER — a working method for multi-step problems. **PROVISIONAL NAME.**

Status: PROPOSED, not canon. The name "SUNDER" (to break a problem apart
deliberately, phase by phase) is a working title only. Every name, phase
label, and threshold in this module is provisional and awaits Chauncey's
word. Essences only: no canon declarations, no sealed identities, no
borrowed names.

REVERSE — what the absorbed source gets wrong (the IDEAL critique):

The source framework (Identify, Define, Explore, Act, Look back) is a
real, honest scaffold, but it has four structural gaps:

1. No failure loop. A wrong attempt is discarded; its information dies
   with it. Nothing is composted, so the same mistake can be made twice
   at full price.
2. No provenance. Attempts carry no record of *why* they were tried,
   what they assumed, or what they taught. "Look back" inspects the
   outcome, never the trail.
3. Assumes working memory holds the plan. The whole breakdown lives in
   the learner's head; there is no external ledger, so a long chain
   degrades silently.
4. "Look back" is a single pass with no promotion path. A lesson learned
   twice is not distinguished from a lesson learned once; nothing ever
   graduates into a reusable procedure.

IMPROVE — what SUNDER adds (the LEVI-native deltas):

(a) Failure composting (REIM-style): every failed attempt becomes a
    fingerprinted compost record. Same failure twice yields the same
    fingerprint — recognized, not re-paid.
(b) Lesson promotion (RIEM-style): a pattern that succeeds in two or
    more *distinct* sessions is promoted to a reusable procedure. One
    success is anecdote; two is corroboration.
(c) Provenance ledger: every attempt is hash-chained into an
    append-only ledger — what was tried, why, what it taught. The trail
    is the work.
(d) Define-done gate: acceptance criteria are declared in UNPACK, and
    the DO phase cannot begin without them. The finish line is drawn
    before the race starts.

LAWS (invariants — stated here, enforced in code, proved in tests):

1. GATE: no attempt may be recorded before acceptance criteria exist.
   The DO phase is unreachable without a completed UNPACK.
2. COMPOST-IDENTITY: the same failed attempt always yields the same
   fingerprint; the compost store is keyed by fingerprint, so a repeat
   failure is recognized, never duplicated.
3. APPEND-ONLY LEDGER: no public function edits or deletes a ledger
   entry. Entries are hash-chained (each carries the hash of the
   previous); the chain is verifiable end to end.
4. PROMOTION THRESHOLD: a pattern is promoted only when corroborated by
   >= 2 distinct sessions. A single success never promotes.
5. CRITERIA VERDICT: EMBED judges the result against the declared
   acceptance criteria by word coverage. A miss yields "unresolved" and
   composts the final state — it never yields "resolved" by assertion.
6. PHASE ORDER: phases advance Survey -> Unpack -> Navigate -> Do ->
   Embed -> Return. No phase may be entered out of order.

Honest limits: acceptance-criteria checking is word-coverage, a floor
borrowed from :mod:`levi.academy.methods` — it measures whether the
vocabulary of "done" shows up, not whether the reasoning is sound.
Promoted patterns are coarse (strategy + step kind), not deep procedural
extraction. Compost hints are template-generated, not pedagogy.

Stdlib only. State under ``<LEVI_HOME>/academy/problem_breakdown/``,
owner-only. No network.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Laws, restated as data so tests can enumerate them.
INVARIANTS = (
    "GATE: do_attempt is unreachable before acceptance criteria are declared",
    "COMPOST-IDENTITY: identical failures share one fingerprint; no duplicates",
    "APPEND-ONLY LEDGER: entries are never edited or deleted; hash-chained",
    "PROMOTION THRESHOLD: promotion requires >= 2 distinct corroborating sessions",
    "CRITERIA VERDICT: embed judges the result against declared criteria only",
    "PHASE ORDER: survey -> unpack -> navigate -> do -> embed -> return",
)

_PHASES = ("survey", "unpack", "navigate", "do", "embed", "return")

# Coverage floor shared with levi.academy.methods' honest grading.
_PER_CRITERION_FLOOR = 0.5
_OVERALL_FLOOR = 0.6
_PROMOTION_SESSIONS = 2


def _base_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (
        (Path(home) if home is not None else Path(base).expanduser())
        / "academy"
        / "problem_breakdown"
    )
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _learner_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _base_dir(home) / learner_id
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


def _fingerprint(payload: Dict[str, Any]) -> str:
    """Deterministic sha256 over the canonical JSON form."""
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _words(text: str) -> set:
    import re

    return set(re.findall(r"[a-z]{3,}", text.lower()))


def _require_nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def open_session(
    learner_id: str,
    problem_statement: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Open a SUNDER session. Phase: survey."""
    learner_id = _require_nonempty(learner_id, "learner_id")
    problem_statement = _require_nonempty(problem_statement, "problem_statement")
    session_id = uuid.uuid4().hex[:12]
    record = {
        "session_id": session_id,
        "learner_id": learner_id,
        "problem": problem_statement,
        "phase": "survey",
        "restatement": "",
        "knowns": [],
        "unknowns": [],
        "sub_questions": [],
        "variables": {},
        "acceptance_criteria": [],
        "strategies": [],
        "chosen_strategy": "",
        "ledger": [],
        "verdict": "",
        "opened_at": _utcnow(now),
        "sealed_at": "",
    }
    _write_json(_learner_dir(learner_id, home) / f"{session_id}.json", record)
    return {"session_id": session_id, "learner_id": learner_id, "phase": "survey"}


def _load(
    learner_id: str, session_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    path = _learner_dir(learner_id, home) / f"{session_id}.json"
    if not path.exists():
        raise KeyError(
            f"unknown sunder session {session_id!r} for learner {learner_id!r}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _save(record: Dict[str, Any], home: Optional[Path] = None) -> None:
    _write_json(
        _learner_dir(record["learner_id"], home) / f"{record['session_id']}.json",
        record,
    )


def _require_phase(record: Dict[str, Any], expected: str) -> None:
    """LAW 6 (PHASE ORDER): phases advance in fixed order, never skipped."""
    if record["phase"] != expected:
        raise ValueError(
            f"session {record['session_id']!r} is in phase {record['phase']!r}; "
            f"expected {expected!r} — phases run survey -> unpack -> navigate "
            "-> do -> embed -> return"
        )
    if record.get("sealed_at"):
        raise ValueError(f"session {record['session_id']!r} is sealed")


def survey(
    session_id: str,
    learner_id: str,
    restatement: str,
    knowns: List[str],
    unknowns: List[str],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """SURVEY: say the problem back in your own words; split knowns/unknowns."""
    record = _load(learner_id, session_id, home)
    _require_phase(record, "survey")
    record["restatement"] = _require_nonempty(restatement, "restatement")
    record["knowns"] = [str(k) for k in knowns or []]
    record["unknowns"] = [str(u) for u in unknowns or []]
    if not record["unknowns"]:
        raise ValueError("unknowns must be non-empty — name what you do not know")
    record["phase"] = "unpack"
    _save(record, home)
    return {"session_id": session_id, "phase": "unpack"}


def unpack(
    session_id: str,
    learner_id: str,
    sub_questions: List[str],
    variables: Dict[str, str],
    acceptance_criteria: List[str],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """UNPACK: enumerate sub-questions, name variables, declare done.

    LAW 1 (GATE): acceptance_criteria must be non-empty. The DO phase is
    unreachable without them — the finish line is drawn before the race.
    """
    record = _load(learner_id, session_id, home)
    _require_phase(record, "unpack")
    if not sub_questions or not isinstance(sub_questions, list):
        raise ValueError("sub_questions must be a non-empty list")
    if not isinstance(variables, dict) or not variables:
        raise ValueError("variables must be a non-empty dict")
    criteria = [str(c).strip() for c in (acceptance_criteria or []) if str(c).strip()]
    if not criteria:
        raise ValueError(
            "acceptance_criteria must be non-empty — define done before acting"
        )
    record["sub_questions"] = [str(q) for q in sub_questions]
    record["variables"] = {str(k): str(v) for k, v in variables.items()}
    record["acceptance_criteria"] = criteria
    record["phase"] = "navigate"
    _save(record, home)
    return {
        "session_id": session_id,
        "phase": "navigate",
        "acceptance_criteria": criteria,
    }


def navigate(
    session_id: str,
    learner_id: str,
    strategies: List[Dict[str, str]],
    chosen_index: int = 0,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """NAVIGATE: propose strategies, each with provenance (why/assumes/risks).

    Runners-up are kept on the record — no discarded knowledge.
    """
    record = _load(learner_id, session_id, home)
    _require_phase(record, "navigate")
    if not strategies or not isinstance(strategies, list):
        raise ValueError("strategies must be a non-empty list")
    cleaned = []
    for i, s in enumerate(strategies):
        if not isinstance(s, dict):
            raise ValueError(f"strategies[{i}] must be a dict")
        name = _require_nonempty(s.get("name", ""), f"strategies[{i}].name")
        cleaned.append(
            {
                "name": name,
                "why": str(s.get("why", "")).strip(),
                "assumes": str(s.get("assumes", "")).strip(),
                "risks": str(s.get("risks", "")).strip(),
            }
        )
        if not cleaned[-1]["why"]:
            raise ValueError(
                f"strategies[{i}].why must be non-empty — provenance is not optional"
            )
    if not 0 <= int(chosen_index) < len(cleaned):
        raise ValueError("chosen_index out of range")
    record["strategies"] = cleaned
    record["chosen_strategy"] = cleaned[int(chosen_index)]["name"]
    record["phase"] = "do"
    _save(record, home)
    return {
        "session_id": session_id,
        "phase": "do",
        "chosen_strategy": record["chosen_strategy"],
        "alternatives": [
            s["name"] for j, s in enumerate(cleaned) if j != int(chosen_index)
        ],
    }


# ---------------------------------------------------------------------------
# DO — attempts, provenance ledger, compost
# ---------------------------------------------------------------------------


def _ledger_hash(entry: Dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return _fingerprint(body)


def do_attempt(
    session_id: str,
    learner_id: str,
    attempt: Dict[str, Any],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """DO: record one attempt against the chosen strategy.

    ``attempt``: {"sub_step": str, "detail": str, "outcome": "pass"|"fail",
    "taught": str (what this attempt taught, even in failure)}.

    LAW 1 (GATE): unreachable before acceptance criteria exist (the phase
    machine guarantees it; re-checked here). LAW 3 (APPEND-ONLY): the
    entry is hash-chained onto the ledger, never edited. LAW 2: a failed
    attempt is composted under its fingerprint — a repeat is recognized,
    not duplicated.
    """
    record = _load(learner_id, session_id, home)
    _require_phase(record, "do")
    if not record["acceptance_criteria"]:
        raise ValueError(
            "define-done gate: acceptance criteria missing — "
            "unpack must declare done before any attempt"
        )
    if not isinstance(attempt, dict):
        raise ValueError("attempt must be a dict")
    sub_step = _require_nonempty(attempt.get("sub_step", ""), "attempt.sub_step")
    detail = _require_nonempty(attempt.get("detail", ""), "attempt.detail")
    outcome = attempt.get("outcome", "")
    if outcome not in ("pass", "fail"):
        raise ValueError('attempt.outcome must be "pass" or "fail"')
    taught = str(attempt.get("taught", "")).strip()

    # Fingerprint covers the attempt content, not the session: the same
    # learner failing the same way twice is recognized, not re-paid.
    # (The session trail stays complete because every attempt is still
    # appended to the ledger — LAW 3. Only the compost is deduplicated.)
    payload = {
        "learner_id": learner_id,
        "strategy": record["chosen_strategy"],
        "sub_step": sub_step,
        "detail": detail,
        "outcome": outcome,
    }
    fingerprint = _fingerprint(payload)
    prev_hash = record["ledger"][-1]["hash"] if record["ledger"] else "GENESIS"
    entry = {
        "seq": len(record["ledger"]),
        "at": _utcnow(now),
        "kind": "attempt",
        "strategy": record["chosen_strategy"],
        "sub_step": sub_step,
        "detail": detail,
        "outcome": outcome,
        "taught": taught,
        "fingerprint": fingerprint,
        "prev_hash": prev_hash,
    }
    entry["hash"] = _ledger_hash(entry)
    record["ledger"].append(entry)

    composted = None
    if outcome == "fail":
        composted = _compost_attempt(learner_id, session_id, entry, home, now)
    _save(record, home)
    return {
        "session_id": session_id,
        "phase": "do",
        "outcome": outcome,
        "fingerprint": fingerprint,
        "ledger_seq": entry["seq"],
        "composted": composted,
    }


def _compost_attempt(
    learner_id: str,
    session_id: str,
    entry: Dict[str, Any],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """LAW 2 (COMPOST-IDENTITY): key the compost by fingerprint.

    The same failure twice returns the existing record with an incremented
    sighting count — recognized, not re-paid.
    """
    d = _base_dir(home) / "__compost__"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    path = d / f"{entry['fingerprint']}.json"
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        record["seen_count"] = int(record.get("seen_count", 1)) + 1
        if session_id not in record["sessions"]:
            record["sessions"].append(session_id)
        _write_json(path, record)
        return {
            "fingerprint": entry["fingerprint"],
            "recognized": True,
            "seen_count": record["seen_count"],
        }
    record = {
        "fingerprint": entry["fingerprint"],
        "learner_id": learner_id,
        "sessions": [session_id],
        "strategy": entry["strategy"],
        "sub_step": entry["sub_step"],
        "detail": entry["detail"],
        "taught": entry.get("taught", ""),
        "drill": (
            f"Remediation for failed step '{entry['sub_step']}' under "
            f"strategy '{entry['strategy']}': {entry['detail']} "
            "Re-attempt on fresh material, then state the rule that would "
            "have prevented the failure. It passes when the same check "
            "would pass on new material."
        ),
        "seen_count": 1,
        "first_seen": _utcnow(now),
    }
    _write_json(path, record)
    return {"fingerprint": entry["fingerprint"], "recognized": False, "seen_count": 1}


def verify_ledger(
    learner_id: str, session_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Verify the ledger's hash chain end to end. LAW 3, checkable."""
    record = _load(learner_id, session_id, home)
    prev = "GENESIS"
    for entry in record["ledger"]:
        if entry["prev_hash"] != prev:
            return {
                "ok": False,
                "broken_at": entry["seq"],
                "reason": "prev_hash mismatch",
            }
        if entry["hash"] != _ledger_hash(entry):
            return {
                "ok": False,
                "broken_at": entry["seq"],
                "reason": "entry hash mismatch",
            }
        prev = entry["hash"]
    return {"ok": True, "entries": len(record["ledger"]), "tip": prev}


# ---------------------------------------------------------------------------
# EMBED — criteria verdict + promotion
# ---------------------------------------------------------------------------


def _coverage(text: str, criterion: str) -> float:
    c_words = _words(criterion)
    if not c_words:
        return 1.0
    t_words = _words(text)
    return len(c_words & t_words) / len(c_words)


def embed(
    session_id: str,
    learner_id: str,
    result_summary: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """EMBED: judge the result against the declared acceptance criteria.

    LAW 5 (CRITERIA VERDICT): "resolved" only when every criterion meets
    the word-coverage floor; otherwise "unresolved" and the final state
    is composted. Passing patterns are corroborated toward promotion.
    """
    record = _load(learner_id, session_id, home)
    _require_phase(record, "do")
    result_summary = _require_nonempty(result_summary, "result_summary")
    per_criterion = []
    for criterion in record["acceptance_criteria"]:
        cov = _coverage(result_summary, criterion)
        per_criterion.append(
            {
                "criterion": criterion,
                "coverage": round(cov, 3),
                "met": cov >= _PER_CRITERION_FLOOR,
            }
        )
    overall = (
        sum(p["coverage"] for p in per_criterion) / len(per_criterion)
        if per_criterion
        else 0.0
    )
    resolved = overall >= _OVERALL_FLOOR and all(p["met"] for p in per_criterion)
    record["verdict"] = "resolved" if resolved else "unresolved"
    record["result_summary"] = result_summary
    record["coverage"] = {"per_criterion": per_criterion, "overall": round(overall, 3)}

    composted = None
    if not resolved:
        entry = {
            "seq": len(record["ledger"]),
            "at": _utcnow(now),
            "kind": "unresolved-final",
            "strategy": record["chosen_strategy"],
            "sub_step": "final-result",
            "detail": result_summary,
            "outcome": "fail",
            "taught": "result did not meet the declared acceptance criteria",
            "fingerprint": "",
            "prev_hash": record["ledger"][-1]["hash"]
            if record["ledger"]
            else "GENESIS",
        }
        entry["fingerprint"] = _fingerprint(
            {
                "learner_id": learner_id,
                "strategy": entry["strategy"],
                "sub_step": entry["sub_step"],
                "detail": entry["detail"],
                "outcome": "fail",
            }
        )
        entry["hash"] = _ledger_hash(entry)
        record["ledger"].append(entry)
        composted = _compost_attempt(learner_id, session_id, entry, home, now)

    promotions = _corroborate_passing_patterns(record, home, now)
    record["phase"] = "return"
    _save(record, home)
    return {
        "session_id": session_id,
        "phase": "return",
        "verdict": record["verdict"],
        "coverage": record["coverage"],
        "composted": composted,
        "promotions": promotions,
    }


def _pattern_fingerprint(strategy: str, sub_step: str) -> str:
    return _fingerprint({"strategy": strategy, "sub_step": sub_step})


def _corroborate_passing_patterns(
    record: Dict[str, Any], home: Optional[Path] = None, now: Optional[float] = None
) -> List[Dict[str, Any]]:
    """LAW 4 (PROMOTION THRESHOLD): promote only at >= 2 distinct sessions."""
    d = _base_dir(home) / "__promoted__"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    seen_patterns = set()
    for entry in record["ledger"]:
        if entry.get("kind") != "attempt" or entry.get("outcome") != "pass":
            continue
        key = (entry["strategy"], entry["sub_step"])
        if key in seen_patterns:
            continue
        seen_patterns.add(key)
        fp = _pattern_fingerprint(*key)
        path = d / f"{fp}.json"
        if path.exists():
            promo = json.loads(path.read_text(encoding="utf-8"))
        else:
            promo = {
                "pattern_fingerprint": fp,
                "strategy": key[0],
                "sub_step": key[1],
                "sessions": [],
                "promoted": False,
                "promoted_at": "",
            }
        if record["session_id"] not in promo["sessions"]:
            promo["sessions"].append(record["session_id"])
        # LAW 4: one success is anecdote; two is corroboration.
        if len(promo["sessions"]) >= _PROMOTION_SESSIONS and not promo["promoted"]:
            promo["promoted"] = True
            promo["promoted_at"] = _utcnow(now)
        _write_json(path, promo)
    out = []
    for key in seen_patterns:
        fp = _pattern_fingerprint(*key)
        promo = json.loads((d / f"{fp}.json").read_text(encoding="utf-8"))
        out.append(
            {
                "pattern_fingerprint": fp,
                "strategy": key[0],
                "sub_step": key[1],
                "corroborating_sessions": len(promo["sessions"]),
                "promoted": promo["promoted"],
            }
        )
    return out


def list_promoted(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every promoted procedure. Only corroborated patterns appear as promoted."""
    d = _base_dir(home) / "__promoted__"
    if not d.exists():
        return []
    out = []
    for path in sorted(d.glob("*.json")):
        promo = json.loads(path.read_text(encoding="utf-8"))
        out.append(promo)
    return out


def return_session(
    session_id: str,
    learner_id: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """RETURN: seal the session and hand back the whole trail."""
    record = _load(learner_id, session_id, home)
    _require_phase(record, "return")
    record["sealed_at"] = _utcnow(now)
    _save(record, home)
    chain = verify_ledger(learner_id, session_id, home)
    return {
        "session_id": session_id,
        "learner_id": learner_id,
        "problem": record["problem"],
        "phase": "return",
        "verdict": record["verdict"],
        "acceptance_criteria": record["acceptance_criteria"],
        "chosen_strategy": record["chosen_strategy"],
        "alternatives": [
            s["name"]
            for s in record["strategies"]
            if s["name"] != record["chosen_strategy"]
        ],
        "ledger_entries": len(record["ledger"]),
        "ledger_ok": chain["ok"],
        "sealed_at": record["sealed_at"],
    }
