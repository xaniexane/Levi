"""Guard/proof tests for levi.academy.problem_breakdown (SUNDER, provisional).

Each test names the law it proves. Run from zero: every test builds its
own sessions under a fresh tmp LEVI_HOME. Nothing here claims beyond
what the assertions check.
"""

import json

import pytest

from levi.academy import problem_breakdown as pb

PROBLEM = "How many fence posts for a 100m fence with posts every 10m?"
RESTATEMENT = "Count the posts needed for a 100 meter fence, 10 meter spacing."
CRITERIA = ["answer is 11 posts", "ends are counted"]
STRATEGIES = [
    {
        "name": "divide-and-add",
        "why": "gaps = length/spacing, posts = gaps + 1",
        "assumes": "both ends need posts",
        "risks": "off-by-one if an end is skipped",
    },
    {
        "name": "draw-it",
        "why": "visual check catches the off-by-one",
        "assumes": "nothing",
        "risks": "slow on long fences",
    },
]


def _to_do(home, learner="L1"):
    s = pb.open_session(learner, PROBLEM, home=home)
    sid = s["session_id"]
    pb.survey(
        sid,
        learner,
        RESTATEMENT,
        knowns=["length 100m", "spacing 10m"],
        unknowns=["whether both ends count"],
        home=home,
    )
    pb.unpack(
        sid,
        learner,
        ["how many gaps?", "do both ends need posts?"],
        {"length": "100m", "spacing": "10m"},
        CRITERIA,
        home=home,
    )
    pb.navigate(sid, learner, STRATEGIES, chosen_index=0, home=home)
    return sid


def _attempt(
    sub_step="compute gaps",
    detail="100/10 = 10 gaps, +1 = 11 posts",
    outcome="pass",
    taught="gaps+1 rule",
):
    return {
        "sub_step": sub_step,
        "detail": detail,
        "outcome": outcome,
        "taught": taught,
    }


# LAW 6 — phase order ---------------------------------------------------------


def test_phase_order_enforced(tmp_path):
    s = pb.open_session("L1", PROBLEM, home=tmp_path)
    sid = s["session_id"]
    with pytest.raises(ValueError):
        pb.navigate(sid, "L1", STRATEGIES, home=tmp_path)
    with pytest.raises(ValueError):
        pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    with pytest.raises(ValueError):
        pb.embed(sid, "L1", "done", home=tmp_path)
    with pytest.raises(ValueError):
        pb.return_session(sid, "L1", home=tmp_path)


def test_sealed_session_rejects_further_work(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    pb.embed(
        sid, "L1", "The answer is 11 posts and both ends are counted.", home=tmp_path
    )
    pb.return_session(sid, "L1", home=tmp_path)
    with pytest.raises(ValueError):
        pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)


# LAW 1 — define-done gate ----------------------------------------------------


def test_gate_unpack_rejects_empty_acceptance_criteria(tmp_path):
    s = pb.open_session("L1", PROBLEM, home=tmp_path)
    sid = s["session_id"]
    pb.survey(
        sid,
        "L1",
        RESTATEMENT,
        knowns=["length 100m"],
        unknowns=["end handling"],
        home=tmp_path,
    )
    with pytest.raises(ValueError):
        pb.unpack(sid, "L1", ["q?"], {"length": "100m"}, [], home=tmp_path)


def test_gate_do_unreachable_without_criteria(tmp_path):
    # The phase machine is the gate: unpack cannot complete without
    # criteria, so "do" is unreachable. Prove the machine holds it.
    sid = _to_do(tmp_path)
    rec = json.loads(
        (tmp_path / "academy" / "problem_breakdown" / "L1" / f"{sid}.json").read_text()
    )
    assert rec["phase"] == "do"
    assert rec["acceptance_criteria"] == CRITERIA


def test_survey_requires_unknowns_and_navigate_requires_why(tmp_path):
    s = pb.open_session("L1", PROBLEM, home=tmp_path)
    sid = s["session_id"]
    with pytest.raises(ValueError):
        pb.survey(sid, "L1", RESTATEMENT, knowns=["x"], unknowns=[], home=tmp_path)
    pb.survey(sid, "L1", RESTATEMENT, knowns=["x"], unknowns=["y"], home=tmp_path)
    pb.unpack(sid, "L1", ["q?"], {"v": "1"}, CRITERIA, home=tmp_path)
    bad = [{"name": "guess", "why": "", "assumes": "", "risks": ""}]
    with pytest.raises(ValueError):
        pb.navigate(sid, "L1", bad, home=tmp_path)


# LAW 2 — compost identity ----------------------------------------------------


