"""Tests for levi.kwic — the KWIC concordance builder.

Law->guard->prove: each test names the law it guards.
"""

from __future__ import annotations

from levi.kwic import STOPWORDS, from_records, kwic_index, render


def test_every_significant_word_indexed_L1():
    entries = kwic_index([("Query By Example", "r1")])
    keywords = [e.keyword for e in entries]
    # "By" is a stopword; Query and Example are significant
    assert sorted(keywords, key=str.lower) == ["Example", "Query"]


def test_stopwords_never_entry_points_L1():
    entries = kwic_index([("The Art of War", "r2")])
    assert {e.keyword for e in entries} == {"Art", "War"}


def test_sorted_case_insensitive_L2():
    entries = kwic_index([
        ("zebra crossing", "a"),
        ("Apple harvest", "b"),
        ("mango season", "c"),
    ])
    assert [e.keyword for e in entries] == [
        "Apple", "crossing", "harvest", "mango", "season", "zebra"]


def test_rotation_lossless_L3():
    title = "Query By Example: ask the database"
    entries = kwic_index([(title, "r3")])
    for e in entries:
        assert " ".join(e.reconstruct().split()) == " ".join(title.split())


def test_location_code_carried():
    entries = kwic_index([("Nomography primer", "arch-nomo")])
    assert all(e.loc == "arch-nomo" for e in entries)


def test_keyword_column_alignment():
    entries = kwic_index([
        ("Query By Example", "r1"),
        ("A much longer title about Example things", "r2"),
    ])
    text = render(entries, keyword_col=30)
    for line, e in zip(text.splitlines(), entries):
        # every keyword starts at exactly the keyword column
        assert line[30:30 + len(e.keyword)] == e.keyword, line


def test_empty_title_yields_nothing():
    assert kwic_index([("", "r")]) == []
    assert kwic_index([("the and of", "r")]) == []


def test_from_records_uses_title_and_id():
    recs = [
        {"id": "arch-a", "title": "Query By Example"},
        {"id": "arch-b", "title": ""},
        {"title": "no id here"},
    ]
    pairs = from_records(recs)
    assert ("Query By Example", "arch-a") in pairs
    assert ("no id here", "") in pairs
    assert all(t for t, _ in pairs)


def test_custom_stopwords():
    entries = kwic_index([("levi archive hunt", "r")], stopwords=frozenset({"levi"}))
    assert {e.keyword for e in entries} == {"archive", "hunt"}


def test_stopwords_constant_sane():
    for w in ("the", "of", "and", "to"):
        assert w in STOPWORDS
