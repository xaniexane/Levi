"""Wave-006 games additions: bagatelle, mancala, charter rules 8-10.

Hermetic: no network, no filesystem writes outside tmp, fixed seeds.
"""

import json

import pytest

from levi.games import bagatelle, charter, mancala
from levi.games.bagatelle import (
    BagatelleBoard,
    Pin,
    Pocket,
    StepBudgetExceeded,
    classic_board,
)
from levi.games.charter import GameManifest
from levi.games.mancala import (
    IllegalMove,
    MancalaRules,
    RulesError,
)


# ---------------------------------------------------------------------------
# Bagatelle
# ---------------------------------------------------------------------------


def test_layout_string_roundtrip_classic():
    board = classic_board()
    clone = BagatelleBoard.from_layout_string(board.layout_string())
    assert clone.width == board.width
    assert clone.height == board.height
    assert len(clone.pins) == len(board.pins)
    assert [(round(p.x, 1), round(p.y, 1)) for p in clone.pins] == [
        (round(p.x, 1), round(p.y, 1)) for p in board.pins
    ]
    assert [(round(k.x, 1), k.score) for k in clone.pockets] == [
        (round(k.x, 1), k.score) for k in board.pockets
    ]


def test_layout_string_roundtrip_custom():
    board = BagatelleBoard(
        width=120.0,
        height=90.0,
        pins=[Pin(10.5, 20.5, 2.0), Pin(60.0, 40.0, 3.5)],
        pockets=[Pocket(30.0, 25), Pocket(90.0, 75)],
    )
    clone = BagatelleBoard.from_layout_string(board.layout_string())
    assert clone.width == 120.0
    assert clone.height == 90.0
    assert (clone.pins[1].x, clone.pins[1].r) == (60.0, 3.5)
    assert [k.score for k in clone.pockets] == [25, 75]


def test_layout_string_rejects_garbage():
    with pytest.raises(ValueError):
        BagatelleBoard.from_layout_string("not-a-layout")
    with pytest.raises(ValueError):
        BagatelleBoard.from_layout_string("")


def test_simulate_deterministic_with_seed():
    board = classic_board()
    a = bagatelle.simulate(board, 90.0, 260.0, seed=11)
    b = bagatelle.simulate(board, 90.0, 260.0, seed=11)
    assert a.pocket_hit == b.pocket_hit
    assert a.steps == b.steps
    assert a.path_sample == b.path_sample


def test_pin_collision_changes_direction():
    pin_board = BagatelleBoard(
        width=100.0,
        height=140.0,
        pins=[Pin(50.0, 70.0, 4.0)],
        pockets=[Pocket(50.0, 10)],
    )
    bare_board = BagatelleBoard(
        width=100.0, height=140.0, pins=[], pockets=[Pocket(50.0, 10)]
    )
    with_pin = bagatelle.simulate(pin_board, 90.0, 200.0, seed=5)
    without_pin = bagatelle.simulate(bare_board, 90.0, 200.0, seed=5)
    assert with_pin.path_sample != without_pin.path_sample


def test_bounded_steps_raises():
    board = classic_board()
    with pytest.raises(StepBudgetExceeded):
        bagatelle.simulate(board, 90.0, 260.0, seed=1, max_steps=1)


def test_empirical_distribution_covers_all_balls(capsys):
    board = classic_board()
    dist = bagatelle.empirical_distribution(
        board, trials=2000, seed=7, angle_deg=90.0, force=260.0
    )
    assert dist
    total = sum(dist.values())
    assert total == pytest.approx(1.0, abs=0.02)  # every ball pocketed
    out = capsys.readouterr().out
    assert "Empirical odds" in out


def test_render_ascii_has_pins_and_pockets():
    art = bagatelle.render_ascii(classic_board())
    assert "o" in art  # pins
    assert "100" in art  # pocket score label


# ---------------------------------------------------------------------------
# Mancala
# ---------------------------------------------------------------------------


def test_kalah_opening_moves():
    state = mancala.new_state(mancala.VARIANTS["kalah"])
    assert mancala.legal_moves(state) == [0, 1, 2, 3, 4, 5]
    assert not mancala.is_terminal(state)


def test_play_kalah_move_sows_and_grants_extra_turn():
    state = mancala.new_state(mancala.VARIANTS["kalah"])
    after = mancala.play(state, 2)  # 4 seeds -> pits 3,4,5 + own store
    assert after["stores"][0] == 1
    assert after["pits"][0] == [4, 4, 0, 5, 5, 5]
    assert after["turn"] == 0  # landed in store: move again
    # old state untouched (immutability for player-owned saves)
    assert state["stores"][0] == 0
    assert state["pits"][0][2] == 4


