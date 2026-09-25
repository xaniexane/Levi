"""Hermetic tests for the L.W.P. reversible press act structure.

Acts are the longer form: the pool partitioned into k contiguous acts,
visited in the palindromic slot order [1..k..1] so the book is reversible
at act altitude. Labels stay neutral ordinals — no story content in the
form. No network, no HOME writes, no randomness: seeds are fixed.
"""

from collections import Counter

import pytest

from levi.lwp.reversible import (
    CLAUSES,
    act_book,
    act_slots,
    compose_acts,
    full_paths,
    is_palindromic_clause,
    press_run,
    reading_words,
    words as word_tokens,
)


def test_act_slots_is_own_reverse():
    for k in range(1, 13):
        slots = act_slots(k)
        assert slots == slots[::-1]
        assert len(slots) == 2 * k - 1
        assert slots[0] == slots[-1] == 1
        assert slots[k - 1] == k  # the middle act


def test_act_slots_rejects_bad_count():
    with pytest.raises(ValueError):
        act_slots(0)
    with pytest.raises(ValueError):
        act_slots(-3)


def test_compose_acts_partitions_pool_exactly():
    acts = compose_acts(4, seed=7)
    assert [a["act"] for a in acts] == ["Act I", "Act II", "Act III", "Act IV"]
    assert [a["index"] for a in acts] == [1, 2, 3, 4]
    # partition: contiguous, disjoint, complete over 1..26
    ranges = [(a["first"], a["last"]) for a in acts]
    covered = sorted(i for first, last in ranges for i in range(first, last + 1))
    assert covered == list(range(1, 27))
    assert acts[0]["first"] == 1
    assert acts[-1]["last"] == 26
    for a in acts:
        assert a["direction"] in (1, -1)
        # each act's path is a permutation of its own range, in its direction
        if a["direction"] == 1:
            assert a["path"] == list(range(a["first"], a["last"] + 1))
        else:
            assert a["path"] == list(range(a["last"], a["first"] - 1, -1))
        assert sorted(a["path"]) == list(range(a["first"], a["last"] + 1))
        # every clause in the act still reads both directions
        for idx in a["path"]:
            assert is_palindromic_clause(CLAUSES[idx - 1])


def test_compose_acts_deterministic_and_varied():
    again = compose_acts(4, seed=7)
    other = compose_acts(4, seed=8)
    assert again == compose_acts(4, seed=7)
    assert other != again


def test_compose_acts_guards():
    with pytest.raises(ValueError):
        compose_acts(0, seed=1)
    with pytest.raises(ValueError):
        compose_acts(13, seed=1)  # bound: at most 12 acts
    with pytest.raises(ValueError):
        compose_acts(27, seed=1)  # more acts than clauses
    # the pool is verified before anything is composed
    with pytest.raises(ValueError):
        compose_acts(2, seed=1, clauses=["The king died."])


def test_compose_acts_single_act_is_whole_pool():
    (only,) = compose_acts(1, seed=3)
    assert (only["first"], only["last"]) == (1, 26)
    assert sorted(only["path"]) == list(range(1, 27))
    assert act_book([only]) == only["path"]


def test_act_book_follows_palindromic_slots():
    acts = compose_acts(4, seed=7)
    book = act_book(acts)
    expected = [idx for s in act_slots(4) for idx in acts[s - 1]["path"]]
    assert book == expected
    # reversing the book reverses every slot's path in mirror order
    mirror = [idx for s in act_slots(4)[::-1] for idx in acts[s - 1]["path"][::-1]]
    assert book[::-1] == mirror


def test_act_book_clause_multiplicity():
    # Acts 1..k-1 appear twice in the slot palindrome; act k appears once.
    k, seed = 4, 7
    acts = compose_acts(k, seed=seed)
    counts = Counter(act_book(acts))
    for a in acts:
        want = 2 if a["index"] < k else 1
        for idx in range(a["first"], a["last"] + 1):
            assert counts[idx] == want


def test_act_book_longer_than_single_span():
    # 2n - size(middle act) > n whenever k >= 2: the book outruns any
    # single-span reading — that is what "longer acts" means.
    n = len(CLAUSES)
    for k in (2, 3, 5, 12):
        acts = compose_acts(k, seed=11)
        assert len(act_book(acts)) > n
        assert len(act_book(acts)) == 2 * n - (acts[-1]["last"] - acts[-1]["first"] + 1)


def test_act_book_words_match_clause_texts():
    acts = compose_acts(3, seed=5)
    order = act_book(acts)
    words = reading_words(order)
    # word count equals the sum over every clause occurrence in the book
    expect = sum(len(word_tokens(CLAUSES[i - 1])) for i in order)
    assert len(words) == expect
    # and every emitted word comes from the pool's vocabulary
    pool_words = {w for c in CLAUSES for w in word_tokens(c)}
    assert set(words) <= pool_words


def test_act_book_needs_acts():
    with pytest.raises(ValueError):
        act_book([])


def test_compose_acts_on_small_pool():
    pool = CLAUSES[:8]
    acts = compose_acts(3, seed=2, clauses=pool)
    assert len(acts) == 3
    covered = sorted(i for a in acts for i in range(a["first"], a["last"] + 1))
    assert covered == list(range(1, 9))
    assert act_book(acts)  # non-empty book from a small pool


def test_older_path_families_untouched():
    # Additivity law: the act extension changes nothing that existed.
    paths = full_paths(26)
    assert paths["return"] == paths["fall"][::-1]
    book = press_run(1, seed=7)[0]
    assert sorted(book["order"]) == list(range(1, 27))
    assert book["words"] == 104
