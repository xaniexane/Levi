"""Hermetic tests for :mod:`levi.gtpm.board` — spec sections 2-4, claims T2-T7.

No network, no daemons, no HOME writes. Deterministic by construction:
no hash() on strings anywhere, no randomness.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from levi.gtpm import board as B


# -- helpers ---------------------------------------------------------------

DEFAULT_LEVELS = ["raw", "parsed", "planned", "verified", "receipted"]


def _ks_trigger_always(_board):
    return True


def _ks_trigger_never(_board):
    return False


def _make_contribute(level, content, confidence, provenance):
    def contribute(_board):
        return (level, dict(content), confidence, list(provenance))

    return contribute


def _scripted_board():
    """Two competing KSs posting rival hypotheses to 'planned'."""
    b = B.new_board()
    B.register_ks(
        b,
        "ks_alpha",
        ["planned"],
        _ks_trigger_always,
        _make_contribute("planned", {"claim": "route-a", "score": 7}, 0.7, ["alpha"]),
        priority=1.0,
    )
    B.register_ks(
        b,
        "ks_beta",
        ["planned"],
        _ks_trigger_always,
        _make_contribute("planned", {"claim": "route-b", "score": 9}, 0.8, ["beta"]),
        priority=1.0,
    )
    return b


def _alternating_trigger(my_name):
    """Fires only when this KS was not the last one to post.

    Gives the scripted T2 scenario strict deterministic alternation:
    alpha fires, then beta, then alpha... — both rivals get posted.
    """

    def trigger(board):
        for ev in reversed(board["transitions"]):
            if ev["event"] == "posted":
                return ev["posted_by"] != my_name
        return True

    return trigger


# -- post validation --------------------------------------------------------

def test_post_rejects_bad_confidence():
    b = B.new_board()
    with pytest.raises(ValueError):
        B.post(b, "raw", {"x": 1}, -0.1, ["p"], "tester")
    with pytest.raises(ValueError):
        B.post(b, "raw", {"x": 1}, 1.5, ["p"], "tester")
    with pytest.raises(ValueError):
        B.post(b, "raw", {"x": 1}, "high", ["p"], "tester")
    # boundaries are legal
    assert B.post(b, "raw", {"x": 1}, 0.0, ["p"], "t")["confidence"] == 0.0
    assert B.post(b, "raw", {"x": 1}, 1.0, ["p"], "t")["confidence"] == 1.0


def test_post_rejects_unknown_level():
    b = B.new_board()
    with pytest.raises(ValueError):
        B.post(b, "imaginary", {"x": 1}, 0.5, ["p"], "tester")


def test_post_rejects_non_dict_content():
    b = B.new_board()
    with pytest.raises(TypeError):
        B.post(b, "raw", ["not", "a", "dict"], 0.5, ["p"], "tester")
    with pytest.raises(TypeError):
        B.post(b, "raw", "a string", 0.5, ["p"], "tester")


def test_post_shape_and_journal():
    b = B.new_board(DEFAULT_LEVELS)
    hyp = B.post(b, "parsed", {"a": 1}, 0.42, ["src1"], "tester", supersedes="h9")
    assert hyp["id"] == "h0"
    assert hyp["level"] == "parsed"
    assert hyp["status"] == "proposed"
    assert hyp["supersedes"] == ["h9"]
    assert hyp["refuted_by"] is None
    assert hyp["t"]  # isoformat utc timestamp present
    assert b["cells"]["parsed"] == [hyp]
    assert B.post(b, "raw", {}, 0.1, [], "t2")["id"] == "h1"  # seq increments
    posted_events = [e for e in b["transitions"] if e["event"] == "posted"]
    assert len(posted_events) == 2
    assert posted_events[0]["id"] == "h0"


def test_new_board_validates_levels():
    with pytest.raises(ValueError):
        B.new_board([])
    with pytest.raises(ValueError):
        B.new_board(["raw", "raw"])
    assert B.new_board()["levels"] == DEFAULT_LEVELS


# -- lifecycle state machine -------------------------------------------------

def test_lifecycle_proposed_active_confirmed():
    b = B.new_board()
    hyp = B.post(b, "planned", {"x": 1}, 0.6, ["p"], "tester")
    assert hyp["status"] == "proposed"
    B.corroborate(b, hyp["id"], by="critic")
    assert hyp["status"] == "active"
    B.confirm(b, hyp["id"])
    assert hyp["status"] == "confirmed"
    kinds = [e["event"] for e in b["transitions"]]
    assert "corroborated" in kinds and "confirmed" in kinds


def test_confirm_requires_active():
    b = B.new_board()
    hyp = B.post(b, "planned", {"x": 1}, 0.6, ["p"], "tester")
    with pytest.raises(ValueError):  # proposed -> confirmed is illegal
        B.confirm(b, hyp["id"])
    B.corroborate(b, hyp["id"], by="c")
    B.confirm(b, hyp["id"])
    with pytest.raises(ValueError):  # double confirm is illegal
        B.confirm(b, hyp["id"])
    with pytest.raises(ValueError):  # unknown id
        B.confirm(b, "h999")


def test_contradict_refutes_but_keeps_hypothesis():
    b = B.new_board()
    hyp = B.post(b, "planned", {"x": 1}, 0.6, ["p"], "tester")
    B.corroborate(b, hyp["id"], by="c")
    B.contradict(b, hyp["id"], by="critic", reason="evidence contradicts")
    assert hyp["status"] == "refuted"
    assert hyp["refuted_by"] == {"by": "critic", "reason": "evidence contradicts"}
    # KEPT, never deleted — still on the board
    assert hyp in b["cells"]["planned"]
    assert any(e["event"] == "refuted" for e in b["transitions"])


def test_corroborate_only_from_proposed():
    b = B.new_board()
    hyp = B.post(b, "planned", {"x": 1}, 0.6, ["p"], "tester")
    B.corroborate(b, hyp["id"], by="c")
    with pytest.raises(ValueError):
        B.corroborate(b, hyp["id"], by="c")  # already active
    B.contradict(b, hyp["id"], by="x", reason="r")
    with pytest.raises(ValueError):
        B.corroborate(b, hyp["id"], by="c")  # refuted, no revival


# -- T2: diversity survival ----------------------------------------------------

def test_t2_diversity_survival_scripted():
    """Two competing KSs; >=2 active hypotheses coexist at the planned step."""
    b = B.new_board()
    B.register_ks(b, "ks_alpha", ["planned"], _alternating_trigger("ks_alpha"),
                  _make_contribute("planned", {"claim": "route-a"}, 0.7, ["a"]), 1.0)
    B.register_ks(b, "ks_beta", ["planned"], _alternating_trigger("ks_beta"),
                  _make_contribute("planned", {"claim": "route-b"}, 0.8, ["b"]), 1.0)
    checks = []
    # alpha and beta alternate fires, so both rival hypotheses get posted
    for cycle in range(10):
        _, receipt = B.step(b, cycle=cycle)
        assert receipt["posted"] is not None
        B.corroborate(b, receipt["posted"]["id"], by="judge")
        active = [h for h in b["cells"]["planned"] if h["status"] == "active"]
        checks.append(len(active) >= 2)
    fraction = sum(checks) / len(checks)
    assert fraction >= 0.3, f"diversity fraction {fraction} below spec floor 0.3"
    # and at the deterministic planned step, both coexist
    active = [h for h in b["cells"]["planned"] if h["status"] == "active"]
    assert {h["posted_by"] for h in active} == {"ks_alpha", "ks_beta"}


def test_diversity_ok_passes_and_fails():
    b = B.new_board()
    h1 = B.post(b, "planned", {"a": 1}, 0.6, ["p"], "t")
    h2 = B.post(b, "planned", {"b": 2}, 0.7, ["p"], "t")
    B.corroborate(b, h1["id"], by="c")
    B.corroborate(b, h2["id"], by="c")
    assert B.diversity_ok(b, "planned") is True
    assert B.diversity_ok(b) is True
    # early pruning before any confirm -> violation (I4)
    B.contradict(b, h2["id"], by="critic", reason="early prune")
    assert B.diversity_ok(b, "planned") is False
    # arbitration confirms winner first -> sanctioned, stays True
    b2 = B.new_board()
    a1 = B.post(b2, "planned", {"a": 1}, 0.6, ["p"], "t")
    a2 = B.post(b2, "planned", {"b": 2}, 0.7, ["p"], "t")
    B.corroborate(b2, a1["id"], by="c")
    B.corroborate(b2, a2["id"], by="c")
    B.arbitrate(b2, "planned", lambda h: "q")
    assert B.diversity_ok(b2, "planned") is True


# -- T3: control determinism ---------------------------------------------------

def _deterministic_board():
    b = B.new_board()
    B.register_ks(b, "zebra", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {"z": 1}, 0.1, ["z"]), priority=5.0)
    B.register_ks(b, "mango", ["parsed"], _ks_trigger_always,
                  _make_contribute("parsed", {"m": 1}, 0.9, ["m"]), priority=5.0)
    B.register_ks(b, "apple", ["planned"], _ks_trigger_never,
                  _make_contribute("planned", {"a": 1}, 0.5, ["a"]), priority=9.0)
    B.post(b, "raw", {"seed": True}, 0.5, ["seed"], "seeder")
    return b


def test_t3_focus_deterministic_1000_calls():
    b = _deterministic_board()
    results = {B.focus(b) for _ in range(1000)}
    assert results == {"mango"}  # priority tie -> name ascending


def test_t3_focus_identical_in_subprocess(tmp_path):
    mine = B.focus(_deterministic_board())
    script = tmp_path / "focus_check.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path(B.__file__).parents[2]).__repr__()})\n"
        "from levi.gtpm import board as B\n"
        "b = B.new_board()\n"
        "B.register_ks(b, 'zebra', ['raw'], lambda b: True,\n"
        "             lambda b: ('raw', {'z': 1}, 0.1, ['z']), priority=5.0)\n"
        "B.register_ks(b, 'mango', ['parsed'], lambda b: True,\n"
        "             lambda b: ('parsed', {'m': 1}, 0.9, ['m']), priority=5.0)\n"
        "B.register_ks(b, 'apple', ['planned'], lambda b: False,\n"
        "             lambda b: ('planned', {'a': 1}, 0.5, ['a']), priority=9.0)\n"
        "B.post(b, 'raw', {'seed': True}, 0.5, ['seed'], 'seeder')\n"
        "print(B.focus(b))\n"
        "print(B.agenda(b)[0][2])\n"  # snapshot hash, cross-process check
    )
    out = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    child_focus, child_snap = out.stdout.split()
    assert child_focus == mine
    assert child_snap == B.agenda(_deterministic_board())[0][2]


# -- T4: KS failure isolation ---------------------------------------------------

def test_t4_ks_failure_isolation():
    def boom(_board):
        raise RuntimeError("ks exploded")

    def bad_trigger(_board):
        raise RuntimeError("trigger exploded")

    b = B.new_board()
    B.register_ks(b, "ks_crashy", ["raw"], _ks_trigger_always, boom, priority=9.0)
    B.register_ks(b, "ks_badtrig", ["raw"], bad_trigger, boom, priority=8.0)
    B.register_ks(b, "ks_good", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {"ok": True}, 0.9, ["g"]), priority=1.0)

    b, receipt = B.step(b, cycle=0)
    assert receipt["focus"] == "ks_good"
    assert receipt["posted"] is not None
    assert receipt["posted"]["posted_by"] == "ks_good"
    skipped_names = {s["ks"] for s in receipt["skipped"]}
    assert {"ks_crashy", "ks_badtrig"} <= skipped_names
    # board still works on the next cycle too
    b, receipt2 = B.step(b, cycle=1)
    assert receipt2["posted"]["posted_by"] == "ks_good"
    # failures journaled, never fatal
    kinds = [e["event"] for e in b["transitions"]]
    assert "contribute_error" in kinds and "trigger_error" in kinds


def test_t4_isolation_20_trials():
    def boom(_board):
        raise RuntimeError("dead ks")

    for trial in range(20):
        b = B.new_board()
        B.register_ks(b, f"dead_{trial}", ["parsed"], _ks_trigger_always, boom, 5.0)
        B.register_ks(b, f"live_{trial}", ["parsed"], _ks_trigger_always,
                      _make_contribute("parsed", {"t": trial}, 0.5, ["l"]), 1.0)
        _, receipt = B.step(b, cycle=trial)
        assert receipt["posted"] is not None, f"trial {trial} produced nothing"
        assert receipt["posted"]["posted_by"] == f"live_{trial}"


# -- T5: arbitration receipts -----------------------------------------------------

def test_t5_arbitration_receipt():
    b = B.new_board()
    h1 = B.post(b, "verified", {"v": "x"}, 0.6, ["ks_one"], "ks_one")
    h2 = B.post(b, "verified", {"v": "x"}, 0.9, ["ks_two"], "ks_two")
    h3 = B.post(b, "verified", {"v": "y"}, 0.4, ["ks_three"], "ks_three")
    for h in (h1, h2, h3):
        B.corroborate(b, h["id"], by="judge")
    B.record_outcome(b, "ks_one", True)    # precision 1.0 -> score 0.6
    B.record_outcome(b, "ks_two", False)   # precision 0.0 -> score 0.0
    B.record_outcome(b, "ks_three", True)  # precision 1.0 -> score 0.4

    receipt = B.arbitrate(b, "verified", lambda h: h["content"]["v"])
    assert receipt["level"] == "verified"
    assert receipt["winner"]["id"] == h1["id"]          # 0.6*1.0 wins group 'x'
    assert receipt["winner"]["status"] == "confirmed"
    assert receipt["winner"]["provenance"] == ["ks_one"]
    loser_ids = {h["id"] for h in receipt["losers"]}
    assert loser_ids == {h2["id"], h3["id"]}
    assert all(h["status"] == "refuted" for h in receipt["losers"])
    assert receipt["weights"] == {h1["id"]: 1.0, h2["id"]: 0.0, h3["id"]: 1.0}
    # refuted hypotheses are kept with their receipts
    assert h2 in b["cells"]["verified"]
    assert h2["refuted_by"]["by"] == "arbitration"


def test_arbitrate_no_active_returns_empty():
    b = B.new_board()
    receipt = B.arbitrate(b, "raw", lambda h: "k")
    assert receipt["winner"] is None and receipt["losers"] == []


def test_record_outcome_precision_math():
    b = B.new_board()
    assert B.record_outcome(b, "k", True)["precision"] == 1.0
    B.record_outcome(b, "k", False)
    B.record_outcome(b, "k", False)
    assert B.record_outcome(b, "k", True)["precision"] == pytest.approx(0.5)


# -- T6: no level-inflation ---------------------------------------------------------

def test_t6_level_inflation_rejected():
    b = B.new_board()
    B.register_ks(b, "ks_parser", ["parsed"], _ks_trigger_always,
                  _make_contribute("verified", {"x": 1}, 0.9, ["p"]), priority=1.0)
    with pytest.raises(ValueError, match="level-inflation"):
        B.post(b, "verified", {"x": 1}, 0.9, ["p"], "ks_parser")
    # nothing was posted or journaled as a hypothesis
    assert b["cells"]["verified"] == []
    assert not [e for e in b["transitions"] if e["event"] == "posted"]
    # audit helper reports a clean board
    assert B.audit_competence(b) == []
    # step() skips the inflating KS instead of letting it through
    _, receipt = B.step(b, cycle=0)
    assert receipt["posted"] is None
    assert receipt["skipped"] and receipt["skipped"][0]["ks"] == "ks_parser"


def test_audit_competence_flags_hand_edited_board():
    b = B.new_board()
    B.register_ks(b, "ks_parser", ["parsed"], _ks_trigger_always,
                  _make_contribute("parsed", {"x": 1}, 0.5, ["p"]), 1.0)
    hyp = B.post(b, "parsed", {"x": 1}, 0.5, ["p"], "ks_parser")
    hyp["level"] = "verified"  # simulate bypassing the API
    b["cells"]["verified"].append(b["cells"]["parsed"].pop())
    violations = B.audit_competence(b)
    assert len(violations) == 1
    assert violations[0]["hypothesis"] == hyp["id"]
    assert violations[0]["competence"] == ["parsed"]


# -- T7: offline ---------------------------------------------------------------------

BANNED_IMPORTS = ("socket", "urllib", "requests", "http")


def test_t7_import_closure_has_no_network_modules(tmp_path):
    script = tmp_path / "import_check.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path(B.__file__).parents[2]).__repr__()})\n"
        "import levi.gtpm.board\n"
        "import levi.gtpm  # package init must be clean too\n"
        f"banned = {BANNED_IMPORTS!r}\n"
        "found = sorted({m for m in sys.modules\n"
        "                if m in banned or m.split('.')[0] in banned})\n"
        "assert not found, f'network modules in import closure: {found}'\n"
        "print('clean')\n"
    )
    out = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    assert "clean" in out.stdout


def test_t7_step_works_with_sockets_disabled(monkeypatch):
    import socket

    def _nope(*a, **k):
        raise RuntimeError("sockets disabled")

    monkeypatch.setattr(socket, "socket", _nope)
    b = B.new_board()
    B.register_ks(b, "ks_a", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {"ok": 1}, 0.7, ["a"]), 1.0)
    _, receipt = B.step(b, cycle=0)
    assert receipt["posted"] is not None
    assert B.focus(b) == "ks_a"


# -- hooks ---------------------------------------------------------------------------

def test_on_transition_listener_receives_events():
    b = B.new_board()
    seen = []
    B.on_transition(b, seen.append)
    hyp = B.post(b, "raw", {"x": 1}, 0.5, ["p"], "t")
    B.corroborate(b, hyp["id"], by="c")
    assert [e["event"] for e in seen] == ["posted", "corroborated"]
    # a failing listener never kills the board
    def bad(_event):
        raise RuntimeError("listener down")

    B.on_transition(b, bad)
    B.confirm(b, hyp["id"])
    assert hyp["status"] == "confirmed"
    assert any(e["event"] == "listener_error" for e in b["transitions"])


def test_step_receipt_shape_and_cycle_event():
    b = B.new_board()
    B.register_ks(b, "ks_a", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {"ok": 1}, 0.7, ["a"]), 2.0)
    b, receipt = B.step(b, cycle=7)
    assert receipt["kind"] == "board"
    assert receipt["cycle"] == 7
    assert receipt["focus"] == "ks_a"
    assert receipt["arbitrations"] == []
    cycle_events = [e for e in b["transitions"] if e["event"] == "cycle"]
    assert cycle_events and cycle_events[0]["cycle"] == 7


def test_agenda_snapshot_changes_with_board_state():
    b = B.new_board()
    B.register_ks(b, "ks_a", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {"ok": 1}, 0.7, ["a"]), 1.0)
    snap1 = B.agenda(b)[0][2]
    B.post(b, "raw", {"more": 1}, 0.3, ["p"], "seeder")
    snap2 = B.agenda(b)[0][2]
    assert snap1 != snap2
    assert len(snap1) == 64  # sha256 hex


def test_agenda_deterministic_ordering():
    b = B.new_board()
    for name in ("c_ks", "a_ks", "b_ks"):
        B.register_ks(b, name, ["raw"], _ks_trigger_always,
                      _make_contribute("raw", {}, 0.5, ["x"]), priority=3.0)
    names = [n for n, _p, _s in B.agenda(b)]
    assert names == ["c_ks", "a_ks", "b_ks"]  # registration order preserved
    assert B.focus(b) == "a_ks"  # focus sorts: priority tie -> name asc


def test_focus_none_when_nothing_triggered():
    b = B.new_board()
    B.register_ks(b, "ks_idle", ["raw"], _ks_trigger_never,
                  _make_contribute("raw", {}, 0.5, ["x"]), 1.0)
    assert B.focus(b) is None
    _, receipt = B.step(b)
    assert receipt["focus"] is None and receipt["posted"] is None


def test_register_ks_validates():
    b = B.new_board()
    with pytest.raises(ValueError):
        B.register_ks(b, "k", ["nope"], _ks_trigger_always,
                      _make_contribute("raw", {}, 0.5, []))
    with pytest.raises(ValueError):
        B.register_ks(b, "k", [], _ks_trigger_always,
                      _make_contribute("raw", {}, 0.5, []))
    B.register_ks(b, "k", ["raw"], _ks_trigger_always,
                  _make_contribute("raw", {}, 0.5, []))
    with pytest.raises(ValueError):
        B.register_ks(b, "k", ["raw"], _ks_trigger_always,
                      _make_contribute("raw", {}, 0.5, []))  # duplicate


def test_hypothesis_serializable():
    b = B.new_board()
    hyp = B.post(b, "planned", {"nested": {"a": [1, 2]}}, 0.5, ["p", "q"], "t")
    json.dumps(hyp)  # receipts must survive the substrate log
    json.dumps(b["transitions"])