def test_play_illegal_move_raises():
    state = mancala.new_state(mancala.VARIANTS["kalah"])
    with pytest.raises(IllegalMove):
        mancala.play(state, 6)
    emptied = mancala.new_state(mancala.VARIANTS["kalah"])
    emptied["pits"][0][2] = 0
    with pytest.raises(IllegalMove):
        mancala.play(emptied, 2)


def test_terminal_and_winner_with_sweep():
    rules = mancala.VARIANTS["kalah"]
    state = mancala.new_state(rules)
    state["pits"] = [[0, 0, 0, 0, 0, 0], [1, 2, 3, 4, 5, 6]]
    state["stores"] = [10, 5]
    assert mancala.is_terminal(state)
    assert mancala.winner(state) == 1  # 5+21=26 beats 10


def test_oware_last_seed_capture():
    rules = mancala.VARIANTS["oware"]
    state = mancala.new_state(rules)
    state["pits"] = [[1, 1, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]]
    after = mancala.play(state, 0)  # pit 1 becomes 2 -> capture both
    assert after["stores"][0] == 2
    assert after["pits"][0][1] == 0


def test_invalid_rules_raise():
    with pytest.raises(RulesError):
        MancalaRules(pits_per_rank=99).validate()
    with pytest.raises(RulesError):
        MancalaRules(sowing="teleport").validate()
    with pytest.raises(RulesError):
        MancalaRules(ranks=4).validate()


def test_state_is_json_serializable():
    state = mancala.new_state(mancala.VARIANTS["kalah"])
    state = mancala.play(state, 2)
    json.dumps(state)  # must not raise


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_generate_variant_validates(seed):
    rules = mancala.generate_variant(seed)
    rules.validate()
    plies = mancala.validate_variant(rules)
    assert 0 < plies <= 400


def test_all_named_variants_terminate():
    for name, rules in mancala.VARIANTS.items():
        assert mancala.validate_variant(rules) > 0, name


def test_generate_variant_is_deterministic():
    assert (
        mancala.generate_variant(42).to_dict() == mancala.generate_variant(42).to_dict()
    )


# ---------------------------------------------------------------------------
# Charter rules 8, 9, 10
# ---------------------------------------------------------------------------


def test_eleven_rules_total():
    assert len(charter.RULES) == 11
    assert [r.id for r in charter.RULES[-4:]] == [
        "no_kill_switch",
        "no_synthetic_scarcity",
        "odds_are_public",
        "sunset_is_planned",
    ]


def test_honest_manifest_still_fair():
    assert charter.is_fair(GameManifest(name="honest"))


def test_rule8_no_kill_switch():
    bad = GameManifest(name="cloud-game", requires_network=True)
    violations = [v["rule"] for v in charter.check_manifest(bad)]
    assert "no_kill_switch" in violations
    good = GameManifest(name="local", requires_network=False)
    assert "no_kill_switch" not in [v["rule"] for v in charter.check_manifest(good)]


def test_rule9_no_synthetic_scarcity():
    bad = GameManifest(name="season-pass", has_time_limited_content=True)
    violations = [v["rule"] for v in charter.check_manifest(bad)]
    assert "no_synthetic_scarcity" in violations
    assert charter.is_fair(GameManifest(name="clean"))


def test_rule10_odds_are_public():
    # Randomness with no audit hook fails.
    sly = GameManifest(name="gacha", has_randomness=True)
    assert "odds_are_public" in [v["rule"] for v in charter.check_manifest(sly)]
    # Randomness with declared odds AND an audit hook passes.
    bagatelle_manifest = GameManifest(
        name="bagatelle",
        has_randomness=True,
        odds_declared=True,
        has_audit_hook=True,
    )
    assert "odds_are_public" not in [
        v["rule"] for v in charter.check_manifest(bagatelle_manifest)
    ]
    # No randomness at all passes trivially.
    assert "odds_are_public" not in [
        v["rule"] for v in charter.check_manifest(GameManifest(name="chess"))
    ]


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_cli_bagatelle(capsys):
    from levi.games.__main__ import main

    assert main(["bagatelle", "--angle", "90", "--force", "260", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "pocket" in out
    assert "layout:" in out


def test_cli_mancala_move(capsys):
    from levi.games.__main__ import main

    assert main(["mancala", "--variant", "kalah", "--move", "2"]) == 0
    out = capsys.readouterr().out
    assert "legal moves" in out


def test_cli_mancala_validate(capsys):
    from levi.games.__main__ import main

    assert main(["mancala", "--validate", "--seed", "2"]) == 0
    out = capsys.readouterr().out
    assert "valid" in out
