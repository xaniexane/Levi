"""cybrus form tests: identity vault & routing core.

Proving bar: the QID name-table gate is fail-closed (exact counts,
non-empty strings), QID coordinate validation rejects hostile input, and
the SER-18/SER-13 canon tables seat exactly the founder's 18/13 names.
"""

import pytest

from levi.cybrus import qid


def test_register_spec_tables_fail_closed():
    with pytest.raises(ValueError):
        qid.register_spec_tables(["a"] * 17, ["s"] * 13)
    with pytest.raises(ValueError):
        qid.register_spec_tables(["a"] * 18, ["s"] * 12)
    with pytest.raises(ValueError):
        qid.register_spec_tables(["a"] * 17 + [""], ["s"] * 13)
    with pytest.raises(ValueError):
        qid.register_spec_tables(["a"] * 17 + [None], ["s"] * 13)


def test_seated_tables_match_founder_canon():
    from levi.ser18 import SER13_STATES, SER18_PHASES, seat

    seat()
    assert qid.PHASE_NAMES == SER18_PHASES
    assert qid.STATE_NAMES == SER13_STATES
    assert len(qid.PHASE_NAMES) == 18
    assert len(qid.STATE_NAMES) == 13


def test_phase_and_state_name_lookup_after_seating():
    from levi.ser18 import seat

    seat()
    # phase_name() is keyed by SHELL: shell 5 -> 5th SER-18 phase ("Echo")
    probe = qid.QID(shell=5, form=1, logic_state=3, recursion=0)
    assert probe.phase_name() == "Echo"
    # state_name() is keyed by logic_state: state 3 -> "Echo"
    assert probe.state_name() == "Echo"
    assert qid.QID(shell=1, form=1, logic_state=1, recursion=0).phase_name() == "Birth"


def test_qid_coordinate_validation():
    with pytest.raises(ValueError):
        qid.QID(shell=0, form=1, logic_state=1, recursion=0)
    with pytest.raises(ValueError):
        qid.QID(shell=1, form=316, logic_state=1, recursion=0)
    with pytest.raises(ValueError):
        qid.QID(shell=1, form=1, logic_state=0, recursion=0)
    with pytest.raises(ValueError):
        qid.QID(shell="1", form=1, logic_state=1, recursion=0)
