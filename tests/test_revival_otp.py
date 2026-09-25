"""Tests for levi.revival.otp — OTP-style supervision trees (hermetic, stdlib-only)."""

from __future__ import annotations

import threading
import time

import pytest

from levi.revival.otp import (
    ChildSpec,
    CrashReport,
    Supervisor,
)


def _pump(sup: Supervisor, cond, timeout: float = 5.0, interval: float = 0.01) -> bool:
    """Drive tick() until cond() is true or timeout. Returns cond() result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sup.tick()
        if cond():
            return True
        time.sleep(interval)
    sup.tick()
    return bool(cond())


def _raiser(stop_event, fail_after: float = 0.0, exc=None):
    if exc is None:
        exc = RuntimeError("boom")
    if fail_after:
        stop_event.wait(fail_after)
    raise exc


def _sleeper(stop_event):
    stop_event.wait(30)


# ------------------------------------------------------------------ specs
def test_child_spec_validation():
    with pytest.raises(ValueError, match="non-empty string"):
        ChildSpec("", _sleeper)
    with pytest.raises(ValueError, match="callable"):
        ChildSpec("x", "not-callable")
    with pytest.raises(ValueError, match="restart_mode"):
        ChildSpec("x", _sleeper, restart_mode="sometimes")
    with pytest.raises(ValueError, match="unknown strategy"):
        Supervisor([ChildSpec("x", _sleeper)], strategy="every_man_for_himself")
    with pytest.raises(ValueError, match="duplicate"):
        Supervisor([ChildSpec("a", _sleeper), ChildSpec("a", _sleeper)])


def test_one_for_one_restarts_only_crashed_child():
    restarts = {"a": 0, "b": 0}

    def a(stop_event):
        restarts["a"] += 1
        raise RuntimeError("a crashed")

    sup = Supervisor(
        [ChildSpec("a", a), ChildSpec("b", _sleeper)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: restarts["a"] >= 2)
        time.sleep(0.05)
        sup.tick()
        assert restarts["a"] >= 2
        # b was never restarted (its thread is the original one, still alive)
        status = sup.status()
        assert status["children"]["b"]["restarts"] == 0
        assert status["children"]["b"]["alive"] is True
        reports = sup.crash_reports("a")
        assert len(reports) >= 1
        assert reports[0].exc_type == "RuntimeError"
        assert reports[0].message == "a crashed"
    finally:
        sup.shutdown()


def test_one_for_all_restarts_everything():
    counts = {"a": 0, "b": 0}
    crash = threading.Event()

    def a(stop_event):
        counts["a"] += 1
        while not stop_event.is_set():
            if crash.is_set():
                raise RuntimeError("a crashed")
            stop_event.wait(0.02)

    def b(stop_event):
        counts["b"] += 1
        stop_event.wait(30)

    sup = Supervisor(
        [ChildSpec("a", a), ChildSpec("b", b)],
        strategy="one_for_all",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: counts["a"] >= 1 and counts["b"] >= 1)
        crash.set()
        # wait for the crash to be noticed and everything restarted
        assert _pump(sup, lambda: counts["a"] >= 2 and counts["b"] >= 2)
        assert counts["b"] >= 2  # b restarted even though it never crashed
    finally:
        sup.shutdown()


def test_rest_for_one_restarts_crashed_and_later_only():
    counts = {"a": 0, "b": 0, "c": 0}
    crash = threading.Event()

    def mk(name, may_crash):
        def _t(stop_event):
            counts[name] += 1
            while not stop_event.is_set():
                if may_crash and crash.is_set():
                    raise RuntimeError(f"{name} crashed")
                stop_event.wait(0.02)

        return _t

    sup = Supervisor(
        [
            ChildSpec("a", mk("a", False)),
            ChildSpec("b", mk("b", True)),
            ChildSpec("c", mk("c", False)),
        ],
        strategy="rest_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: all(v >= 1 for v in counts.values()))
        crash.set()
        assert _pump(sup, lambda: counts["b"] >= 2 and counts["c"] >= 2)
        time.sleep(0.05)
        sup.tick()
        assert counts["a"] == 1, "children started before the crashed one are untouched"
        assert counts["b"] >= 2 and counts["c"] >= 2
    finally:
        sup.shutdown()


def test_intensity_limit_gives_up_and_shuts_down():
    sup = Supervisor(
        [ChildSpec("flapper", _raiser, max_restarts=2, restart_window=60.0)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: sup.gave_up == "flapper", timeout=5.0)
        status = sup.status()
        assert status["gave_up"] == "flapper"
        assert status["children"]["flapper"]["state"] == "defunct"
        assert status["shutdown"] is True
        reports = sup.crash_reports("flapper")
        assert len(reports) == 3  # 2 restarts + the fatal one
        assert all(isinstance(r, CrashReport) for r in reports)
        # restart counts recorded on the reports
        assert [r.restart_count for r in reports] == [1, 2, 3]
    finally:
        sup.shutdown()


def test_intensity_window_slides():
    """Restarts spaced outside the window do not trigger give-up."""
    calls = {"n": 0}
    crash = threading.Event()

    def flaky(stop_event):
        calls["n"] += 1
        while not stop_event.is_set():
            if crash.is_set():
                crash.clear()  # crash exactly once per arming
                raise RuntimeError("flap")
            stop_event.wait(0.02)

    sup = Supervisor(
        [ChildSpec("flaky", flaky, max_restarts=1, restart_window=0.2)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        crash.set()  # arm crash #1
        assert _pump(sup, lambda: calls["n"] >= 2)  # crashed -> restarted
        time.sleep(0.35)  # let the restart-intensity window slide past
        sup.tick()
        assert sup.gave_up is None
        crash.set()  # arm crash #2: old restart has aged out of the window
        assert _pump(sup, lambda: calls["n"] >= 3, timeout=5.0)
        time.sleep(0.1)
        sup.tick()
        assert sup.gave_up is None
        assert sup.status()["children"]["flaky"]["state"] == "running"
    finally:
        sup.shutdown()


def test_transient_clean_exit_is_not_restarted():
    done = threading.Event()

    def quick(stop_event):
        done.set()  # returns immediately: clean exit

    sup = Supervisor(
        [ChildSpec("quick", quick, restart_mode="transient")],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: done.is_set())
        time.sleep(0.1)
        sup.tick()
        status = sup.status()
        assert status["children"]["quick"]["state"] == "stopped"
        assert status["children"]["quick"]["restarts"] == 0
        assert sup.crash_reports("quick") == []
    finally:
        sup.shutdown()


def test_permanent_clean_exit_is_restarted():
    calls = {"n": 0}

    def quick(stop_event):
        calls["n"] += 1  # returns immediately

    sup = Supervisor(
        [ChildSpec("quick", quick)],  # permanent by default
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: calls["n"] >= 2)
        reports = sup.crash_reports("quick")
        assert reports and reports[0].exc_type == "ChildExitedNormally"
    finally:
        sup.shutdown()


def test_graceful_shutdown_signals_children():
    seen = threading.Event()

    def worker(stop_event):
        seen.wait(5)  # blocks until stop_event is set below
        # emulate cooperative shutdown
        while not stop_event.is_set():
            time.sleep(0.01)

    def notifier(stop_event):
        seen.set()
        stop_event.wait(30)

    sup = Supervisor(
        [ChildSpec("w", worker), ChildSpec("n", notifier)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: seen.is_set())
        sup.shutdown()
        status = sup.status()
        assert status["shutdown"] is True
        assert all(c["state"] == "stopped" for c in status["children"].values())
        assert all(c["alive"] is False for c in status["children"].values())
    finally:
        sup.shutdown()  # idempotent


def test_monitor_thread_drives_restarts():
    calls = {"n": 0}

    def crasher(stop_event):
        calls["n"] += 1
        raise RuntimeError("x")

    sup = Supervisor([ChildSpec("c", crasher)]).start()  # monitor thread on
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and calls["n"] < 2:
            time.sleep(0.02)
        assert calls["n"] >= 2
    finally:
        sup.shutdown()


def test_crash_report_summary():
    r = CrashReport(
        child="c",
        exc_type="ValueError",
        message="bad",
        traceback="tb",
        at=1.0,
        restart_count=2,
    )
    assert "c" in r.summary() and "ValueError" in r.summary()


def test_lazy_levi_target_missing_module_surfaces_as_crash():
    from levi.revival.otp import lazy_levi_target

    target = lazy_levi_target("levi.no_such_module_xyz:run")
    sup = Supervisor([ChildSpec("lazy", target)]).start(start_monitor=False)
    try:
        assert _pump(sup, lambda: len(sup.crash_reports("lazy")) >= 1)
        assert "lazy import failed" in sup.crash_reports("lazy")[0].message
    finally:
        sup.shutdown()


def test_demo_runs():
    from levi.revival.otp import demo

    out = demo()
    assert out["beats"] >= 1
    assert out["consumed"] == ["msg-0", "msg-1", "msg-2"]
    assert out["status"]["shutdown"] is True
