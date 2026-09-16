"""Hermetic tests for levi.commitments.

No network, no real HOME: CommitmentStore() resolves paths at call
time, so monkeypatched HOME isolates everything. Dates are pinned via
explicit --day / as_of so tests don't depend on the real calendar.
"""

from __future__ import annotations

import pytest

from levi.commitments.__main__ import main as cli_main
from levi.commitments.commitments import CommitmentError, CommitmentStore


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return CommitmentStore()


def test_define_and_list(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("read", unit="pages", target=20, per="day", start="2026-01-01")
    names = [c["name"] for c in st.list()]
    assert names == ["read"]
    with pytest.raises(CommitmentError):
        st.define("read")  # duplicate


def test_define_validation(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(CommitmentError):
        st.define("x", per="fortnight")
    with pytest.raises(CommitmentError):
        st.define("x", target=0)
    with pytest.raises(CommitmentError):
        st.define("x", rest_days_per_week=7)


def test_streak_counts_consecutive_hits(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("walk", start="2026-09-10")
    for d in ["2026-09-10", "2026-09-11", "2026-09-12"]:
        st.checkin("walk", day=d)
    s = st.status("walk", as_of="2026-09-12")
    assert s["streak"] == 3
    assert s["longest"] == 3
    assert s["hits"] == 3


def test_missed_day_breaks_streak_but_longest_kept(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("walk", start="2026-09-10")
    st.checkin("walk", day="2026-09-10")
    st.checkin("walk", day="2026-09-11")
    # 09-12 missed; 09-13 hit
    st.checkin("walk", day="2026-09-13")
    s = st.status("walk", as_of="2026-09-13")
    assert s["streak"] == 1
    assert s["longest"] == 2
    assert "2026-09-12" in s["missed"]


def test_rest_days_never_break_streak(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    # 2026-09-12 is a Saturday
    st.define("walk", start="2026-09-11", rest_days_per_week=2)
    st.checkin("walk", day="2026-09-11")  # Friday hit
    # Saturday + Sunday are rest -> streak continues into Monday
    st.checkin("walk", day="2026-09-14")  # Monday hit
    s = st.status("walk", as_of="2026-09-14")
    assert s["streak"] == 4  # Fri, Sat(rest), Sun(rest), Mon
    assert "2026-09-12" not in s["missed"]


def test_mulligan_forgives_and_is_limited(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("walk", start="2026-09-10", mulligans_per_month=1)
    st.checkin("walk", day="2026-09-10")
    r = st.mulligan("walk", day="2026-09-11")
    assert "mulligan applied" in r["message"]
    s = st.status("walk", as_of="2026-09-11")
    assert s["streak"] == 2
    with pytest.raises(CommitmentError):
        st.mulligan("walk", day="2026-09-12")  # none left


def test_weekly_target_sums_days(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("gym", per="week", target=3, start="2026-09-07")  # Monday
    st.checkin("gym", day="2026-09-07")
    st.checkin("gym", day="2026-09-09")
    st.checkin("gym", day="2026-09-11")
    s = st.status("gym", as_of="2026-09-13")
    assert s["hits"] == 1 and s["streak"] == 1


def test_pause_holds_streak_state(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("walk", start="2026-09-10")
    st.checkin("walk", day="2026-09-10")
    st.edit("walk", paused=True)
    s = st.status("walk", as_of="2026-09-10")
    assert s["state"] == "paused"


def test_checkin_accumulates_and_rejects_pre_start(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("water", unit="glasses", target=8, start="2026-09-10")
    st.checkin("water", value=3, day="2026-09-10")
    r = st.checkin("water", value=5, day="2026-09-10")
    assert r["total"] == 8
    with pytest.raises(CommitmentError):
        st.checkin("water", day="2026-09-09")


def test_no_shaming_copy_anywhere():
    import levi.commitments.commitments as mod
    import levi.commitments.__main__ as cli

    blob = open(mod.__file__).read() + open(cli.__file__).read()
    lowered = blob.lower()
    for banned in [
        "shame",
        "lazy",
        "failure",
        "let yourself down",
        "disappoint",
        "pathetic",
        "loser",
    ]:
        assert banned not in lowered, "guilt copy found: " + banned


def test_copy_is_neutral_on_miss(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.define("walk", start="2026-09-10")
    s = st.status("walk", as_of="2026-09-10")
    assert "missed last period" in s["state"] or "on track" in s["state"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_cli_define_checkin_status(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert (
        cli_main(
            [
                "define",
                "read",
                "--target",
                "20",
                "--unit",
                "pages",
                "--start",
                "2026-09-10",
            ]
        )
        == 0
    )
    assert cli_main(["checkin", "read", "--value", "20", "--day", "2026-09-10"]) == 0
    assert cli_main(["status", "read"]) == 0
    out = capsys.readouterr().out
    assert "streak" in out and "read" in out


def test_cli_mulligan_and_pause(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    cli_main(["define", "walk", "--mulligans", "1", "--start", "2026-09-10"])
    assert cli_main(["mulligan", "walk", "--day", "2026-09-11"]) == 0
    assert "mulligan applied" in capsys.readouterr().out
    assert cli_main(["pause", "walk"]) == 0
    assert "held, not broken" in capsys.readouterr().out
    assert cli_main(["resume", "walk"]) == 0


def test_cli_unknown_commitment_fails(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["status", "nope"]) == 1
    assert cli_main(["checkin", "nope"]) == 1