def test_failed_attempt_composts_with_deterministic_fingerprint(tmp_path):
    sid = _to_do(tmp_path)
    r1 = pb.do_attempt(
        sid, "L1", _attempt(outcome="fail", taught="off by one"), home=tmp_path
    )
    r2 = pb.do_attempt(
        sid, "L1", _attempt(outcome="fail", taught="off by one"), home=tmp_path
    )
    assert r1["fingerprint"] == r2["fingerprint"]
    assert r2["composted"]["recognized"] is True
    assert r2["composted"]["seen_count"] == 2
    # LAW 3 coexistence: both attempts stay on the ledger; only the
    # compost is deduplicated.
    rec = json.loads(
        (tmp_path / "academy" / "problem_breakdown" / "L1" / f"{sid}.json").read_text()
    )
    assert len(rec["ledger"]) == 2
    compost_files = list(
        (tmp_path / "academy" / "problem_breakdown" / "__compost__").glob("*.json")
    )
    assert len(compost_files) == 1


def test_same_failure_across_sessions_recognized(tmp_path):
    sid1 = _to_do(tmp_path, learner="L1")
    r1 = pb.do_attempt(sid1, "L1", _attempt(outcome="fail"), home=tmp_path)
    sid2 = _to_do(tmp_path, learner="L1")
    r2 = pb.do_attempt(sid2, "L1", _attempt(outcome="fail"), home=tmp_path)
    assert r1["fingerprint"] == r2["fingerprint"]
    assert r2["composted"]["recognized"] is True
    assert r2["composted"]["seen_count"] == 2


# LAW 3 — append-only, hash-chained ledger ------------------------------------


def test_ledger_hash_chain_verifies(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(outcome="fail"), home=tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    chain = pb.verify_ledger("L1", sid, home=tmp_path)
    assert chain["ok"] is True
    assert chain["entries"] == 2


def test_ledger_tamper_detected(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    path = tmp_path / "academy" / "problem_breakdown" / "L1" / f"{sid}.json"
    rec = json.loads(path.read_text())
    rec["ledger"][0]["detail"] = "forged detail"
    path.write_text(json.dumps(rec))
    chain = pb.verify_ledger("L1", sid, home=tmp_path)
    assert chain["ok"] is False


def test_no_delete_or_edit_api_exists():
    mutators = [
        n
        for n in dir(pb)
        if any(
            k in n for k in ("delete", "remove", "update", "purge", "edit", "rewrite")
        )
    ]
    assert mutators == [], f"ledger must be append-only, found: {mutators}"


# LAW 5 — criteria verdict -----------------------------------------------------


def test_embed_resolved_only_against_criteria(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    out = pb.embed(
        sid, "L1", "The answer is 11 posts and both ends are counted.", home=tmp_path
    )
    assert out["verdict"] == "resolved"
    assert out["composted"] is None


def test_embed_unresolved_composts_final_state(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    out = pb.embed(sid, "L1", "I got some number, not sure which.", home=tmp_path)
    assert out["verdict"] == "unresolved"
    assert out["composted"] is not None
    assert out["composted"]["fingerprint"]


# LAW 4 — promotion threshold --------------------------------------------------


def test_single_success_does_not_promote(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    out = pb.embed(
        sid, "L1", "The answer is 11 posts and both ends are counted.", home=tmp_path
    )
    promo = out["promotions"][0]
    assert promo["corroborating_sessions"] == 1
    assert promo["promoted"] is False


def test_two_distinct_sessions_promote(tmp_path):
    for _ in range(2):
        sid = _to_do(tmp_path)
        pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
        out = pb.embed(
            sid,
            "L1",
            "The answer is 11 posts and both ends are counted.",
            home=tmp_path,
        )
    promo = out["promotions"][0]
    assert promo["corroborating_sessions"] == 2
    assert promo["promoted"] is True
    listed = pb.list_promoted(home=tmp_path)
    assert any(p["promoted"] for p in listed)


def test_same_session_twice_does_not_double_count(tmp_path):
    # Two passing attempts with the same pattern inside ONE session still
    # count as one corroborating session.
    sid = _to_do(tmp_path)
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    pb.do_attempt(
        sid, "L1", _attempt(detail="100/10=10 gaps, +1=11 posts again"), home=tmp_path
    )
    out = pb.embed(
        sid, "L1", "The answer is 11 posts and both ends are counted.", home=tmp_path
    )
    assert out["promotions"][0]["corroborating_sessions"] == 1
    assert out["promotions"][0]["promoted"] is False


# Full path --------------------------------------------------------------------


def test_full_happy_path_and_sealed_return(tmp_path):
    sid = _to_do(tmp_path)
    pb.do_attempt(
        sid, "L1", _attempt(outcome="fail", taught="forgot +1"), home=tmp_path
    )
    pb.do_attempt(sid, "L1", _attempt(), home=tmp_path)
    emb = pb.embed(
        sid, "L1", "The answer is 11 posts and both ends are counted.", home=tmp_path
    )
    assert emb["verdict"] == "resolved"
    sealed = pb.return_session(sid, "L1", home=tmp_path)
    assert sealed["verdict"] == "resolved"
    assert sealed["ledger_entries"] == 2
    assert sealed["ledger_ok"] is True
    assert sealed["sealed_at"]


def test_invariants_enumerated():
    assert len(pb.INVARIANTS) == 6
