"""Hermetic tests for the LEVI Games Warehouse (fair-play additions)."""

from datetime import date

import pytest

from levi.games import charter, daily_puzzle, deduction, hotseat, saves
from levi.games.charter import GameManifest


# ---------------------------------------------------------------------------
# Charter
# ---------------------------------------------------------------------------


def test_charter_default_manifest_is_fair():
    assert charter.is_fair(GameManifest(name="honest-game"))


def test_charter_catches_paid_randomness():
    m = GameManifest(name="sly", has_paid_randomness=True)
    violations = charter.check_manifest(m)
    assert any(v["rule"] == "no_paid_randomness" for v in violations)


def test_charter_catches_all_sly_trades():
    m = GameManifest(
        name="casino",
        has_paid_randomness=True,
        has_streak_punishment=True,
        has_fomo_timers=True,
        has_pay_for_hints=True,
        requires_network=True,
        progress_portable=False,
        odds_declared=False,
        has_time_limited_content=True,
        has_randomness=True,  # with no audit hook: rule 10 trips
        has_sunset_plan=False,  # networked with no funeral plan: rule 11 trips
    )
    ids = {v["rule"] for v in charter.check_manifest(m)}
    assert ids == {r.id for r in charter.RULES}


def test_charter_text_lists_all_rules():
    text = charter.charter_text()
    for rule in charter.RULES:
        assert rule.title in text


# ---------------------------------------------------------------------------
# Codebreak
# ---------------------------------------------------------------------------


def test_codebreak_feedback_black_white():
    assert deduction.feedback(("A", "B", "C", "D"), ("A", "B", "C", "D")) == (4, 0)
    assert deduction.feedback(("A", "B", "C", "D"), ("D", "C", "B", "A")) == (0, 4)
    assert deduction.feedback(("A", "A", "B", "C"), ("A", "B", "B", "D")) == (2, 0)
    assert deduction.feedback(("A", "B", "C", "D"), ("E", "F", "E", "F")) == (0, 0)


def test_codebreak_solves_and_roundtrips():
    game = deduction.new_game(seed=7)
    secret = "".join(game.secret)
    black, white = game.guess(secret)
    assert (black, white) == (4, 0)
    assert game.solved
    restored = deduction.CodebreakGame.from_dict(game.to_dict())
    assert restored.solved and restored.secret == game.secret


def test_codebreak_rejects_bad_guesses():
    game = deduction.new_game(seed=1)
    with pytest.raises(deduction.CodebreakError):
        game.guess("ZZZZ")
    with pytest.raises(deduction.CodebreakError):
        game.guess("AB")


def test_codebreak_manifest_is_fair():
    assert charter.is_fair(deduction.MANIFEST)


# ---------------------------------------------------------------------------
# Daily cipher
# ---------------------------------------------------------------------------


def test_cipher_deterministic_per_date():
    d = date(2026, 9, 16)
    c1, m1 = daily_puzzle.puzzle_for(d)
    c2, m2 = daily_puzzle.puzzle_for(d)
    assert (c1, m1) == (c2, m2)


def test_cipher_differs_across_dates():
    a, _ = daily_puzzle.puzzle_for(date(2026, 9, 16))
    b, _ = daily_puzzle.puzzle_for(date(2026, 9, 17))
    assert a != b


def test_cipher_roundtrip_and_solve():
    game = daily_puzzle.new_cipher(date(2026, 9, 16))
    assert not game.solved()
    inv = {c: p for p, c in game.cipher.items()}
    for ch in set(c for c in game.ciphered if c in daily_puzzle.ALPHABET):
        game.map(ch, inv[ch])
    assert game.solved()


def test_cipher_hint_is_free_and_unlimited():
    game = daily_puzzle.new_cipher(date(2026, 9, 16))
    for _ in range(3):
        game.hint()
    assert game.hints_used == 3  # no cost, no cap


def test_cipher_manifest_is_fair():
    assert charter.is_fair(daily_puzzle.MANIFEST)


def test_cipher_save_roundtrip():
    game = daily_puzzle.new_cipher(date(2026, 9, 16))
    game.map("Q", "E")
    restored = daily_puzzle.DailyCipher.from_dict(game.to_dict())
    assert restored.mapping == game.mapping


# ---------------------------------------------------------------------------
# Hotseat
# ---------------------------------------------------------------------------


def test_tictactoe_win_and_draw():
    g = hotseat.TicTacToe()
    for move in ("0", "3", "1", "4", "2"):  # X takes top row
        g.apply_move(move)
    assert g.winner() == 0
    g2 = hotseat.TicTacToe()
    for move in ("0", "1", "2", "4", "3", "5", "7", "6", "8"):
        g2.apply_move(move)
    assert g2.winner() == -1


def test_tictactoe_rejects_occupied_cell():
    g = hotseat.TicTacToe()
    g.apply_move("0")
    with pytest.raises(hotseat.GameError):
        g.apply_move("0")


def test_nim_last_move_wins():
    g = hotseat.Nim((1, 1))
    g.apply_move("0 1")
    g.apply_move("1 1")
    assert g.winner() == 1


def test_nim_rejects_bad_moves():
    g = hotseat.Nim((3,))
    with pytest.raises(hotseat.GameError):
        g.apply_move("0 4")
    with pytest.raises(hotseat.GameError):
        g.apply_move("bogus")


def test_hotseat_roundtrips():
    for cls, kwargs in ((hotseat.TicTacToe, {}), (hotseat.Nim, {})):
        g = cls(**kwargs)
        first = g.legal_moves()[0]
        g.apply_move(first)
        restored = cls.from_dict(g.to_dict())
        assert restored.to_dict() == g.to_dict()


def test_hotseat_manifest_is_fair():
    assert charter.is_fair(hotseat.MANIFEST)


# ---------------------------------------------------------------------------
# Saves
# ---------------------------------------------------------------------------


def test_saves_roundtrip_and_portability(tmp_path):
    store = saves.SaveStore(root=tmp_path)
    state = {"secret": ["A", "B", "C", "D"], "attempts": 3}
    store.save("codebreak", "slot1", state)
    assert store.load("codebreak", "slot1") == state
    assert store.list_slots("codebreak") == ["slot1"]

    portable = tmp_path / "exported.json"
    store.export("codebreak", "slot1", portable)
    assert store.delete("codebreak", "slot1")
    game_id, slot = store.import_save(portable)
    assert (game_id, slot) == ("codebreak", "slot1")
    assert store.load("codebreak", "slot1") == state


def test_saves_refuse_foreign_files(tmp_path):
    store = saves.SaveStore(root=tmp_path)
    bad = tmp_path / "evil.json"
    bad.write_text('{"game_id": "x"}', encoding="utf-8")
    with pytest.raises(saves.SaveError):
        store.import_save(bad)


def test_saves_missing_slot(tmp_path):
    store = saves.SaveStore(root=tmp_path)
    with pytest.raises(saves.SaveError):
        store.load("codebreak", "nope")
