"""Hermetic tests for levi.copper — the scored-choreography runner."""

import pytest

from levi.copper import FakeClock, Score, ScoreError, run


def test_order_and_wait_ms():
    seen = []
    score = (Score("s")
             .wait_ms(100, name="w1")
             .exec("a", lambda: seen.append("a") or "A")
             .wait_ms(200, name="w2"))
    clock = FakeClock()
    receipt = run(score, clock=clock)
    assert receipt.completed
    assert seen == ["a"]
    assert clock.now_ms() == 300
    assert clock.advances == [100, 200]


def test_wait_until_satisfied():
    calls = {"n": 0}

    def pred():
        calls["n"] += 1
        return calls["n"] >= 3

    score = Score("s").wait_until("ready", pred, timeout_ms=1000, poll_ms=100)
    clock = FakeClock()
    receipt = run(score, clock=clock)
    assert receipt.completed
    assert clock.now_ms() == 200  # satisfied on 3rd poll after 2 polls
    assert any(e.get("status") == "satisfied" for e in receipt.events)


def test_wait_until_timeout_stops_score():
    ran = []
    score = (Score("s")
             .wait_until("never", lambda: False, timeout_ms=500, poll_ms=100)
             .exec("later", lambda: ran.append(1)))
    receipt = run(score, clock=FakeClock())
    assert not receipt.completed
    assert receipt.stopped_at == 0
    assert "timed out" in receipt.stop_reason
    assert ran == []  # score stopped; nothing after the timeout ran


def test_skip_if_skips_next_exec():
    ran = []
    score = (Score("s")
             .skip_if("skippy", lambda: True)
             .exec("skipped", lambda: ran.append("x"))
             .exec("runs", lambda: ran.append("y")))
    receipt = run(score, clock=FakeClock())
    assert receipt.completed
    assert ran == ["y"]
    assert receipt.executed() == ["runs"]


def test_skip_if_false_runs_exec():
    ran = []
    score = (Score("s")
             .skip_if("keep", lambda: False)
             .exec("runs", lambda: ran.append("y")))
    receipt = run(score, clock=FakeClock())
    assert receipt.completed and ran == ["y"]


def test_skip_if_without_following_exec_is_harmless():
    score = (Score("s")
             .skip_if("lonely", lambda: True)
             .wait_ms(10))
    receipt = run(score, clock=FakeClock())
    assert receipt.completed
    assert any(e.get("status") == "no-exec-after" for e in receipt.events)


def test_exec_error_stops_and_records():
    def boom():
        raise RuntimeError("kaboom")

    ran = []
    score = (Score("s")
             .exec("bad", boom)
             .exec("never", lambda: ran.append(1)))
    receipt = run(score, clock=FakeClock())
    assert not receipt.completed
    assert receipt.stopped_at == 0
    assert "raised" in receipt.stop_reason
    assert ran == []
    err = [e for e in receipt.events if e.get("status") == "error"][0]
    assert "RuntimeError" in err["error"]


def test_receipt_events_carry_timestamps():
    score = (Score("s")
             .wait_ms(50, name="w")
             .exec("e", lambda: None))
    receipt = run(score, clock=FakeClock())
    waits = [e for e in receipt.events if e["op"] == "wait_ms"]
    execs = [e for e in receipt.events if e["op"] == "exec"]
    assert waits[0]["at_ms"] == 0
    assert execs[0]["at_ms"] == 50
    assert execs[0]["elapsed_ms"] >= 0


def test_builder_is_deny_closed():
    with pytest.raises(ScoreError):
        Score("")
    with pytest.raises(ScoreError):
        Score("s").wait_ms(-5)
    with pytest.raises(ScoreError):
        Score("s").wait_ms("ten")
    with pytest.raises(ScoreError):
        Score("s").wait_until("x", lambda: True, timeout_ms=0)
    with pytest.raises(ScoreError):
        Score("s").exec("x", "not-callable")
    with pytest.raises(ScoreError):
        Score("s").skip_if("x", None)


def test_empty_score_completes():
    receipt = run(Score("empty"), clock=FakeClock())
    assert receipt.completed and receipt.events == []


def test_full_recovery_score_demo():
    healthy = {"ok": False}

    def restart():
        healthy["ok"] = True
        return "restarted"

    score = (Score("recovery")
             .skip_if("already-healthy", lambda: healthy["ok"])
             .wait_ms(2_000)
             .exec("restart-service", restart)
             .wait_until("healthy", lambda: healthy["ok"],
                         timeout_ms=30_000, poll_ms=500))
    clock = FakeClock()
    receipt = run(score, clock=clock)
    assert receipt.completed
    assert receipt.executed() == ["restart-service"]
    assert clock.now_ms() == 2_000
    assert healthy["ok"]


def test_skip_if_only_skips_adjacent_exec():
    calls = []

    score = (Score("s")
             .skip_if("already-healthy", lambda: True)
             .exec("restart-service", lambda: calls.append("restart"))
             .wait_ms(10)
             .exec("notify", lambda: calls.append("notify")))
    clock = FakeClock()
    receipt = run(score, clock=clock)
    assert receipt.completed
    # Copper semantics: only the immediately following exec is skipped.
    assert calls == ["notify"]
    assert receipt.executed() == ["notify"]
    assert clock.now_ms() == 10
