# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Dynasty wave tests — Gamemaster's tic-tac-toe title.

Pure engine tests: no LEVI_HOME writes needed, but the hermetic
fixture is kept for convention. No network, no daemons.
"""

from __future__ import annotations

import pytest

from levi.dynasty.dna import assert_clean
from levi.dynasty.wave.gamemaster_ttt import (
    LINES,
    MoveError,
    apply_move,
    best_move,
    legal_moves,
    new_board,
    play_game,
    verify_chain,
    winner,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


# -- engine --------------------------------------------------------------
def test_new_board_empty():
    board = new_board()
    assert len(board) == 9
    assert legal_moves(board) == list(range(9))
    assert winner(board) is None


def test_apply_move_returns_new_board(tmp_home):
    board = new_board()
    moved = apply_move(board, "X", 4)
    assert moved[4] == "X"
    assert board[4] is None  # original untouched
    assert moved is not board


def test_legal_moves_reflects_occupancy(tmp_home):
    board = apply_move(apply_move(new_board(), "X", 0), "O", 8)
    assert legal_moves(board) == [1, 2, 3, 4, 5, 6, 7]


@pytest.mark.parametrize("bad_pos", [-1, 9, 100, True, False, "4", 4.0, None])
def test_apply_move_bad_position_raises(tmp_home, bad_pos):
    with pytest.raises(MoveError):
        apply_move(new_board(), "X", bad_pos)


def test_apply_move_occupied_cell_raises(tmp_home):
    board = apply_move(new_board(), "X", 4)
    with pytest.raises(MoveError):
        apply_move(board, "O", 4)


@pytest.mark.parametrize("bad_player", ["x", "o", "Z", "", None, 1])
def test_apply_move_bad_player_raises(tmp_home, bad_player):
    with pytest.raises(MoveError):
        apply_move(new_board(), bad_player, 0)


def test_apply_move_on_finished_game_raises(tmp_home):
    board = new_board()
    for pos in (0, 1, 2):
        board = apply_move(board, "X", pos)
    assert winner(board) == "X"
    with pytest.raises(MoveError):
        apply_move(board, "O", 3)


def test_winner_rows_cols_diags(tmp_home):
    for line in LINES:
        board = new_board()
        for pos in line:
            board = apply_move(board, "O", pos)
        assert winner(board) == "O"


def test_winner_draw():
    # X O X / X O O / O X X — full board, no three-in-a-row
    cells = ("X", "O", "X", "X", "O", "O", "O", "X", "X")
    assert winner(cells) == "draw"


def test_winner_none_mid_game(tmp_home):
    board = apply_move(apply_move(new_board(), "X", 0), "O", 4)
    assert winner(board) is None


# -- minimax --------------------------------------------------------------
def test_best_move_takes_winning_move():
    board = apply_move(apply_move(new_board(), "X", 0), "X", 1)
    assert best_move(board, "X") == 2


def test_best_move_blocks_opponent_win():
    board = apply_move(apply_move(new_board(), "O", 0), "O", 1)
    assert best_move(board, "X") == 2


def test_best_move_deterministic_lowest_index_tiebreak():
    # Empty board: every move draws with perfect play — lowest index wins.
    assert best_move(new_board(), "X") == 0
    assert best_move(new_board(), "O") == 0


def test_best_move_finished_game_raises():
    board = ("X", "O", "X", "X", "O", "O", "O", "X", "X")
    with pytest.raises(MoveError):
        best_move(board, "X")


def test_best_move_bad_depth_limit_raises():
    with pytest.raises(MoveError):
        best_move(new_board(), "X", depth_limit=0)


def test_minimax_never_loses_as_x_against_random():
    for seed in range(30):
        match = play_game("mini-x", "rand-o", o_policy="random", o_seed=seed)
        assert match["winner"] != "rand-o", f"minimax lost as X (seed {seed})"


def test_minimax_vs_minimax_is_always_draw():
    for _ in range(5):
        match = play_game("mini-x", "mini-o")
        assert match["winner"] == "draw"


def test_minimax_o_never_loses_to_scripted_x():
    # X opens scripted (corner), then falls back to minimax; O is
    # minimax throughout — O must never win, and play ends in a draw.
    match = play_game("script-x", "mini-o", x_moves=[0])
    assert match["winner"] != "mini-o"
    assert match["winner"] == "draw"
    assert verify_chain(match) is True


# -- receipted matches ------------------------------------------------------
def test_play_game_full_structure(tmp_home):
    match = play_game("amy", "bot")
    assert match["game"] == "tic-tac-toe"
    assert match["player_x"] == "amy"
    assert match["player_o"] == "bot"
    assert match["winner"] in ("amy", "bot", "draw")
    assert len(match["moves"]) == len(match["turn_hashes"])
    assert match["final_hash"] == match["turn_hashes"][-1]
    # first turn hash binds the genesis prev-hash
    first = match["moves"][0]
    assert first["turn"] == 1 and first["player"] == "X"
    assert verify_chain(match) is True


def test_play_game_scripted_x_moves(tmp_home):
    # X plays corners 0,2 scripted; O answers with minimax.
    match = play_game("amy", "bot", x_moves=[0, 2, 6, 8])
    scripted = [m["pos"] for m in match["moves"] if m["player"] == "X"]
    assert scripted[:2] == [0, 2]
    assert verify_chain(match) is True


def test_play_game_illegal_scripted_move_raises(tmp_home):
    # X scripts 0 twice — the second play is illegal.
    with pytest.raises(MoveError):
        play_game("amy", "bot", x_moves=[0, 0])


def test_play_game_same_names_raise(tmp_home):
    with pytest.raises(MoveError):
        play_game("amy", "amy")
    with pytest.raises(MoveError):
        play_game("", "bot")


def test_play_game_unknown_policy_raises(tmp_home):
    with pytest.raises(MoveError):
        play_game("amy", "bot", o_policy="cheat")


def test_play_game_deterministic_given_inputs(tmp_home):
    a = play_game("amy", "bot")
    b = play_game("amy", "bot")
    assert a["turn_hashes"] == b["turn_hashes"]
    assert a["final_hash"] == b["final_hash"]


def test_corrupt_turn_order_cannot_verify(tmp_home):
    match = play_game("amy", "bot")
    # 1) swap two turns in the log -> chain breaks
    tampered = dict(match)
    tampered["moves"] = [dict(m) for m in match["moves"]]
    tampered["moves"][0], tampered["moves"][1] = (
        tampered["moves"][1],
        tampered["moves"][0],
    )
    assert verify_chain(tampered) is False
    # 2) forge a position -> chain breaks
    tampered2 = dict(match)
    tampered2["moves"] = [dict(m) for m in match["moves"]]
    tampered2["moves"][2] = dict(tampered2["moves"][2])
    tampered2["moves"][2]["pos"] = (tampered2["moves"][2]["pos"] + 1) % 9
    assert verify_chain(tampered2) is False
    # 3) forge the final hash -> chain breaks
    tampered3 = dict(match, final_hash="0" * 64)
    assert verify_chain(tampered3) is False
    # the untouched original still verifies
    assert verify_chain(match) is True


def test_verify_chain_rejects_malformed(tmp_home):
    assert verify_chain({}) is False
    assert verify_chain({"moves": [], "turn_hashes": [], "final_hash": "x"}) is False


# -- eyes-only fence ----------------------------------------------------------
def test_no_eyes_only_markers_in_match_records(tmp_home):
    import json

    match = play_game("amy", "bot")
    assert_clean(json.dumps(match), "tic-tac-toe match record")
