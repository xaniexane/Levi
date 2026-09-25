"""Tests for levi.games.sunset — the sunset escrow."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from levi.games import sunset


@pytest.fixture()
def vault(tmp_path):
    return sunset.EscrowVault(root=tmp_path / "escrow")


def _plan(game_id="codebreak"):
    p = sunset.SunsetPlan(
        game_id=game_id,
        escrow_text="If we ever shut down, the game keeps working and your data leaves with you.",
    )
    p.commitments["offline_patch"] = sunset.Commitment(
        promised=True,
        delivered=True,
        evidence="ships with local-only mode, flag --offline",
    )
    p.commitments["state_export"] = sunset.Commitment(
        promised=True, delivered=False, evidence=""
    )
    return p


def test_round_trip(vault):
    p = _plan()
    path = vault.store(p)
    assert path.exists()
    loaded = vault.load("codebreak")
    assert loaded.game_id == "codebreak"
    assert loaded.commitments["offline_patch"].delivered is True
    assert loaded.commitments["offline_patch"].evidence.startswith("ships with")
    assert set(loaded.commitments) >= set(sunset.COMMITMENTS)


def test_missing_plan_is_honest_failure(vault):
    with pytest.raises(sunset.SunsetError) as ei:
        vault.load("ghost-game")
    assert "no sunset plan" in str(ei.value)


def test_drill_reports_broken_promise(vault):
    vault.store(_plan())
    report = sunset.drill(vault, "codebreak")
    assert report.promises_made == 2
    assert report.promises_kept == 1
    assert report.honest is False
    fails = [r for r in report.results if r.promised and not r.ok]
    assert [r.commitment for r in fails] == ["state_export"]
    assert "unverified escrow is marketing" in report.text()


def test_drill_all_kept(vault):
    p = _plan()
    p.commitments["state_export"] = sunset.Commitment(
        promised=True, delivered=True, evidence="JSON saves under ~/.levi/games/saves"
    )
    vault.store(p)
    report = sunset.drill(vault, "codebreak")
    assert report.honest is True
    assert "All 2 promises kept" in report.text()


def test_mark_delivered_then_drill_passes(vault):
    vault.store(_plan())
    sunset.mark_delivered(
        vault, "codebreak", "state_export", "JSON saves under ~/.levi/games/saves"
    )
    report = sunset.drill(vault, "codebreak")
    assert report.honest is True


def test_mark_delivered_rejects_unknown_commitment(vault):
    vault.store(_plan())
    with pytest.raises(sunset.SunsetError):
        sunset.mark_delivered(vault, "codebreak", "flying_cars", "nope")


def test_bad_plan_rejected(vault):
    with pytest.raises(sunset.SunsetError):
        sunset.SunsetPlan.from_dict({"no_game_id": True})


def test_escrow_files_are_owner_only(vault, tmp_path):
    path = vault.store(_plan())
    import os
    import stat

    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_charter_rule_sunset():
    class M:
        def __init__(self, network, plan):
            self.requires_network = network
            self.has_sunset_plan = plan

    # Offline games: no plan needed, the default honest side.
    assert sunset.charter_rule_sunset(M(False, False)) is True
    # Networked game with a plan: acceptable.
    assert sunset.charter_rule_sunset(M(True, True)) is True
    # Networked game WITHOUT a plan: not a LEVI game (the Crew trade).
    assert sunset.charter_rule_sunset(M(True, False)) is False


def test_list_games(vault):
    assert vault.list_games() == []
    vault.store(_plan("alpha"))
    vault.store(_plan("beta"))
    assert vault.list_games() == ["alpha", "beta"]
