"""Hermetic tests for the L.W.P. reversible press (levi.lwp.reversible).

No network, no HOME writes, no randomness: every assertion is deterministic
(seeds are fixed). All example data is synthetic or the module's own pool.
"""

import pytest

from levi.lwp.reversible import (
    CLAUSES,
    full_paths,
    is_palindromic_clause,
    press_run,
    reading,
    reading_words,
    slice_path,
    spiral_path,
    story_counts,
    verify_pool,
    words,
)


def test_words_tokenizes_and_lowercases():
    assert words("Dawn breaks, breaks dawn.") == ["dawn", "breaks", "breaks", "dawn"]


def test_pool_is_fully_admissible():
    assert verify_pool() == []
    assert len(CLAUSES) == 26
    assert all(is_palindromic_clause(c) for c in CLAUSES)


def test_inadmissible_clause_rejected():
    assert not is_palindromic_clause("The king died.")
    assert verify_pool(["The king died."]) != []


def test_full_paths_are_reverses_with_same_words():
    paths = full_paths(26)
    assert paths["return"] == paths["fall"][::-1]
    assert reading_words(paths["fall"]) == reading_words(paths["return"])[::-1]
    assert len(reading_words(paths["fall"])) == 104


def test_every_clause_survives_reversal():
    # The core guarantee: each clause reads identically both directions,
    # so ANY ordering is grammatical prose.
    for c in CLAUSES:
        w = words(c)
        assert w == w[::-1]


def test_slice_path_free_directional():
    assert slice_path(13, 1, 26) == list(range(13, 27))
    assert slice_path(13, -1, 26) == list(range(13, 0, -1))
    assert slice_path(1, 1, 26, length=3) == [1, 2, 3]
    assert slice_path(26, -1, 26, length=2) == [26, 25]


def test_slice_path_wraparound():
    # Start at page 1, head backward: 1, 26, 25, ...
    assert slice_path(1, -1, 26, wraparound=True)[:4] == [1, 26, 25, 24]
    assert len(slice_path(5, 1, 26, wraparound=True)) == 26
    assert sorted(slice_path(5, 1, 26, wraparound=True)) == list(range(1, 27))


def test_slice_path_rejects_bad_args():
    with pytest.raises(ValueError):
        slice_path(0, 1, 26)
    with pytest.raises(ValueError):
        slice_path(1, 0, 26)


def test_spiral_path_is_full_permutation():
    path = spiral_path(13, 26)
    assert path[:4] == [13, 14, 12, 15]
    assert sorted(path) == list(range(1, 27))
    assert len(path) == 26


def test_spiral_path_from_any_origin():
    for origin in (1, 7, 26):
        path = spiral_path(origin, 26)
        assert sorted(path) == list(range(1, 27))
        assert path[0] == origin


def test_reading_returns_clause_texts_in_order():
    assert reading([1, 26]) == [CLAUSES[0], CLAUSES[25]]


def test_story_counts():
    counts = story_counts(26)
    assert counts["full_span"] == 2
    assert counts["slices_either_direction"] == 26 * 27
    assert counts["wraparound_circular"] == 52
    assert counts["spiral_origins"] == 26
    assert counts["permutations"] == 403291461126605635584000000


def test_press_run_emits_verified_books():
    books = press_run(5, seed=7)
    assert len(books) == 5
    for b in books:
        assert sorted(b["order"]) == list(range(1, 27))
        assert b["words"] == 104
        assert b["seed"] == 7


def test_press_run_is_reproducible_and_varied():
    again = press_run(5, seed=7)
    other = press_run(5, seed=8)
    assert [b["order"] for b in again] == [b["order"] for b in press_run(5, seed=7)]
    assert [b["order"] for b in other] != [b["order"] for b in again]


def test_press_run_halts_on_bad_pool():
    with pytest.raises(ValueError):
        press_run(1, seed=1, clauses=["The king died."])
