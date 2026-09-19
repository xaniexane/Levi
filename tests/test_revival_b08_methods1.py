"""Tests for LEVI revival methods batch 1 (B08): loci, combart, wheels,
pinakes, tironian, commonplace, florilegia, triplebook."""

from __future__ import annotations

import pytest

from core.levi.revival import loci, combart, wheels, pinakes, tironian
from core.levi.revival import commonplace, florilegia, triplebook


# ---------------------------------------------------------------------------
# 1. loci — Method of Loci
# ---------------------------------------------------------------------------


def _route() -> loci.Route:
    r = loci.Route("morning walk")
    r.add_locus("gate", "the iron gate")
    r.add_locus("fountain", "the old fountain")
    r.add_locus("oak", "the big oak")
    r.deposit("gate", "a burning key", "api key rotated")
    r.deposit("fountain", "coins melting", "budget cut 12%")
    r.deposit("oak", "a nesting clock", "deadline friday")
    return r


def test_loci_recall_order():
    r = _route()
    facts = [fact for _, fact in r.recall()]
    assert facts == ["api key rotated", "budget cut 12%", "deadline friday"]


def test_loci_forgetting_and_revisit():
    r = _route()
    # decay the fountain by walking without revisiting it
    for _ in range(9):
        r.recall()
    assert r.strength("fountain") < loci.FORGET_THRESHOLD
    assert "fountain" in r.forgetting_loci()
    with pytest.raises(loci.Forgotten):
        r.recall_vivid("fountain")
    # revisiting restores it
    r.revisit("fountain")
    assert r.strength("fountain") == 1.0
    image, fact = r.recall_vivid("fountain")
    assert image == "coins melting" and fact == "budget cut 12%"


def test_loci_round_trip():
    r = _route()
    r2 = loci.Route.from_dict(r.to_dict())
    assert [loc.name for loc in r2.loci] == ["gate", "fountain", "oak"]
    assert [fact for _, fact in r2.recall()] == [
        "api key rotated",
        "budget cut 12%",
        "deadline friday",
    ]


# ---------------------------------------------------------------------------
# 2. combart — combinatorial ideation
# ---------------------------------------------------------------------------


def test_combart_enumeration_is_deterministic():
    primitives = ["memory", "dream", "machine"]
    first = combart.enumerate_combinations(primitives, 2)
    second = combart.enumerate_combinations(list(reversed(primitives)), 2)
    assert first == second
    assert len(first) == 3  # C(3,2)


def test_combart_judge_marks_meaningful_set():
    judge = combart.pair_judge([["dream", "machine"]])
    result = combart.run(["memory", "dream", "machine"], 2, judge)
    assert result.total == 3
    assert result.judged == 1
    assert result.meaningful == [("dream", "machine")]
    rep = combart.report(result)
    assert rep["meaningful_count"] == 1


def test_combart_thematic_judge():
    judge = combart.thematic_judge(["memory"])
    result = combart.run(["memory", "dream", "machine"], 2, judge)
    assert result.judged == 2
    assert all("memory" in combo for combo in result.meaningful)


def test_combart_rejects_bad_k():
    with pytest.raises(ValueError):
        combart.enumerate_combinations(["a", "b"], 3)


# ---------------------------------------------------------------------------
# 3. wheels — concentric memory wheels
# ---------------------------------------------------------------------------


def _wheels() -> wheels.Wheels:
    return wheels.Wheels.build(
        [
            ("agent", ["memory", "dream", "will"], 1),
            ("tool", ["search", "write", "run"], 1),
            ("mood", ["calm", "sharp", "playful"], 2),
        ]
    )


def test_wheels_alignment_and_rotation():
    w = _wheels()
    assert w.alignment(0) == {"agent": "memory", "tool": "search", "mood": "calm"}
    assert w.alignment(1) == {"agent": "dream", "tool": "write", "mood": "playful"}
    # full rotation returns to the start configuration
    assert w.configuration_at(3) == w.configuration_at(0)


def test_wheels_sweep_covers_all_configurations():
    w = _wheels()
    swept = w.sweep()
    assert len(swept) == 3
    assert len({tuple(sorted(d.items())) for d in swept}) == 3


def test_wheels_proximity_by_alignment():
    w = _wheels()
    rots = w.query("memory", "agent", "tool")
    assert rots == [0]  # memory sits at the spoke only at rotation 0
    partners = w.partners_of("dream", "agent", "mood")
    assert partners == ["playful"]  # dream aligns with playful at rotation 1
    assert w.coaligned("will", "agent", 2)["tool"] == "run"


