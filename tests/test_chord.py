"""Proof for levi.methods.chord: the four declared laws.

LAW 1 totality: every chord 1..31 -> exactly one symbol; empty -> ValueError.
LAW 2 order-independence: stroke symbol depends only on the key SET.
LAW 3 round-trip: encode(s) -> decode == s for every encodable symbol.
LAW 4 trainer honesty: exact strokes only; misses reported, never corrected.

Hermetic: no I/O, no network.
"""

from __future__ import annotations

import itertools

import pytest

from core.levi.methods import chord
from core.levi.methods.chord import ChordKeyer, KeyerTrainer


# ---- LAW 1: totality ------------------------------------------------------


class TestTotality:
    def test_all_31_chords_map_to_exactly_one_symbol(self):
        seen = set()
        for total in range(1, 32):
            keys = [k for k in chord.KEYS if total & k]
            sym = chord.decode(keys)
            assert isinstance(sym, str) and len(sym) == 1
            seen.add(total)
        assert seen == set(range(1, 32))

    def test_alphabet_is_engelbart_order(self):
        for n, letter in enumerate("abcdefghijklmnopqrstuvwxyz", start=1):
            keys = [k for k in chord.KEYS if n & k]
            assert chord.decode(keys) == letter

    def test_empty_stroke_rejected(self):
        with pytest.raises(ValueError):
            chord.decode([])

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError):
            chord.decode([1, 3])
        with pytest.raises(ValueError):
            chord.decode([32])

    def test_duplicate_key_rejected(self):
        with pytest.raises(ValueError):
            chord.decode([1, 1, 2])


# ---- LAW 2: order-independence --------------------------------------------


class TestOrderIndependence:
    def test_press_order_does_not_matter(self):
        a = chord.decode([1, 2, 4])
        b = chord.decode([4, 2, 1])
        c = chord.decode([2, 4, 1])
        assert a == b == c == "g"  # 1+2+4 = 7

    def test_rolled_stroke_registers_on_final_release(self):
        keyer = ChordKeyer()
        keyer.press(1)
        keyer.press(2)
        assert keyer.release(1) is None  # still one key down: no register
        assert keyer.release(2) == "c"  # 1+2 = 3

    def test_release_order_does_not_matter(self):
        k1, k2 = ChordKeyer(), ChordKeyer()
        for k in (k1, k2):
            k.press(4)
            k.press(16)
        assert k1.release(4) is None and k1.release(16) == "t"  # 4+16=20
        assert k2.release(16) is None and k2.release(4) == "t"

    def test_keyer_rejects_bad_presses(self):
        keyer = ChordKeyer()
        with pytest.raises(ValueError):
            keyer.press(3)
        keyer.press(1)
        with pytest.raises(ValueError):
            keyer.press(1)  # double-press
        with pytest.raises(ValueError):
            keyer.release(2)  # never depressed


# ---- LAW 3: round-trip ----------------------------------------------------


class TestRoundTrip:
    def test_every_symbol_round_trips(self):
        for total in range(1, 32):
            keys = [k for k in chord.KEYS if total & k]
            sym = chord.decode(keys)
            assert chord.decode(chord.encode(sym)) == sym

    def test_type_text_is_a_stroke_plan(self):
        keyer = ChordKeyer()
        plan = keyer.type_text("hi?")
        assert [chord.decode(s) for s in plan] == ["h", "i", "?"]

    def test_unknown_symbol_rejected(self):
        with pytest.raises(ValueError):
            chord.encode("!")
        with pytest.raises(ValueError):
            chord.encode("A")  # lowercase-only alphabet, honest limit


# ---- LAW 4: trainer honesty -----------------------------------------------


class TestTrainerHonesty:
    def test_exact_hit_accepted(self):
        t = KeyerTrainer()
        assert t.attempt("c", [1, 2]) is True
        assert t.accuracy == 1.0

    def test_miss_reported_with_expected_chord(self):
        t = KeyerTrainer()
        assert t.attempt("c", [1, 4]) is False  # 1+4=5 -> 'e', wrong
        assert t.attempts == 1 and t.correct == 0
        target, expected, got = t.misses[0]
        assert target == "c"
        assert expected == frozenset({1, 2})
        assert got == frozenset({1, 4})
        assert 0.0 <= t.accuracy <= 1.0

    def test_no_auto_correct(self):
        t = KeyerTrainer()
        t.attempt("c", [1, 4])
        # the miss stands as a miss: nothing silently became 'c'
        assert t.correct == 0
        assert t.misses[0][0] == "c"

    def test_accuracy_starts_honest(self):
        assert KeyerTrainer().accuracy == 0.0

    def test_drill_plan_matches_encode(self):
        t = KeyerTrainer()
        assert t.drill("ab") == [chord.encode("a"), chord.encode("b")]

    def test_trainer_rejects_unknown_target(self):
        t = KeyerTrainer()
        with pytest.raises(ValueError):
            t.attempt("!", [1])
