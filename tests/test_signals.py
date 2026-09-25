"""Hermetic tests for the LEVI signal plane (core/levi/signals/).

Everything runs against tmp homes: ``$LEVI_HOME`` is monkeypatched (or
``home=`` is passed explicitly) so the real ~/.levi is never touched.
Clocks are injected; there is no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from levi.signals import (
    ActiveHours,
    Instinct,
    InstinctRegistry,
    Mode,
    Signal,
    SignalGrade,
    default_registry,
    deliver,
    gather_evidence,
    get_mode,
    graded_digest,
    heartbeat_to_signals,
    levi_home,
    matches_evidence,
    render,
    route,
    set_mode,
    signals_for_supervisor,
)
from levi.signals.focus import quiet_delivers, should_deliver as focus_should_deliver


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Redirect the LEVI home at call time via $LEVI_HOME."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _sig(grade, **kw):
    params = {"grade": grade, "tag": "[test]", "title": "t"}
    params.update(kw)
    return Signal(**params)


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    """Naive local datetime on 2026-09-{day}; hours.py treats naive as local."""
    return datetime(2026, 9, day, hour, minute, 0)


# ---------------------------------------------------------------------------
# grades / routing
# ---------------------------------------------------------------------------


class TestGrades:
    def test_silent_suppressed_entirely(self):
        d = route(_sig(SignalGrade.SILENT))
        assert d.delivered is False
        assert d.surface == "none"
        assert d.render() == ""
        assert render(_sig(SignalGrade.SILENT)) == ""

    def test_nudge_is_one_chrome_line(self):
        d = route(_sig(SignalGrade.NUDGE, title="block ends", body="in 8m"))
        assert d.delivered is True
        assert d.surface == "chrome-line"
        assert d.render() == "[test] block ends — in 8m"
        assert "\n" not in d.render()

    def test_card_is_tagged_with_actions(self):
        s = _sig(
            SignalGrade.CARD,
            title="DUE: ship page",
            actions=("done", "snooze 1h", "drop"),
        )
        d = route(s)
        assert d.surface == "card" and d.delivered is True
        text = d.render()
        assert "[test] DUE: ship page" in text
        assert "done / snooze 1h / drop" in text

    def test_escalate_requires_ack(self):
        s = _sig(SignalGrade.ESCALATE, title="2x missed lock")
        assert s.requires_ack is True  # forced by the dataclass
        d = route(s)
        assert d.requires_ack is True
        assert "ack required" in d.render()

    def test_escalate_cannot_downgrade_ack(self):
        s = Signal(grade=SignalGrade.ESCALATE, tag="[w]", title="x", requires_ack=False)
        assert s.requires_ack is True

    def test_tag_must_be_bracketed(self):
        with pytest.raises(ValueError):
            _sig(SignalGrade.CARD, tag="warden")


# ---------------------------------------------------------------------------
# instincts: evidence matching, cooldowns, grade caps
# ---------------------------------------------------------------------------


class TestEvidenceMatching:
    def test_bare_key_truthy(self):
        assert matches_evidence("focus.empty_block", {"focus.empty_block": True})
        assert not matches_evidence("focus.empty_block", {"focus.empty_block": False})

    def test_missing_key_never_fires(self):
        assert not matches_evidence("focus.empty_block", {})

    def test_comparison(self):
        assert matches_evidence("commitments.missed>=2", {"commitments.missed": 3})
        assert not matches_evidence("commitments.missed>=2", {"commitments.missed": 1})
        assert matches_evidence("logs.error_spike==true", {"logs.error_spike": True})

    def test_bad_spec_never_fires(self):
        assert not matches_evidence("!!!", {"a": 1})


def _cooldown_instinct(cooldown=3600, max_grade=SignalGrade.CARD):
    def handler(evidence):
        return Signal(
            grade=SignalGrade.CARD, tag="[t]", title="fired", source="instinct.cd"
        )

    return Instinct(
        id="instinct.cd",
        fires_on="x.flag",
        cooldown=cooldown,
        max_grade=max_grade,
        does="test instinct",
        handler=handler,
    )


class TestCooldowns:
    def test_second_fire_inside_cooldown_is_silent(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(_cooldown_instinct())
        first = reg.evaluate({"x.flag": True})
        assert len(first) == 1
        assert reg.evaluate({"x.flag": True}) == []

    def test_cooldown_persists_across_registries(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(_cooldown_instinct())
        assert len(reg.evaluate({"x.flag": True})) == 1
        reg2 = InstinctRegistry(home=home)  # fresh registry, same home
        reg2.register(_cooldown_instinct())
        assert reg2.evaluate({"x.flag": True}) == []

    def test_cooldown_expires(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(_cooldown_instinct(cooldown=3600))
        t0 = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        assert len(reg.evaluate({"x.flag": True}, now=t0)) == 1
        assert reg.evaluate({"x.flag": True}, now=t0 + timedelta(seconds=3599)) == []
        assert (
            len(reg.evaluate({"x.flag": True}, now=t0 + timedelta(seconds=3601))) == 1
        )

    def test_levi_home_resolved_at_call_time(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LEVI_HOME", str(tmp_path))
        assert levi_home() == tmp_path
        reg = InstinctRegistry()  # no home= → resolves env at call time
        reg.register(_cooldown_instinct())
        reg.evaluate({"x.flag": True})
        assert (tmp_path / "signals" / "cooldowns.json").exists()

    def test_no_evidence_no_fire(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(_cooldown_instinct())
        assert reg.evaluate({}) == []
        assert reg.evaluate({"x.flag": False}) == []

    def test_duplicate_id_rejected(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(_cooldown_instinct())
        with pytest.raises(ValueError):
            reg.register(_cooldown_instinct())


class TestGradeCaps:
    def test_capped_instinct_never_emits_escalate(self, home):
        def loud(evidence):
            return Signal(
                grade=SignalGrade.ESCALATE,
                tag="[t]",
                title="loud",
                source="instinct.loud",
            )

        reg = InstinctRegistry(home=home)
        reg.register(
            Instinct(
                id="instinct.loud",
                fires_on="x.flag",
                cooldown=0,
                max_grade=SignalGrade.CARD,
                does="capped",
                handler=loud,
            )
        )
        (signal,) = reg.evaluate({"x.flag": True})
        assert signal.grade is SignalGrade.CARD
        assert signal.requires_ack is False

    def test_default_signal_uses_max_grade(self, home):
        reg = InstinctRegistry(home=home)
        reg.register(
            Instinct(
                id="instinct.plain",
                fires_on="x.flag",
                cooldown=0,
                max_grade=SignalGrade.NUDGE,
                does="nudge me",
            )
        )
        (signal,) = reg.evaluate({"x.flag": True})
        assert signal.grade is SignalGrade.NUDGE
        assert signal.title == "nudge me"


# ---------------------------------------------------------------------------
# focus mute
# ---------------------------------------------------------------------------


class TestFocus:
    def test_focus_blocks_plain_cards(self):
        assert focus_should_deliver(_sig(SignalGrade.CARD), Mode.FOCUS) is False
        assert focus_should_deliver(_sig(SignalGrade.NUDGE), Mode.FOCUS) is False

    def test_focus_passes_due_now_and_escalate(self):
        assert (
            focus_should_deliver(_sig(SignalGrade.CARD, due_now=True), Mode.FOCUS)
            is True
        )
        assert focus_should_deliver(_sig(SignalGrade.ESCALATE), Mode.FOCUS) is True

    def test_other_modes_pass_everything(self):
        for mode in (Mode.PLAN, Mode.REVIEW, Mode.PLAY):
            assert focus_should_deliver(_sig(SignalGrade.NUDGE), mode) is True
            assert focus_should_deliver(_sig(SignalGrade.SILENT), mode) is True

    def test_quiet_is_focus_equivalent(self):
        for grade in SignalGrade:
            s = _sig(grade)
            assert quiet_delivers(s) == focus_should_deliver(s, Mode.FOCUS)

    def test_mode_persists(self, home):
        assert get_mode(home) is Mode.PLAN  # default
        set_mode("focus", home)
        assert get_mode(home) is Mode.FOCUS


# ---------------------------------------------------------------------------
# active-hours gate
# ---------------------------------------------------------------------------


class TestHours:
    def test_inside_window_passes(self):
        gate = ActiveHours()
        assert gate.should_deliver(_sig(SignalGrade.NUDGE), _at(15, 10)) is True
        assert gate.should_deliver(_sig(SignalGrade.CARD), _at(15, 21, 59)) is True

    def test_outside_window_only_escalate(self):
        gate = ActiveHours()
        assert gate.should_deliver(_sig(SignalGrade.NUDGE), _at(15, 23)) is False
        assert gate.should_deliver(_sig(SignalGrade.CARD), _at(15, 7, 59)) is False
        assert gate.should_deliver(_sig(SignalGrade.ESCALATE), _at(15, 3)) is True

    def test_window_edges(self):
        gate = ActiveHours()
        assert gate.in_window(_at(15, 8, 0)) is True  # inclusive start
        assert gate.in_window(_at(15, 22, 0)) is False  # exclusive end

    def test_overnight_window(self):
        gate = ActiveHours.from_strings("22:00", "06:00")
        assert gate.in_window(_at(15, 23, 30)) is True
        assert gate.in_window(_at(16, 2, 0)) is True
        assert gate.in_window(_at(16, 12, 0)) is False

    def test_bad_window_rejected(self):
        with pytest.raises(ValueError):
            ActiveHours(start=(25, 0))


# ---------------------------------------------------------------------------
# delivery pipeline
# ---------------------------------------------------------------------------


class TestDeliver:
    def test_silent_dropped_by_pipeline(self, home):
        out = deliver(
            [_sig(SignalGrade.SILENT)], home=home, mode=Mode.PLAN, now=_at(15, 10)
        )
        assert out == []

    def test_focus_plus_hours_combined(self, home):
        now = _at(15, 23)  # outside active hours
        signals = [
            _sig(SignalGrade.NUDGE, title="n"),
            _sig(SignalGrade.CARD, title="c"),
            _sig(SignalGrade.CARD, title="due", due_now=True),
            _sig(SignalGrade.ESCALATE, title="e"),
        ]
        out = deliver(signals, home=home, mode=Mode.FOCUS, now=now)
        assert [s.title for s in out] == ["e"]  # only ESCALATE survives both


# ---------------------------------------------------------------------------
# wired instincts on real evidence
# ---------------------------------------------------------------------------


def _write_sessions_with_errors(home: Path, count: int, now: datetime) -> None:
    d = home / "agent" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"ts": now.isoformat(), "error": "boom %d" % i})
        for i in range(count)
    ]
    (d / "s1.jsonl").write_text("\n".join(lines), encoding="utf-8")


def _write_focus_block(
    home: Path, start: datetime, end: datetime, name: str = "deep work"
) -> None:
    d = home / "focus"
    d.mkdir(parents=True, exist_ok=True)
    (d / "blocks.json").write_text(
        json.dumps(
            [
                {"name": name, "start": start.isoformat(), "end": end.isoformat()},
            ]
        ),
        encoding="utf-8",
    )


class TestWiredInstincts:
    def test_two_miss_fires_on_evidence(self, home):
        from levi.commitments.commitments import CommitmentStore

        store = CommitmentStore(home=home)
        # tmp home is not named ".levi": wiring reads <home>/.levi/… here.
        store.define("write", start="2026-09-01")
        # 9 missed daily periods, no check-ins
        evidence = gather_evidence(home, _at(10, 10))
        assert evidence["commitments.missed"] >= 2
        reg = default_registry(home=home)
        signals = reg.evaluate(evidence, _at(10, 10))
        two_miss = [s for s in signals if s.source == "instinct.two_miss"]
        assert len(two_miss) == 1
        assert two_miss[0].grade is SignalGrade.ESCALATE
        assert two_miss[0].tag == "[warden]"

    def test_two_miss_silent_without_evidence(self, home):
        reg = default_registry(home=home)
        signals = reg.evaluate(gather_evidence(home, _at(10, 10)))
        # The default accountability plane may still fire (e.g. the sweep
        # cadence reminder); two_miss itself must stay silent.
        assert [s for s in signals if s.source == "instinct.two_miss"] == []

    def test_error_spike_fires(self, home):
        now = _at(15, 12)
        _write_sessions_with_errors(home, 6, now)
        evidence = gather_evidence(home, now)
        assert evidence["logs.errors_1h"] == 6
        assert evidence["logs.error_spike"] is True
        reg = default_registry(home=home)
        (signal,) = [
            s for s in reg.evaluate(evidence, now) if s.source == "instinct.error_spike"
        ]
        assert signal.grade is SignalGrade.CARD
        assert "6 error" in signal.body

    def test_no_spike_no_fire(self, home):
        now = _at(15, 12)
        _write_sessions_with_errors(home, 2, now)
        reg = default_registry(home=home)
        signals = reg.evaluate(gather_evidence(home, now), now)
        assert [s for s in signals if s.source == "instinct.error_spike"] == []

    def test_empty_block_fires(self, home):
        now = _at(15, 12)
        _write_focus_block(
            home, now - timedelta(minutes=60), now + timedelta(minutes=60)
        )
        evidence = gather_evidence(home, now)
        assert evidence["focus.in_block"] is True
        assert evidence["focus.empty_block"] is True
        reg = default_registry(home=home)
        (signal,) = [
            s for s in reg.evaluate(evidence, now) if s.source == "instinct.empty_block"
        ]
        assert signal.grade is SignalGrade.CARD
        assert signal.due_now is True  # pierces focus mute

    def test_block_with_activity_stays_silent(self, home):
        now = _at(15, 12)
        _write_focus_block(
            home, now - timedelta(minutes=60), now + timedelta(minutes=60)
        )
        _write_sessions_with_errors(home, 0, now)  # session file touched now
        (home / "agent" / "sessions" / "s1.jsonl").write_text(
            json.dumps({"ts": now.isoformat(), "msg": "working"}) + "\n",
            encoding="utf-8",
        )
        evidence = gather_evidence(home, now)
        assert evidence["focus.empty_block"] is False
        reg = default_registry(home=home)
        assert [
            s for s in reg.evaluate(evidence, now) if s.source == "instinct.empty_block"
        ] == []


# ---------------------------------------------------------------------------
# supervisor adapter
# ---------------------------------------------------------------------------


class TestSupervisorAdapter:
    def _report(self, services):
        return {"services": services}

    def test_down_service_becomes_card(self, home):
        report = self._report(
            {
                "heartbeat": {"ok": True, "detail": "fine"},
                "agent-server": {"ok": False, "detail": "port in use"},
            }
        )
        signals = signals_for_supervisor(report, home=home, now=_at(15, 10))
        # The default accountability plane (e.g. the sweep cadence reminder)
        # may add its own signals; the supervisor layer contributes exactly
        # one card for the down service.
        supervisor = [s for s in signals if s.tag == "[supervisor]"]
        assert len(supervisor) == 1
        (signal,) = supervisor
        assert signal.grade is SignalGrade.CARD
        assert signal.tag == "[supervisor]"
        assert "agent-server" in signal.title

    def test_all_up_no_evidence_no_signals(self, home):
        report = self._report({"heartbeat": {"ok": True, "detail": "fine"}})
        signals = signals_for_supervisor(report, home=home, now=_at(15, 10))
        # The supervisor layer is silent; the default instinct plane may
        # still contribute (e.g. the sweep cadence reminder).
        assert [s for s in signals if s.tag == "[supervisor]"] == []

    def test_signals_sorted_highest_grade_first(self, home):
        from levi.commitments.commitments import CommitmentStore

        store = CommitmentStore(home=home)
        store.define("write", start="2026-09-01")
        report = self._report({"x": {"ok": False, "detail": "down"}})
        signals = signals_for_supervisor(report, home=home, now=_at(10, 10))
        grades = [s.grade.value for s in signals]
        assert grades == sorted(grades, reverse=True)  # highest grade first
        assert signals[0].source == "instinct.two_miss"  # ESCALATE first
        down = [s for s in signals if s.tag == "[supervisor]"]
        assert len(down) == 1 and "x" in down[0].title


# ---------------------------------------------------------------------------
# heartbeat adapter
# ---------------------------------------------------------------------------


def _hb_result(silent, attention=(), reason="nothing needs attention"):
    return SimpleNamespace(
        checked_at="2026-09-15T12:00:00+00:00",
        silent=silent,
        attention=list(attention),
        reason=reason,
    )


class TestHeartbeatAdapter:
    def test_silent_maps_to_silent_signal(self):
        (signal,) = heartbeat_to_signals(_hb_result(True))
        assert signal.grade is SignalGrade.SILENT
        assert route(signal).delivered is False

    def test_silent_digest_produces_no_output(self, home):
        assert graded_digest(_hb_result(True), home=home) is None

    def test_attention_items_become_cards(self, home):
        result = _hb_result(
            False,
            [
                "growth: 2 provisional learning(s) since last heartbeat — review needed",
                "  • learned a thing",
                "tracked item: automation 'x' — stale (no successful run in 7+ days)",
            ],
        )
        signals = heartbeat_to_signals(result)
        assert len(signals) == 2
        assert all(s.grade is SignalGrade.CARD for s in signals)
        assert "learned a thing" in signals[0].body
        digest = graded_digest(result, home=home, now=_at(15, 12))
        assert digest is not None
        assert "[heartbeat]" in digest
        assert "growth: 2 provisional" in digest

    def test_digest_honors_hours_gate(self, home):
        result = _hb_result(False, ["something needs attention"])
        # 03:00 local: non-escalated cards are held → no output.
        assert graded_digest(result, home=home, now=_at(15, 3)) is None
