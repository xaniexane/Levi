"""ser-18-core form tests: canon tables, seating, lifecycle, world model.

Proving bar: the SER-18/SER-13 name tables come from the founder's corpus
spec (verbatim), seat() is fail-closed + idempotent, the lifecycle is a
pure state machine with dry-run purity, and unknown phases are data.
"""

import pytest

from levi.ser18 import (
    FORM_NAME,
    SER13_STATES,
    SER18_PHASES,
    Lifecycle,
    seat,
    world_model,
)


def test_canon_tables_hold_exact_canonical_counts():
    assert len(SER18_PHASES) == 18
    assert len(SER13_STATES) == 13
    # anchor points from the founder's spec (verbatim order)
    assert SER18_PHASES[0] == "Birth"
    assert SER18_PHASES[-1] == "Termination"
    assert SER18_PHASES[4] == "Echo"
    assert SER18_PHASES[8] == "Rebirth"
    assert SER13_STATES[0] == "Forward"
    assert SER13_STATES[9] == "Null"
    assert SER13_STATES[-1] == "Hyper-Meta"


def test_seat_registers_tables_fail_closed_and_idempotent():
    from levi.cybrus import qid

    first = seat()
    assert first["form"] == FORM_NAME
    assert first["status"] in ("seated", "already-seated")
    assert qid.PHASE_NAMES == SER18_PHASES
    assert qid.STATE_NAMES == SER13_STATES
    second = seat()
    assert second["status"] in ("seated", "already-seated")
    assert qid.PHASE_NAMES == SER18_PHASES  # unchanged by re-seating


def test_seat_refuses_different_canon():
    from levi.cybrus import qid

    seat()
    qid.register_spec_tables  # the gate itself
    # simulate a foreign canon already seated
    old_phases, old_states = qid.PHASE_NAMES, qid.STATE_NAMES
    try:
        qid.PHASE_NAMES = ["Foreign"] * 18
        qid.STATE_NAMES = ["Alien"] * 13
        receipt = seat()
        assert receipt["status"] == "refused"
        assert "refusing to overwrite" in receipt["reason"]
    finally:
        qid.PHASE_NAMES, qid.STATE_NAMES = old_phases, old_states


def test_qid_gate_rejects_wrong_counts():
    from levi.cybrus.qid import register_spec_tables

    with pytest.raises(ValueError):
        register_spec_tables(["only", "seventeen"] * 8 + ["x"], ["s"] * 13)


def test_lifecycle_rejects_unknown_phase_at_construction():
    with pytest.raises(ValueError):
        Lifecycle(phase="Narnia")


def test_lifecycle_advance_cycles_and_wraps():
    lc = Lifecycle(phase="Preservation")
    r = lc.advance()
    assert r["status"] == "advanced"
    assert lc.phase == "Termination"
    r = lc.advance()
    assert lc.phase == "Birth"  # the cycle: collapse -> rebirth -> ... -> birth


def test_lifecycle_dry_run_purity():
    lc = Lifecycle(phase="Echo")
    r = lc.advance(dry_run=True)
    assert r["status"] == "dry-run"
    assert r["dry_run"] is True
    assert r["phase"] == "Reflection"  # the would-be phase
    assert lc.phase == "Echo"  # nothing moved
    assert lc.history == []


def test_lifecycle_goto_rejects_hostile_phase_as_data():
    lc = Lifecycle(phase="Echo")
    for bad in ("'; DROP TABLE phases; --", 42, None, ["Echo"]):
        r = lc.goto(bad)
        assert r["status"] == "rejected", bad
        assert lc.phase == "Echo"  # data never accepted


def test_world_model_is_descriptive_not_simulative():
    wm = world_model()
    assert wm["shells"] == 21
    assert wm["forms_per_shell"] == 315
    assert wm["logic_states"] == 13
    assert "does not simulate" in wm["honest_limit"]
