"""Hermetic tests for levi.premortem — ranking math, validation, immutability.

No network, no real ~/.levi: $LEVI_HOME is redirected to a tmp dir.
"""

import pytest

from levi.premortem.ritual import Premortem


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return Premortem()


def test_begin_and_list(pm):
    s = pm.begin("launch the new pricing page")
    assert s.id.startswith("pm-")
    assert s.status == "open"
    assert len(pm.sessions()) == 1
    assert len(pm.sessions(status="closed")) == 0


def test_begin_rejects_empty(pm):
    with pytest.raises(ValueError):
        pm.begin("   ")


def test_add_cause_validation(pm):
    s = pm.begin("ship v2")
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "   ", 3, 3)  # empty cause
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "server melts", 0, 3)  # below range
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "server melts", 6, 3)  # above range
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "server melts", 3.5, 3)  # not an int
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "server melts", True, 3)  # bool is not an int
    with pytest.raises(KeyError):
        pm.add_cause("pm-nope", "server melts", 3, 3)


def test_ranking_math(pm):
    s = pm.begin("migrate the database")
    pm.add_cause(s.id, "minor copy typo", likelihood=2, impact=1)  # 2
    pm.add_cause(s.id, "rollback fails", likelihood=3, impact=5)  # 15
    pm.add_cause(
        s.id,
        "data loss on cutover",
        likelihood=5,
        impact=5,
        mitigation="rehearse restore twice",
    )  # 25
    result = pm.close(s.id)
    ranked = result["ranked"]
    assert [c["risk"] for c in ranked] == [25, 15, 2]
    assert ranked[0]["cause"] == "data loss on cutover"
    assert ranked[0]["mitigated"] is True
    assert ranked[1]["mitigated"] is False
    assert result["top_risk"] == 25
    assert result["unmitigated"] == 2


def test_tie_break_by_impact_then_stable(pm):
    s = pm.begin("rebrand")
    pm.add_cause(s.id, "press misreads it", likelihood=2, impact=5)  # 10
    pm.add_cause(s.id, "logo renders badly", likelihood=5, impact=2)  # 10
    result = pm.close(s.id)
    # same risk -> higher impact first
    assert result["ranked"][0]["cause"] == "press misreads it"


def test_checklist_flags_unmitigated(pm):
    s = pm.begin("hire a contractor")
    pm.add_cause(s.id, "they ghost mid-project", likelihood=4, impact=4)
    result = pm.close(s.id)
    assert "UNMITIGATED" in result["checklist"][0]


def test_closed_session_is_immutable(pm):
    s = pm.begin("open a storefront")
    pm.add_cause(s.id, "rent spikes", likelihood=3, impact=4)
    pm.close(s.id)
    with pytest.raises(ValueError):
        pm.close(s.id)  # already closed
    with pytest.raises(ValueError):
        pm.add_cause(s.id, "late idea", likelihood=1, impact=1)
    assert pm.get_session(s.id).status == "closed"


def test_close_unknown_session(pm):
    with pytest.raises(KeyError):
        pm.close("pm-nope")


def test_empty_session_closes_cleanly(pm):
    s = pm.begin("do nothing ambitious")
    result = pm.close(s.id)
    assert result["n_causes"] == 0
    assert result["checklist"] == []
    assert result["top_risk"] == 0


def test_state_survives_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    s = Premortem().begin("expand to europe")
    Premortem().add_cause(s.id, "regulatory surprise", 4, 5)
    assert len(Premortem().get_session(s.id).causes) == 1


def test_cli_smoke(tmp_path, monkeypatch, capsys):
    from levi.premortem.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    assert main(["begin", "rewrite the billing system"]) == 0
    out = capsys.readouterr().out
    session_id = out.split()[1].rstrip(":")
    assert session_id.startswith("pm-")
    assert (
        main(
            [
                "cause",
                session_id,
                "double billing",
                "--likelihood",
                "4",
                "--impact",
                "5",
                "--mitigation",
                "idempotency keys",
            ]
        )
        == 0
    )
    assert (
        main(["cause", session_id, "oops", "--likelihood", "9", "--impact", "5"]) == 1
    )  # rejected
    assert main(["close", session_id]) == 0
    out = capsys.readouterr().out
    assert "pre-mortem" in out
    assert "risk 20" in out
    assert main(["list"]) == 0