# ---------------------------------------------------------------------------
# 4. pinakes — critical annotated catalog
# ---------------------------------------------------------------------------


def _pinax() -> pinakes.Pinax:
    p = pinakes.Pinax()
    p.add(
        pinakes.Entry(
            title="On Memory",
            author="The Archivist",
            rating=5,
            context="Foundational treatise on the art of recollection.",
            tags=["memory", "method"],
            see_also=["Commonplacing"],
            authentic="genuine",
        )
    )
    p.add(
        pinakes.Entry(
            title="Commonplacing",
            author="The Clerk",
            rating=4,
            context="Practical guide to keeping a commonplace book.",
            tags=["method", "writing"],
            authentic="unknown",
        )
    )
    p.add(
        pinakes.Entry(
            title="Dubious Pamphlet",
            author="Anonymous",
            rating=1,
            context="Unverifiable claims about instant recall.",
            tags=["memory"],
            authentic="dubious",
        )
    )
    return p


def test_pinakes_search_returns_entries_with_judgments():
    p = _pinax()
    hits = p.search("memory")
    assert len(hits) == 2
    # best first: the 5-star entry leads
    assert hits[0].title == "On Memory"
    assert hits[0].judgment()["rating"] == 5
    assert hits[1].judgment()["authentic"] == "dubious"


def test_pinakes_flag_and_genuine_shelf():
    p = _pinax()
    p.flag("Commonplacing", "genuine", "verified against the manuscript")
    assert p.evaluate("Commonplacing")["authentic"] == "genuine"
    assert "verified against the manuscript" in p.get("Commonplacing").context
    genuine = {e.title for e in p.genuine_only()}
    assert genuine == {"On Memory", "Commonplacing"}


def test_pinakes_cross_references_and_quality_shelf():
    p = _pinax()
    refs = p.cross_references("On Memory")
    assert [e.title for e in refs] == ["Commonplacing"]
    shelf = p.of_rating(4)
    assert [e.title for e in shelf] == ["On Memory", "Commonplacing"]
    with pytest.raises(KeyError):
        p.evaluate("No Such Work")


# ---------------------------------------------------------------------------
# 5. tironian — productive shorthand
# ---------------------------------------------------------------------------


def test_tironian_encode_known_vocabulary():
    stream = tironian.encode("I do not know")
    assert stream.unknown_words == []
    assert stream.coverage == 1.0
    assert "→" not in stream.text()  # 'to' is absent; sanity on marks
    assert "¬" in stream.text()  # not
    assert "kn" in stream.text()  # know -> root mark


def test_tironian_compounding_rule():
    stream = tironian.encode("thinking")
    assert stream.text() == "thⁿᵍ"  # ROOT+SUFFIX: think + ing
    assert tironian.decode(stream) == "thinking"


def test_tironian_degrades_gracefully_on_unseen_words():
    stream = tironian.encode("the quixotic zebra")
    assert "quixotic" in stream.unknown_words
    assert "zebra" in stream.unknown_words
    assert "⟦quixotic⟧" in stream.text()
    assert "⟦zebra⟧" in stream.text()
    # decode keeps fluency: unknowns come back verbatim, nothing raises
    back = tironian.decode(stream)
    assert "quixotic" in back and "zebra" in back


def test_tironian_round_trip_fidelity():
    assert tironian.fidelity("I do not know the time") == 1.0
    # contracted unknown stems are lossy by design: xylophoning -> xylphn+ing
    assert tironian.fidelity("the xylophoning zebra") < 1.0


# ---------------------------------------------------------------------------
# 6. commonplace — capture + grid index
# ---------------------------------------------------------------------------


def _book() -> commonplace.Commonplace:
    b = commonplace.Commonplace()
    b.capture("Memory", "We remember places, not lists.", source="field notes")
    b.capture("Memory", "Revisit or lose.", reflection="decay is honest")
    b.capture("Craft", "Sharp tools, calm hands.", source="workshop")
    return b


def test_commonplace_lookup_beats_rereading():
    b = _book()
    hits = b.lookup("memory")
    assert len(hits) == 2
    assert all(h.head == "Memory" for h in hits)
    assert hits[0].excerpt == "We remember places, not lists."
    # the grid routed it: bucket -> head -> entry numbers
    bucket = commonplace.bucket_code("Memory")
    assert b.grid()[bucket]["Memory"] == [0, 1]


