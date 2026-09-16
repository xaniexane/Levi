"""Hermetic tests for levi.bridging — no network, tmp HOME."""

from __future__ import annotations

import pytest

from levi.bridging import SHELF
from levi.bridging.bridging import (
    BridgingError,
    BridgingStore,
    fit_bridging,
    note_status,
)
from levi.bridging.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)


def _synthetic():
    """Two camps (a*, b*), two factional notes, one bridging note, one junk note."""
    camp_a = [f"a{i}" for i in range(1, 5)]
    camp_b = [f"b{i}" for i in range(1, 5)]
    ratings = {
        "fA": {u: 1.0 for u in camp_a} | {u: -1.0 for u in camp_b},
        "fB": {u: -1.0 for u in camp_a} | {u: 1.0 for u in camp_b},
        "bridge": {u: 1.0 for u in camp_a + camp_b},
        "junk": {u: -1.0 for u in camp_a + camp_b},
    }
    return ratings


def test_shelf_shape():
    assert SHELF["name"] == "bridging"
    assert SHELF["summary"]
    assert isinstance(SHELF["items"], list) and SHELF["items"]


def test_fit_is_deterministic():
    r = _synthetic()
    f1, f2 = fit_bridging(r), fit_bridging(r)
    assert f1.note_helpfulness == f2.note_helpfulness
    assert f1.rater_factor == f2.rater_factor


def test_bridging_note_outscores_factional():
    fit = fit_bridging(_synthetic())
    h = fit.note_helpfulness
    assert h["bridge"] > h["fA"]
    assert h["bridge"] > h["fB"]
    assert h["junk"] < h["fA"]  # junk is the floor


def test_camps_are_discovered():
    fit = fit_bridging(_synthetic())
    signs_a = {fit.camps(f"a{i}") for i in range(1, 5)}
    signs_b = {fit.camps(f"b{i}") for i in range(1, 5)}
    assert len(signs_a) == 1 and len(signs_b) == 1 and signs_a != signs_b


def test_status_labels():
    ratings = _synthetic()
    fit = fit_bridging(ratings)
    st = {nid: note_status(nid, fit, ratings)["status"] for nid in ratings}
    assert st["bridge"] == "BRIDGING-HELPFUL"
    assert st["junk"] == "NOT-HELPFUL"
    assert st["fA"] in ("HELPFUL-ONE-CAMP", "NEEDS-MORE-RATINGS")
    assert st["fB"] in ("HELPFUL-ONE-CAMP", "NEEDS-MORE-RATINGS")


def test_sparse_note_needs_more_ratings():
    ratings = {"lonely": {"u1": 1.0, "u2": 1.0}}
    fit = fit_bridging(ratings)
    assert note_status("lonely", fit, ratings)["status"] == "NEEDS-MORE-RATINGS"


def test_rating_bounds_enforced(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    s = BridgingStore()
    n = s.add_note("a claim")
    with pytest.raises(BridgingError):
        s.add_rating(n.id, "r", 2.0)
    with pytest.raises(BridgingError):
        s.add_rating("nope", "r", 1.0)
    with pytest.raises(BridgingError):
        s.add_note("   ")


def test_store_roundtrip_and_cli(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["note", "--text", "water is wet", "--id", "n1"]) == 0
    for rater, val in [
        ("a1", "1"),
        ("a2", "1"),
        ("b1", "1"),
        ("b2", "1"),
        ("a3", "-1"),
        ("b3", "-1"),
    ]:
        assert main(["rate", "--note", "n1", "--rater", rater, "--value", val]) == 0
    assert main(["notes"]) == 0
    out = capsys.readouterr().out
    assert "n1" in out and ("HELPFUL" in out or "NEEDS-MORE" in out)
    assert main(["explain", "n1"]) == 0
    assert "helpfulness" in capsys.readouterr().out
    assert main(["rate", "--note", "n1", "--rater", "zz", "--value", "banana"]) == 2
