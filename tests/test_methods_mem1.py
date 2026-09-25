"""Hermetic tests for core.levi.methods (memory & retrieval systems, part 1).

loci, llull, bruno, pinakes, tironian, commonplace, florilegia, _persist.
Isolated HOME via LEVI_HOME=tmp_path; no network; deterministic.
"""

from __future__ import annotations


import pytest

from core.levi.methods import _persist
from core.levi.methods import (
    bruno,
    commonplace,
    florilegia,
    llull,
    loci,
    pinakes,
    tironian,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


# ---- _persist ------------------------------------------------------------


def test_persist_roundtrip_and_quarantine(home):
    p = _persist.store_path("t1")
    _persist.save_json(p, {"a": 1})
    assert _persist.load_json(p) == {"a": 1}
    assert _persist.load_json(_persist.store_path("missing")) is None
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(_persist.CorruptStoreError):
        _persist.load_json(p)
    assert not p.exists()
    quarantined = list(home.glob(".levi/methods/t1.corrupt-*.json"))
    assert len(quarantined) == 1  # fail-closed: data preserved, never absorbed


def test_persist_rejects_unsafe_names():
    with pytest.raises(ValueError):
        _persist.store_path("../evil")
    with pytest.raises(ValueError):
        _persist.store_path("")


# ---- loci ---------------------------------------------------------------


def test_loci_walk_and_quiz(home):
    pal = loci.Palace("talks")
    pal.add_room("Foyer")
    pal.add_locus("Foyer", "front door")
    pal.add_locus("Foyer", "coat rack")
    pal.deposit("Foyer", "front door", "open with a question", "a giant question mark")
    pal.deposit(
        "Foyer", "coat rack", "three-act structure", "coats shaped like acts I-III"
    )
    script = pal.walk_script()
    assert "front door" in script and "giant question mark" in script
    rounds = pal.quiz_round()
    assert rounds[0] == (
        "At front door (a giant question mark) what did you place?",
        "open with a question",
    )
    assert pal.coverage() == (2, 2)
    pal.save()
    pal2 = loci.Palace("talks")
    assert pal2.coverage() == (2, 2)
    pal2.clear_locus("Foyer", "front door")  # route reuse: image swapped, place kept
    assert pal2.coverage() == (1, 2)


def test_loci_deny_closed(home):
    pal = loci.Palace("p2")
    pal.add_room("R")
    with pytest.raises(ValueError):
        pal.add_room("R")  # duplicate room
    pal.add_locus("R", "L")
    with pytest.raises(ValueError):
        pal.add_locus("R", "L")  # duplicate locus
    with pytest.raises(KeyError):
        pal.deposit("Nope", "L", "fact")
    with pytest.raises(KeyError):
        pal.deposit("R", "Nope", "fact")
    with pytest.raises(ValueError):
        pal.deposit("R", "L", "   ")  # empty fact
    with pytest.raises(ValueError):
        loci.Palace("   ")


# ---- llull ---------------------------------------------------------------


def test_llull_exhaustion_and_judgment():
    ars = llull.Ars(["goodness", "greatness", "eternity"])
    pairs = list(ars.pairs())
    assert len(pairs) == 3
    assert ("goodness", "greatness") in pairs and ("goodness", "eternity") in pairs
    assert ars.count(2) == 3 and ars.count(3) == 1
    assert len(list(ars.triples())) == 1
    kept = ars.generate(2, judge=lambda c: "goodness" in c)
    assert kept and all("goodness" in c for c in kept)
    everything = ars.generate(2)  # no judge: word salad, honestly unjudged
    assert len(everything) == 3


def test_llull_deny_closed():
    with pytest.raises(ValueError):
        llull.Ars([])
    with pytest.raises(ValueError):
        llull.Ars(["a", "a"])  # distinct primitives required
    ars = llull.Ars(["a", "b"])
    with pytest.raises(ValueError):
        list(ars.combinations(1))
    with pytest.raises(ValueError):
        list(ars.combinations(5))
    with pytest.raises(ValueError):
        ars.generate(2, limit=0)


# ---- bruno ----------------------------------------------------------------


def test_bruno_wheel_spin_is_deterministic():
    def make():
        w = bruno.Wheel("essay", seed=42)
        w.add_ring(
            "argument",
            ["syllogism", "analogy", "example"],
            {"analogy": "a bridge made of mirrors"},
        )
        w.add_ring("evidence", ["statistic", "anecdote"])
        return w

    w1, w2 = make(), make()
    assert [w1.spin() for _ in range(5)] == [w2.spin() for _ in range(5)]
    assert w1.total_configurations() == 3 * 2
    cfg = w1.configuration_with_images()
    assert set(cfg) == {"argument", "evidence"}
    assert all(isinstance(v, tuple) and len(v) == 2 for v in cfg.values())


def test_bruno_rotation_and_render():
    w = bruno.Wheel("w")
    w.add_ring("r", ["a", "b", "c"])
    assert w.configuration() == {"r": "a"}
    w.spin(steps={"r": 2})
    assert w.configuration() == {"r": "c"}
    assert "r=c" in w.render()
    deck = w.deal(4)
    assert len(deck) == 4
    w2 = bruno.Wheel.from_dict(w.to_dict())
    assert w2.configuration() == w.configuration()


def test_bruno_deny_closed():
    w = bruno.Wheel("w")
    with pytest.raises(ValueError):
        w.add_ring("r", ["only-one"])
    with pytest.raises(ValueError):
        w.add_ring("r2", ["a", "a"])
    with pytest.raises(ValueError):
        w.spin()  # no rings


# ---- pinakes --------------------------------------------------------------


def test_pinakes_catalog_and_disputed(home):
    cat = pinakes.Pinakes()
    e1 = pinakes.Entry(
        title="On Memory",
        author="Cicero",
        subject="rhetoric",
        summary="founding myth of loci, via Simonides",
        authenticity="disputed",
        provenance="my shelf",
    )
    e2 = pinakes.Entry(
        title="Ars Magna",
        author="Llull, Ramon",
        subject="logic",
        authenticity="authentic",
    )
    id1 = cat.add(e1)
    id2 = cat.add(e2)
    cat.link(id1, id2)
    assert cat.entries[id1].crossrefs == [id2]
    assert [e for _, e in cat.by_author("cicero")]
    assert [e for _, e in cat.by_subject("logic")]
    assert [eid for eid, _ in cat.disputed()] == [id1]
    text = cat.annotated_list()
    assert "authenticity: disputed" in text and "see also" in text
    cat.save()
    cat2 = pinakes.Pinakes()
    assert len(cat2.entries) == 2 and cat2.entries[id1].crossrefs == [id2]


def test_pinakes_deny_closed(home):
    cat = pinakes.Pinakes()
    with pytest.raises(ValueError):
        cat.add(pinakes.Entry(title="", author="X", subject="Y"))
    with pytest.raises(ValueError):
        cat.add(pinakes.Entry(title="T", author="X", subject="Y", authenticity="canon"))
    with pytest.raises(KeyError):
        cat.link("P-9999", "P-0001")


# ---- tironian --------------------------------------------------------------


def test_tironian_define_expand_compound():
    sh = tironian.Shorthand()
    sh.define("mtg", "meeting with quarterly review team")
    sh.define_compound("-q", "{x} with quarterly figures")
    assert sh.expand("prep mtg now") == "prep meeting with quarterly review team now"
    assert (
        sh.expand("see mtg-q")
        == "see meeting with quarterly review team with quarterly figures"
    )
    assert sh.expand("mtg, ok?") == "meeting with quarterly review team, ok?"
    assert sh.expand("unknown stays") == "unknown stays"  # graceful degradation
    sh2 = tironian.Shorthand.from_dict(sh.to_dict())
    assert sh2.expand("mtg") == "meeting with quarterly review team"


def test_tironian_deny_closed():
    sh = tironian.Shorthand()
    sh.define("mtg", "meeting")
    with pytest.raises(ValueError):
        sh.define("mtg", "different")  # collision
    with pytest.raises(ValueError):
        sh.define("mt", "other")  # prefix ambiguity
    with pytest.raises(ValueError):
        sh.define("has space", "x")
    with pytest.raises(ValueError):
        sh.define_compound("-q", "no placeholder")
    assert tironian.Shorthand.suggest("quarterly business review") == "qbr"
    # collision -> consonant-skeleton fallback, deterministic
    fb = tironian.Shorthand.suggest("quarterly business review", {"qbr"})
    assert fb != "qbr" and fb == tironian.Shorthand.suggest(
        "quarterly business review", {"qbr"}
    )


# ---- commonplace ------------------------------------------------------------


def test_commonplace_capture_index_audit(home):
    book = commonplace.CommonplaceBook()
    book.capture(
        "Habit",
        commonplace.Excerpt(
            text="We are what we repeatedly do.",
            source="Aristotle (attrib.)",
            note="on practice",
        ),
    )
    book.capture("Habit", commonplace.Excerpt(text="Another habit note", source="me"))
    book.capture("Habit formation", commonplace.Excerpt(text="x", source="y"))
    idx = book.index()
    assert idx["H"] == ["Habit", "Habit formation"]
    assert len(book.retrieve("habit")) == 2  # case-insensitive head lookup
    hits = book.search("repeatedly")
    assert len(hits) == 1 and hits[0][0] == "Habit"
    audit = book.audit_heads()
    assert any(
        "Habit" in s for s in audit["merge_candidates"]
    )  # lexical overlap flagged
    book.save()
    book2 = commonplace.CommonplaceBook()
    assert len(book2.retrieve("Habit")) == 2


def test_commonplace_deny_closed(home):
    book = commonplace.CommonplaceBook()
    book.add_head("Virtue")
    with pytest.raises(ValueError):
        book.add_head("virtue")  # duplicate (case-insensitive)
    with pytest.raises(KeyError):
        book.retrieve("nope")
    with pytest.raises(ValueError):
        book.capture("H", commonplace.Excerpt(text="  "))
    with pytest.raises(ValueError):
        book.search("  ")


# ---- florilegia --------------------------------------------------------------


def test_florilegia_provenance_chain(home):
    fl = florilegia.Florilegium("dicta")
    fl.gather(
        florilegia.Excerpt(
            passage="Justice too long delayed is justice denied.",
            source="Gladstone, speech",
            head="justice",
            confidence="high",
        )
    )
    fl.gather(
        florilegia.Excerpt(
            passage="borrowed line",
            source="Aristotle",
            head="justice",
            second_hand=True,
            second_hand_from="Some Other Florilegium",
        )
    )
    assert fl.heads() == ["justice"]
    assert len(fl.needs_verification()) == 1  # florilegia-of-florilegia audit
    assert "SECOND-HAND" in fl.render()
    fl.save()
    fl2 = florilegia.Florilegium("dicta")
    assert len(fl2.excerpts) == 2


def test_florilegia_deny_closed(home):
    fl = florilegia.Florilegium("f2")
    with pytest.raises(ValueError):
        fl.gather(
            florilegia.Excerpt(passage="x", source="s", head="h", second_hand=True)
        )  # unnamed second-hand source
    with pytest.raises(ValueError):
        fl.gather(florilegia.Excerpt(passage="", source="s", head="h"))
