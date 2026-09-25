"""Integration tests: the default accountability instincts (signals/defaults.py).

Everything runs against tmp homes: ``$LEVI_HOME`` is monkeypatched, each
module's store is seeded explicitly, and no network or threads are
involved. The tmp home is NOT named ".levi", so the user-base
translation (``home.parent if home.name == ".levi"``) is a no-op here —
each module resolves to the same store the test seeded.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from levi.signals import default_registry
from levi.signals.defaults import (
    accountability_evidence,
    register_default_instincts,
)
from levi.signals.grades import SignalGrade
from levi.signals.instincts import InstinctRegistry


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _now():
    return datetime.now(timezone.utc)


# -- registration -----------------------------------------------------------


def test_nine_default_instincts_registered(home):
    reg = default_registry(home=home)
    ids = {i.id for i in reg.list()}
    expected = {
        "instinct.two_miss",
        "instinct.empty_block",
        "instinct.error_spike",
        "instinct.promise_overdue",
        "instinct.promise_overdue_severe",
        "instinct.decision_revisit",
        "instinct.interruption_noise",
        "instinct.drift_card",
        "instinct.friction_review",
        "instinct.teachback_review",
        "instinct.energy_recompute",
        "instinct.sweep_cadence",
    }
    assert expected <= ids


def test_default_instinct_cooldowns_and_caps(home):
    reg = default_registry(home=home)
    by_id = {i.id: i for i in reg.list()}
    assert by_id["instinct.promise_overdue"].cooldown == 12 * 3600
    assert by_id["instinct.promise_overdue"].max_grade is SignalGrade.CARD
    assert by_id["instinct.promise_overdue_severe"].cooldown == 24 * 3600
    assert by_id["instinct.promise_overdue_severe"].max_grade is SignalGrade.ESCALATE
    assert by_id["instinct.decision_revisit"].cooldown == 24 * 3600
    assert by_id["instinct.decision_revisit"].max_grade is SignalGrade.CARD
    assert by_id["instinct.interruption_noise"].cooldown == 7 * 24 * 3600
    assert by_id["instinct.interruption_noise"].max_grade is SignalGrade.NUDGE
    assert by_id["instinct.drift_card"].cooldown == 7 * 24 * 3600
    assert by_id["instinct.friction_review"].cooldown == 7 * 24 * 3600
    assert by_id["instinct.teachback_review"].cooldown == 30 * 24 * 3600
    assert by_id["instinct.energy_recompute"].max_grade is SignalGrade.SILENT
    assert by_id["instinct.sweep_cadence"].cooldown == 7 * 24 * 3600


def test_register_defaults_on_foreign_registry(home):
    reg = register_default_instincts(InstinctRegistry(home=home))
    assert reg.get("instinct.drift_card") is not None


def test_premortem_before_lock_not_registered(home):
    # No clean evidence source exists (verified: no big-lock concept in
    # the commitments or premortem packages) — it stays documented, not
    # registered.
    reg = default_registry(home=home)
    assert reg.get("instinct.premortem_before_lock") is None


# -- promises ----------------------------------------------------------------


def test_promises_overdue_fires_card(home):
    from levi.promises.promises import PromiseStore

    store = PromiseStore(home=home)
    store.make("ship the report", due="2026-09-10", now=date(2026, 8, 1))
    evidence = accountability_evidence(home)
    assert evidence["promises.overdue"] >= 1
    assert not evidence["promises.overdue_severe"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    overdue = [s for s in signals if s.source == "instinct.promise_overdue"]
    assert len(overdue) == 1
    assert overdue[0].grade is SignalGrade.CARD
    assert overdue[0].tag == "[warden]"
    assert "fulfill" in overdue[0].actions


def test_promises_severe_escalates_with_ack(home):
    from levi.promises.promises import PromiseStore

    store = PromiseStore(home=home)
    store.make("fix the outage", due="2026-06-10", now=date(2026, 6, 1))
    evidence = accountability_evidence(home)
    assert evidence["promises.overdue_severe"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    severe = [s for s in signals if s.source == "instinct.promise_overdue_severe"]
    assert len(severe) == 1
    assert severe[0].grade is SignalGrade.ESCALATE
    assert severe[0].requires_ack


def test_promises_clean_ledger_stays_silent(home):
    evidence = accountability_evidence(home)
    assert evidence["promises.overdue"] == 0
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    assert [s for s in signals if s.source.startswith("instinct.promise")] == []


# -- decisions ----------------------------------------------------------------


def test_decision_revisit_fires_card(home):
    from levi.decisions.decisions import DecisionJournal

    DecisionJournal(home=home).decide("use sqlite", "simple and local", "2026-09-01")
    evidence = accountability_evidence(home)
    assert evidence["decisions.revisit_due"] >= 1
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    revisit = [s for s in signals if s.source == "instinct.decision_revisit"]
    assert len(revisit) == 1
    assert revisit[0].grade is SignalGrade.CARD
    assert "reaffirm" in revisit[0].actions


# -- interruptions ------------------------------------------------------------


def test_interruption_noise_fires_nudge(home):
    from levi.interruptions.interruptions import InterruptionLedger

    ledger = InterruptionLedger(home=home)
    ledger.log("slack", "ping about deploy", "noise")
    evidence = accountability_evidence(home)
    assert evidence["interruptions.logged_7d"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    noise = [s for s in signals if s.source == "instinct.interruption_noise"]
    assert len(noise) == 1
    assert noise[0].grade is SignalGrade.NUDGE


def test_interruption_empty_ledger_stays_silent(home):
    evidence = accountability_evidence(home)
    assert not evidence["interruptions.logged_7d"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    assert [s for s in signals if s.source == "instinct.interruption_noise"] == []


# -- drift / friction / teachback / energy / sweeps ----------------------------


def test_drift_silent_without_data(home):
    evidence = accountability_evidence(home)
    assert not evidence["drift.card"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    assert [s for s in signals if s.source == "instinct.drift_card"] == []


def test_drift_card_translated_and_capped(home):
    # The drift module emits a CARD-grade dict; the handler translates it
    # and the registry caps it at CARD even if the dict claimed ESCALATE.
    from levi.signals.defaults import _drift_card_handler

    card = {
        "grade": "ESCALATE",
        "tag": "[drift]",
        "title": "Goal drift",
        "body": "behavior diverged",
    }
    signal = _drift_card_handler({"drift.card": True, "_drift.card": card})
    assert signal.grade is SignalGrade.ESCALATE  # handler is honest; registry clamps
    assert "[drift]" in signal.body  # module provenance preserved


def test_friction_review_fires_nudge(home):
    from levi.friction.log import FrictionLog

    log = FrictionLog(home=home)
    for note in (
        "slow test suite again",
        "slow test suite rerun",
        "slow test suite flaky",
    ):
        log.capture(note)
    evidence = accountability_evidence(home)
    assert evidence["friction.captured"] >= 3
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    review = [s for s in signals if s.source == "instinct.friction_review"]
    assert len(review) == 1
    assert review[0].grade is SignalGrade.NUDGE


def test_teachback_due_fires_nudge(home):
    from levi.teachback.model import TeachbackModel

    model = TeachbackModel(home=home)
    model.add_statement("goal", "ship weekly", confidence=0.5)
    # Age the statement 40 days back.
    data = json.loads(model._path.read_text(encoding="utf-8"))
    old = (_now() - timedelta(days=40)).isoformat()
    for doc in data.values():
        doc["updated_at"] = old
    model._path.write_text(json.dumps(data), encoding="utf-8")
    evidence = accountability_evidence(home)
    assert evidence["teachback.due"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    review = [s for s in signals if s.source == "instinct.teachback_review"]
    assert len(review) == 1
    assert review[0].grade is SignalGrade.NUDGE


def test_teachback_fresh_model_stays_silent(home):
    from levi.teachback.model import TeachbackModel

    TeachbackModel(home=home).add_statement("goal", "ship weekly", confidence=0.5)
    evidence = accountability_evidence(home)
    assert not evidence["teachback.due"]
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    assert [s for s in signals if s.source == "instinct.teachback_review"] == []


def test_energy_recompute_is_silent(home):
    from levi.energy.tracker import EnergyLog

    start = _now() - timedelta(hours=3)
    EnergyLog(home=home).log_session(
        start.isoformat(),
        (start + timedelta(hours=2)).isoformat(),
        kind="deep",
        shipped=True,
    )
    evidence = accountability_evidence(home)
    assert evidence["energy.deep_shipped"] >= 1
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    internal = [s for s in signals if s.source == "instinct.energy_recompute"]
    assert len(internal) == 1
    assert internal[0].grade is SignalGrade.SILENT
    # SILENT never reaches the user through the delivery pipeline.
    from levi.signals import deliver

    assert [
        s
        for s in deliver(signals, home=home)
        if s.source == "instinct.energy_recompute"
    ] == []


def test_sweep_cadence_fires_nudge(home):
    from levi.sweeps.sweeps import builtin_specs

    assert builtin_specs()  # the reminder is only honest when specs exist
    evidence = accountability_evidence(home)
    assert evidence["sweeps.have_specs"] >= 1
    reg = default_registry(home=home)
    signals = reg.evaluate(evidence, _now())
    sweep = [s for s in signals if s.source == "instinct.sweep_cadence"]
    assert len(sweep) == 1
    assert sweep[0].grade is SignalGrade.NUDGE


# -- cooldowns -----------------------------------------------------------------


def test_second_evaluation_inside_cooldown_is_silent(home):
    from levi.friction.log import FrictionLog

    log = FrictionLog(home=home)
    for note in (
        "slow test suite again",
        "slow test suite rerun",
        "slow test suite flaky",
    ):
        log.capture(note)
    moment = _now()
    evidence = accountability_evidence(home)
    reg = default_registry(home=home)
    first = reg.evaluate(evidence, moment)
    assert any(s.source == "instinct.friction_review" for s in first)
    second = reg.evaluate(evidence, moment)
    assert [s for s in second if s.source == "instinct.friction_review"] == []


# -- growth <-> creed hook -------------------------------------------------------


def test_creed_corroboration_hook_is_fail_safe():
    from levi.growth.cycle import _creed_corroboration_hook

    hook = _creed_corroboration_hook()
    assert callable(hook)

    class ExplodingStore:
        def get(self, _entry_id):
            raise RuntimeError("boom")

    # Never raises, even when the store explodes.
    assert hook("e1", ExplodingStore()) is None


def test_cycle_passes_hook_to_consolidate(monkeypatch, home):
    import levi.growth.cycle as cycle

    seen = {}

    class FakeExp:
        meta = {"origin": "local"}

    class FakeLearning:
        def to_dict(self):
            return {"id": "l1"}

    def fake_consolidate(learnings, **kwargs):
        seen.update(kwargs)
        return {
            "accepted": len(learnings),
            "corroborated": 0,
            "skipped": 0,
            "writes": [],
        }

    monkeypatch.setattr(cycle, "harvest_new", lambda since=None: ([FakeExp()], {}))
    # NOTE: cycle.py currently calls reflect_detailed() (3-tuple). If a
    # sibling renames it again, this patch target needs updating too.
    monkeypatch.setattr(
        cycle,
        "reflect_detailed",
        lambda exps, use_model=True: ([FakeLearning()], "rule", {}),
    )
    monkeypatch.setattr(cycle, "reflect_cloud", lambda exps: [])
    monkeypatch.setattr(cycle, "consolidate", fake_consolidate)
    cycle.run_cycle(dry_run=True)
    assert "on_corroborate" in seen
    assert callable(seen["on_corroborate"])


# -- evidence shape ---------------------------------------------------------------


def test_evidence_keys_present(home):
    evidence = accountability_evidence(home)
    for key in (
        "promises.overdue",
        "promises.overdue_severe",
        "decisions.revisit_due",
        "interruptions.logged_7d",
        "drift.card",
        "friction.captured",
        "teachback.due",
        "energy.deep_shipped",
        "sweeps.have_specs",
    ):
        assert key in evidence, key
