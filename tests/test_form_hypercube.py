"""hypercube form tests: QID dimensional projection.

Proving bar: projection is deterministic, pure, fail-closed on out-of-range
or hostile inputs, and honest about being a map (one-way, not a real
dimension traversal).
"""

import pytest

from levi.hypercube import FORM_NAME, AXES, capabilities, cubie, project


def test_projection_is_deterministic_and_bounded():
    a = project(7, 315, 13, 0)
    b = project(7, 315, 13, 0)
    assert a == b
    assert len(a) == 3
    assert all(0.0 <= v < 1.0 for v in a)


def test_projection_distinguishes_inputs():
    p1 = project(1, 1, 1)
    p2 = project(21, 315, 13)
    assert p1 != p2


def test_recursion_perturbs_deterministically():
    a = project(3, 100, 5, recursion=0)
    b = project(3, 100, 5, recursion=7)
    assert a != b
    assert project(3, 100, 5, recursion=7) == b


def test_fail_closed_on_out_of_range_and_hostile():
    with pytest.raises(ValueError):
        project(0, 1, 1)  # shell below canon
    with pytest.raises(ValueError):
        project(22, 1, 1)  # shell above canon
    with pytest.raises(ValueError):
        project(1, 316, 1)  # form above canon
    with pytest.raises(ValueError):
        project(1, 1, 14)  # logic state above canon
    with pytest.raises(ValueError):
        project(1, 1, 1, -1)  # negative recursion
    for bad in ("7", 7.5, None, True, [7]):
        with pytest.raises(ValueError):
            project(bad, 1, 1)


def test_cubie_record_carries_canon_names_when_seated():
    from levi.ser18 import seat

    seat()
    c = cubie(1, 5, 3)  # form 5 -> 5th SER-18 phase, state 3 -> 3rd state
    assert c["form"] == FORM_NAME
    assert c["qid"] == {"shell": 1, "form": 5, "logic_state": 3, "recursion": 0}
    assert c["phase_name"] == "Echo"
    assert c["state_name"] == "Echo"
    assert "one-way" in c["honest_limit"]


def test_capabilities_honest_limit():
    caps = capabilities()
    assert caps["form"] == FORM_NAME
    assert caps["axes"] == list(AXES)
    assert "does not perform" in caps["honest_limit"]


def test_no_inverse_offered():
    import levi.hypercube as hc

    public = [n for n in dir(hc) if not n.startswith("_")]
    assert not any("inverse" in n or "unproject" in n or "decode" in n for n in public)