def test_commonplace_heads_evolve_and_rehead_moves():
    b = _book()
    b.ensure_head("Forgetting", rationale="decay deserves its own head")
    b.rehead(1, "Forgetting")
    assert b.lookup("forgetting")[0].seq == 1
    assert b.lookup("memory") == [b._by_seq(0)]
    assert "Forgetting" in b.heads()


def test_commonplace_append_only_sequence():
    b = _book()
    assert b.entry_count() == 3
    e = b.capture("Memory", "A fourth note.")
    assert e.seq == 3  # nothing rewritten: the new entry takes the next number
    assert b.entry_count() == 4


# ---------------------------------------------------------------------------
# 7. florilegia — curated excerpt canon
# ---------------------------------------------------------------------------


def _florilegium() -> florilegia.Florilegium:
    f = florilegia.Florilegium()
    f.gather(
        "We remember places, not lists.",
        topics=["memory", "method"],
        provenance=florilegia.Provenance(
            author="The Archivist",
            work="On Memory",
            locator="ch.1",
            collected_by="levi",
        ),
    )
    f.gather(
        "Revisit or lose: decay is honest.",
        topics=["memory"],
        provenance=florilegia.Provenance(
            author="The Clerk",
            work="Commonplacing",
            collected_by="levi",
        ),
    )
    return f


def test_florilegia_indexed_retrieval_without_the_library():
    f = _florilegium()
    assert len(f.by_topic("memory")) == 2
    assert len(f.by_topic("method")) == 1
    assert len(f.by_author("the archivist")) == 1
    assert len(f.search("decay")) == 1
    assert f.topics() == ["memory", "method"]


def test_florilegia_provenance_survives():
    f = _florilegium()
    excerpt = f.by_topic("method")[0]
    assert "The Archivist" in excerpt.provenance.citation()
    assert "ch.1" in excerpt.provenance.citation()
    assert "gathered by levi" in excerpt.provenance.citation()


def test_florilegia_canon_is_curated_order():
    f = _florilegium()
    canon = f.canon("first principles", rationale="what the community keeps")
    canon.curate(1)  # deliberate order: the clerk's line first
    canon.curate(0)
    rendered = f.canon_text("first principles")
    assert [r["text"] for r in rendered] == [
        "Revisit or lose: decay is honest.",
        "We remember places, not lists.",
    ]
    assert all(r["citation"] for r in rendered)
    with pytest.raises(KeyError):
        f.canon_text("no such canon")


# ---------------------------------------------------------------------------
# 8. triplebook — triple-book accounting
# ---------------------------------------------------------------------------


def _books() -> triplebook.TripleBook:
    b = triplebook.TripleBook()
    b.jot("sold a story draft to the press")
    b.record(
        "sale of draft",
        debits=[("cash", 5000)],
        credits=[("income", 5000)],
    )
    b.record(
        "paper and ink",
        debits=[("expense", 800)],
        credits=[("cash", 800)],
    )
    return b


def test_triplebook_records_balanced_entries():
    b = _books()
    assert b.account_balance("cash") == 4200
    assert b.account_balance("income") == -5000  # net credit
    assert b.account_balance("expense") == 800
    assert len(b.memoriale) == 1  # the raw jot stays at level 1
    assert len(b.giornale) == 2


def test_triplebook_refuses_unbalanced_entry_with_offender():
    b = triplebook.TripleBook()
    with pytest.raises(triplebook.UnbalancedEntry) as exc:
        b.record(
            "cookery",
            debits=[("cash", 1000)],
            credits=[("income", 900)],
        )
    assert exc.value.entry.narration == "cookery"
    assert len(b.giornale) == 0  # the offender was never stored


def test_triplebook_trial_balance_verifies():
    b = _books()
    tb = b.trial_balance()
    assert tb["balanced"] is True
    assert tb["total_debits"] == tb["total_credits"] == 5800


def test_triplebook_close_carries_to_equity():
    b = _books()
    b.close("income", "expense", "equity")
    tb = b.trial_balance()
    assert tb["balanced"] is True
    assert b.account_balance("income") == 0
    assert b.account_balance("expense") == 0
    assert b.account_balance("equity") == -4200  # profit as net credit
