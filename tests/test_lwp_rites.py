"""Tests for levi.lwp.rites — tarot, dice, journal loop."""

from pathlib import Path

import pytest

from levi.lwp.rites import (
    DEFAULT_REVERSAL_ODDS,
    DICE,
    Rites,
    TarotDeck,
    Dice,
)


def test_deck_has_78_cards():
    deck = TarotDeck(seed=1)
    assert deck.remaining() == 78


def test_destructive_draw_no_repeats_across_full_deck():
    deck = TarotDeck(seed=7)
    seen = set()
    while deck.remaining():
        draws = deck.draw(min(5, deck.remaining()))
        for d in draws:
            key = (d.card.name, d.card.arcana)
            assert key not in seen, f"repeat: {key}"
            seen.add(key)
    assert len(seen) == 78
    assert deck.remaining() == 0


def test_draw_past_empty_raises():
    deck = TarotDeck(seed=7)
    deck.draw(78)
    with pytest.raises(ValueError):
        deck.draw(1)


def test_reshuffle_restores_full_deck():
    deck = TarotDeck(seed=7)
    deck.draw(78)
    assert deck.remaining() == 0
    deck.reshuffle()
    assert deck.remaining() == 78


def test_reversal_rate_within_configured_band():
    # 20k seeded draws with reshuffles; default 6% must land in 2-10%.
    deck = TarotDeck(seed=42, reversal_odds=DEFAULT_REVERSAL_ODDS)
    reversed_count = 0
    total = 20000
    for _ in range(total):
        if deck.remaining() == 0:
            deck.reshuffle()
        if deck.draw(1)[0].card.reversed:
            reversed_count += 1
    rate = reversed_count / total
    assert 0.02 <= rate <= 0.10, f"reversal rate {rate:.3f} out of band"


def test_reversal_odds_configurable():
    deck = TarotDeck(seed=3, reversal_odds=0.0)
    draws = deck.draw(78)
    assert not any(d.card.reversed for d in draws)
    with pytest.raises(ValueError):
        TarotDeck(seed=3, reversal_odds=1.5)


def test_deck_deterministic_given_seed():
    a = TarotDeck(seed=99)
    b = TarotDeck(seed=99)
    names_a = [d.card.describe() for d in a.draw(10)]
    names_b = [d.card.describe() for d in b.draw(10)]
    assert names_a == names_b


def test_dice_ranges():
    dice = Dice(seed=11)
    for die, sides in DICE.items():
        for _ in range(200):
            r = dice.roll(die)
            assert 1 <= r.value <= sides, f"{die} gave {r.value}"


def test_dice_unknown_die_raises():
    with pytest.raises(ValueError):
        Dice(seed=1).roll("d30")


def test_dice_deterministic_given_seed():
    a, b = Dice(seed=5), Dice(seed=5)
    assert [a.roll("d20").value for _ in range(20)] == \
           [b.roll("d20").value for _ in range(20)]


def test_rites_loop_journal_tags(tmp_path: Path):
    r = Rites(seed=1234, home=tmp_path)
    r.roll("d20")
    r.draw(1)
    entry = r.note("The road forks at the river.")
    assert entry.at  # timestamp present
    assert entry.last_roll is not None and "d20" in entry.last_roll
    assert entry.last_draw is not None
    assert entry.status == "proposed"


def test_journal_note_without_castings(tmp_path: Path):
    r = Rites(seed=1, home=tmp_path)
    entry = r.note("A quiet line.")
    assert entry.last_roll is None
    assert entry.last_draw is None


def test_journal_requires_explicit_home():
    r = Rites(seed=1)  # no home
    with pytest.raises(ValueError):
        r.note("no home, no write")


def test_export_single_markdown_file(tmp_path: Path):
    r = Rites(seed=9, home=tmp_path)
    r.roll("d6")
    r.draw(3)
    r.note("First casting.")
    r.roll("d20")
    r.note("Second casting.")
    out = r.export()
    assert out.is_file()
    assert out.suffix == ".md"
    text = out.read_text(encoding="utf-8")
    assert text.count("## ") >= 2  # both entries present
    assert "d6" in text and "d20" in text
    assert "proposed" in text


def test_propose_never_auto_canon(tmp_path: Path):
    r = Rites(seed=2, home=tmp_path)
    r.roll("d8")
    r.draw(2)
    events = r.propose()
    assert len(events) == 3
    assert all(e["status"] == "proposed" for e in events)
    assert {e["kind"] for e in events} == {"roll", "draw"}


def test_journal_files_mode_0600(tmp_path: Path):
    r = Rites(seed=4, home=tmp_path)
    r.note("sealed line")
    out = r.export()
    import os
    assert oct(os.stat(out).st_mode & 0o777) == "0o600"
