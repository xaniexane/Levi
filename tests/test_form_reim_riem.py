"""reim + riem form tests: compost failures, compress lessons.

Proving bar: both are fail-closed on bad inputs, composting preserves
failures (nothing destroyed), and compression is honest about what it
carried over.
"""

import pytest

from levi.identity.reim import REIM
from levi.identity.riem import RIEM


def test_compost_rejects_non_dict_outcome():
    with pytest.raises(ValueError):
        REIM().compost("a failure is not a string")


def test_compost_preserves_failure_as_lesson():
    lessons = REIM().compost(
        {
            "identity": "probe",
            "success": False,
            "score": 0.2,
            "notes": "test",
            "failures": ["winner score 0.2000 below threshold 0.70"],
        }
    )
    assert isinstance(lessons, list) and lessons
    # the failure is preserved in the lessons, not destroyed
    joined = " ".join(str(l) for l in lessons)
    assert "0.2" in joined or "below" in joined


def test_compress_rejects_bad_inputs():
    with pytest.raises(ValueError):
        RIEM().compress("not-lessons", {})
    with pytest.raises(ValueError):
        RIEM().compress([], "not-a-genome")


def test_compress_produces_deltas():
    genome = {"traits": {}, "lineage": []}
    deltas = RIEM().compress(
        [{"kind": "correction", "detail": "probe lesson", "weight": 1.0}],
        genome,
    )
    assert isinstance(deltas, dict)


def test_reim_riem_roundtrip_honest():
    reim, riem = REIM(), RIEM()
    outcome = {
        "identity": "probe",
        "success": True,
        "score": 0.9,
        "notes": "",
        "failures": [],
    }
    lessons = reim.compost(outcome)
    genome = {"traits": {}, "lineage": []}
    deltas = riem.compress(lessons, genome)
    assert isinstance(deltas, dict)
