"""Hermetic tests for forgotten-methods batch B09 (methods 2: indexing & attention).

Modules: edgeindex, peekaboo, uniterm, colonclass, mundaneum, kardex,
tickler, ivy6.

Hermetic: no network, deterministic, all persistence under tmp_path.
Stdlib only.
"""

from datetime import date

import pytest

from levi.revival import (
    colonclass,
    edgeindex,
    ivy6,
    kardex,
    mundaneum,
    peekaboo,
    tickler,
    uniterm,
)


# ===========================================================================
# edgeindex — post-coordinate indexing, the needle-shake
# ===========================================================================


def test_edgeindex_tag_after_collection_and_shake_and():
    deck = edgeindex.EdgeIndex()
    deck.add_document("d1", "pricing memo")
    deck.add_document("d2", "pricing negotiation")
    deck.add_document("d3", "hiring plan")
    # Tagging happens AFTER collection: cards filed first, notched later.
    deck.tag("d1", "pricing", "2024")
    deck.tag("d2", "pricing", "negotiation", "2024")
    deck.tag("d3", "hiring", "2024")
    assert deck.shake(require=("pricing", "negotiation")) == ["d2"]
    assert deck.shake(require=("2024",)) == ["d1", "d2", "d3"]


def test_edgeindex_or_not_and_explained_shake():
    deck = edgeindex.EdgeIndex()
    deck.add_document("d1")
    deck.add_document("d2")
    deck.add_document("d3")
    deck.tag("d1", "alpha")
    deck.tag("d2", "alpha", "beta")
    deck.tag("d3", "beta")
    assert deck.shake(any_of=("alpha", "beta")) == ["d1", "d2", "d3"]
    assert deck.shake(require=("alpha",), exclude=("beta",)) == ["d1"]
    explained = deck.shake_with_explain(require=("alpha",), exclude=("beta",))
    assert explained["fell"] == ["d1"]
    assert explained["deck_size"] == 3
    roles = {n["feature"]: n["role"] for n in explained["needles"]}
    assert roles == {"alpha": "AND", "beta": "NOT"}


def test_edgeindex_unknown_feature_and_untag():
    deck = edgeindex.EdgeIndex()
    deck.add_document("d1")
    with pytest.raises(edgeindex.UnknownFeature):
        deck.shake(require=("nope",))
    with pytest.raises(edgeindex.UnknownDocument):
        deck.tag("ghost", "alpha")
    deck.tag("d1", "alpha")
    deck.untag("d1", "alpha")
    assert deck.card_features("d1") == set()
    assert deck.shake(require=("alpha",)) == []


def test_edgeindex_persistence_round_trip(tmp_path):
    deck = edgeindex.EdgeIndex(tmp_path / "deck")
    deck.add_document("d1", "memo")
    deck.tag("d1", "pricing", "2024")
    deck.save()
    again = edgeindex.EdgeIndex(tmp_path / "deck")
    assert again.card_features("d1") == {"pricing", "2024"}
    assert again.shake(require=("pricing",)) == ["d1"]


# ===========================================================================
# peekaboo — optical coincidence, the inspectable stack
# ===========================================================================


def _post_sample():
    deck = peekaboo.PeekABooDeck()
    deck.post("d1", "cognitive load and worked examples", "paper one")
    deck.post("d2", "cognitive load in classrooms", "paper two")
    deck.post("d3", "worked examples for algebra", "paper three")
    return deck


def test_peekaboo_term_records_list_positions():
    deck = _post_sample()
    assert deck.term_record("cognitive") == ["d1", "d2"]
    assert deck.term_record("examples") == ["d1", "d3"]
    assert deck.term_record("absent") == []
    assert deck.term_positions("load", "d1") == [1]


def test_peekaboo_stack_shows_intermediate_coincidence():
    deck = _post_sample()
    result = deck.stack(["cognitive", "load", "examples"])
    stages = result["stages"]
    assert [s["term"] for s in stages] == ["cognitive", "load", "examples"]
    assert stages[0]["still_lit"] == ["d1", "d2"]
    assert stages[1]["still_lit"] == ["d1", "d2"]
    assert stages[2]["still_lit"] == ["d1"]
    assert result["coincidence"] == ["d1"]
    assert deck.coincide(["worked", "examples"]) == ["d1", "d3"]


def test_peekaboo_remove_withdraws_positions():
    deck = _post_sample()
    deck.remove("d1")
    assert deck.term_record("cognitive") == ["d2"]
    assert deck.coincide(["cognitive", "examples"]) == []
    with pytest.raises(peekaboo.UnknownDocument):
        deck.remove("d1")


def test_peekaboo_persistence_round_trip(tmp_path):
    deck = peekaboo.PeekABooDeck(tmp_path / "deck")
    deck.post("d1", "cognitive load", "t")
    deck.save()
    again = peekaboo.PeekABooDeck(tmp_path / "deck")
    assert again.term_record("cognitive") == ["d1"]
    assert again.terms() == ["cognitive", "load"]


# ===========================================================================
# uniterm — uncontrolled terms, explicit Boolean core
# ===========================================================================


def _index_sample():
    f = uniterm.UnitermFile()
    f.index("d1", "grant deadline proposal draft", "proposal")
    f.index("d2", "grant rejected appeal letter", "appeal")
    f.index("d3", "deadline report summary", "report")
    return f


def test_uniterm_parse_produces_readable_tree():
    tree = uniterm.parse_query("deadline AND grant NOT rejected")
    assert tree.read() == "((deadline AND grant) AND NOT rejected)"
    assert tree.terms() == {"deadline", "grant", "rejected"}
    implicit = uniterm.parse_query("grant deadline")
    assert implicit.read() == "(grant AND deadline)"
    grouped = uniterm.parse_query("(grant OR deadline) AND report")
    assert grouped.read() == "((grant OR deadline) AND report)"


def test_uniterm_coordinate_shows_inspectable_core():
    f = _index_sample()
    result = f.coordinate("deadline AND grant NOT rejected")
    assert result["tree"] == "((deadline AND grant) AND NOT rejected)"
    assert result["matches"] == ["d1"]
    assert result["per_term"]["grant"] == ["d1", "d2"]
    assert result["why"] == {"d1": ["deadline", "grant"]}
    assert result["titles"] == {"d1": "proposal"}


def test_uniterm_not_and_syntax_errors():
    f = _index_sample()
    assert f.coordinate("NOT rejected")["matches"] == ["d1", "d3"]
    with pytest.raises(uniterm.QuerySyntaxError):
        uniterm.parse_query("")
    with pytest.raises(uniterm.QuerySyntaxError):
        uniterm.parse_query("grant AND")
    with pytest.raises(uniterm.QuerySyntaxError):
        uniterm.parse_query("(grant")


def test_uniterm_unindex_and_persistence(tmp_path):
    f = uniterm.UnitermFile(tmp_path / "u")
    f.index("d1", "grant deadline", "t")
    f.unindex("d1")
    assert f.vocabulary() == []
    assert f.coordinate("grant")["matches"] == []
    with pytest.raises(uniterm.UnitermError):
        f.unindex("d1")
    f.index("d2", "grant deadline", "t2")
    f.save()
    again = uniterm.UnitermFile(tmp_path / "u")
    assert again.coordinate("grant AND deadline")["matches"] == ["d2"]


# ===========================================================================
# colonclass — PMEST faceted synthesis
# ===========================================================================


def test_colonclass_synthesize_facet_ordered():
    notation = colonclass.synthesize(
        time="1950",
        space="India",
        energy="Treatment",
        matter="Disease",
        personality="Medicine",
    )
    assert notation == "Medicine:Disease:Treatment:India:1950"
    # Single letters and lowercase spellings work too.
    assert colonclass.synthesize(P="Medicine", T="1950") == "Medicine:1950"
    assert colonclass.synthesize(personality="Medicine") == "Medicine"
    with pytest.raises(ValueError):
        colonclass.synthesize()
    with pytest.raises(ValueError):
        colonclass.synthesize(unknown="x")


def test_colonclass_parse_round_trip():
    parsed = colonclass.parse("Medicine:Disease:Treatment:India:1950")
    assert parsed == {
        "P": "Medicine",
        "M": "Disease",
        "E": "Treatment",
        "S": "India",
        "T": "1950",
    }
    multi = colonclass.parse("Medicine:Disease;Tissue:Treatment")
    assert multi["M"] == ["Disease", "Tissue"]
    with pytest.raises(colonclass.NotationError):
        colonclass.parse("")
    with pytest.raises(ValueError):
        colonclass.synthesize(personality="a:b")  # separator refused


def test_colonclass_catalog_and_facet_pivot():
    cat = colonclass.ColonClass()
    cat.define("Energy", "Treatment", "Diagnosis")
    n1 = cat.catalog(
        "tb paper",
        personality="Medicine",
        matter="Disease",
        energy="Treatment",
        space="India",
        time="1950",
    )
    n2 = cat.catalog(
        "tb survey",
        personality="Medicine",
        matter="Disease",
        energy="Diagnosis",
        space="India",
        time="1960",
    )
    assert n1 == "Medicine:Disease:Treatment:India:1950"
    assert cat.notation_of("tb paper") == n1
    assert cat.subjects_in_facet("Space", "India") == ["tb paper", "tb survey"]
    assert cat.subjects_in_facet("E", "Treatment") == ["tb paper"]
    assert n2 != n1
    with pytest.raises(colonclass.ColonClassError):
        cat.notation_of("missing")


def test_colonclass_adhoc_values_and_persistence(tmp_path):
    cat = colonclass.ColonClass(tmp_path / "cc")
    # Ad-hoc values need no registration: synthesis is never pre-enumerated.
    n = cat.catalog("wild", personality="Xenobiology", time="2150")
    assert n == "Xenobiology:2150"
    cat.save()
    again = colonclass.ColonClass(tmp_path / "cc")
    assert again.notation_of("wild") == "Xenobiology:2150"


# ===========================================================================
# mundaneum — facts, typed relations, the query service
# ===========================================================================


def _store_sample():
    store = mundaneum.Mundaneum()
    store.record_fact("remote-work", "extends", "deep work blocks", "note-1")
    store.record_fact(
        "remote-work", "contradicts", "office presence required", "note-2"
    )
    store.record_fact("remote-work", "contradicts", "async is sufficient", "note-3")
    return store


def test_mundaneum_fact_requires_relation_and_source():
    store = mundaneum.Mundaneum()
    fact = store.record_fact("x", "causes", "y", "src-1", note="n")
    assert fact.fact_id == "f1"
    assert store.get_fact("f1").obj == "y"
    with pytest.raises(mundaneum.UnknownRelation):
        store.record_fact("x", "vibes_with", "y", "src")
    with pytest.raises(ValueError):
        store.record_fact("x", "causes", "y", "  ")
    with pytest.raises(mundaneum.UnknownFact):
        store.get_fact("f99")
    store.define_relation("predicts", inverse="predicted_by")
    assert "predicts" in store.relation_types()
    store.record_fact("x", "predicts", "z", "src-2")


def test_mundaneum_relations_between_subjects():
    store = _store_sample()
    about = store.facts_about("remote-work")
    assert len(about) == 3
    assert len(store.facts_about("remote-work", "contradicts")) == 2
    between = store.relations_between("remote-work", "deep work blocks")
    assert [f.relation for f in between] == ["extends"]
    assert store.subjects() == ["remote-work"]
    assert store.fact_count() == 3


def test_mundaneum_service_synthesizes_and_flags_conflicts():
    service = mundaneum.MundaneumService(_store_sample())
    answer = service.answer("remote-work")
    assert set(answer.grouped) == {"extends", "contradicts"}
    assert len(answer.conflicts) == 1  # the two contradicting claims
    rendered = answer.render()
    assert "disagrees" in rendered
    assert "note-2" in rendered and "note-3" in rendered
    assert "deep work blocks" in rendered
    empty = service.answer("nothing-here")
    assert "nothing recorded" in empty.render()


def test_mundaneum_persistence_round_trip(tmp_path):
    store = mundaneum.Mundaneum(tmp_path / "m")
    store.record_fact("a", "causes", "b", "src")
    store.save()
    again = mundaneum.Mundaneum(tmp_path / "m")
    assert again.facts_about("a")[0].obj == "b"
    assert again.fact_count() == 1


# ===========================================================================
# kardex — the visible file: ambient strips, one-swap updates
# ===========================================================================


def test_kardex_board_is_ambiently_legible():
    kx = kardex.Kardex()
    kx.add_record("sub-1", "streaming", "ACTIVE")
    kx.add_record("sub-2", "domain", "EXPIRES-SOON")
    board = kx.board()
    assert board == [
        {"rec_id": "sub-1", "label": "streaming", "status": "ACTIVE"},
        {"rec_id": "sub-2", "label": "domain", "status": "EXPIRES-SOON"},
    ]
    with pytest.raises(kardex.DuplicateRecord):
        kx.add_record("sub-1", "dup", "ACTIVE")
    with pytest.raises(kardex.UnknownRecord):
        kx.get("ghost")


def test_kardex_single_swap_update_and_strip_history():
    kx = kardex.Kardex()
    kx.add_record("r1", "pipeline", "LEAD", detail="big client")
    kx.update_status("r1", "NEGOTIATING")
    assert kx.get("r1").status == "NEGOTIATING"
    kx.update_status("r1", "NEGOTIATING")  # no-op: history untouched
    history = kx.history("r1")
    assert len(history) == 1
    assert (history[0].old, history[0].new) == ("LEAD", "NEGOTIATING")
    kx.update_status("r1", "WON")
    assert [e.new for e in kx.history("r1")] == ["NEGOTIATING", "WON"]
    with pytest.raises(ValueError):
        kx.update_status("r1", "  ")


def test_kardex_needs_attention_flags_red_strips():
    kx = kardex.Kardex()
    kx.add_record("a", "meds", "OK")
    kx.add_record("b", "meds", "OVERDUE")
    kx.add_record("c", "meds", "LOW")
    flagged = kx.needs_attention(lambda r: r.status in ("OVERDUE", "LOW"))
    assert [s["rec_id"] for s in flagged] == ["b", "c"]
    removed = kx.remove_record("c")
    assert removed.rec_id == "c"
    assert kx.record_count() == 2


def test_kardex_persistence_round_trip(tmp_path):
    kx = kardex.Kardex(tmp_path / "k")
    kx.add_record("r1", "label", "ACTIVE")
    kx.update_status("r1", "PAUSED")
    kx.save()
    again = kardex.Kardex(tmp_path / "k")
    assert again.get("r1").status == "PAUSED"
    assert len(again.history("r1")) == 1


# ===========================================================================
# tickler — the 43 folders, perpetual rotation
# ===========================================================================


def test_tickler_daily_and_monthly_filing():
    tf = tickler.TicklerFile(today=date(2026, 9, 16))
    tf.file("pay rent", date(2026, 9, 20), context="landlord email")
    tf.file("renew passport", date(2027, 1, 5), context="expires March")
    status = tf.status()
    assert list(status["daily_folders"]) == ["2026-09-20"]
    assert list(status["monthly_folders"]) == ["2027-01"]
    assert tf.pending_count() == 2
    with pytest.raises(ValueError):
        tf.file("late", date(2026, 9, 15))
    with pytest.raises(ValueError):
        tf.file("  ", date(2026, 9, 20))


def test_tickler_today_resurfaces_with_context_and_clears():
    tf = tickler.TicklerFile(today=date(2026, 9, 16))
    tf.file("call dentist", date(2026, 9, 16), context="tooth hurts since Tue")
    peeked = tf.peek_today()
    assert len(peeked) == 1  # peek does not empty the folder
    surfaced = tf.today()
    assert len(surfaced) == 1
    item = surfaced[0]
    assert item["text"] == "call dentist"
    assert item["context"] == "tooth hurts since Tue"
    assert item["overdue"] is False
    assert tf.today() == []  # folder emptied
    assert tf.pending_count() == 0


def test_tickler_advance_rolls_monthly_and_marks_overdue():
    tf = tickler.TicklerFile(today=date(2026, 9, 16))
    tf.file("november review", date(2026, 11, 1), context="quarterly")
    tf.file("missed", date(2026, 9, 16))
    tf.advance(46)  # to 2026-11-01: the monthly folder rolls into daily
    assert tf.today_date == date(2026, 11, 1)
    surfaced = tf.today()
    by_text = {i["text"]: i for i in surfaced}
    assert by_text["november review"]["overdue"] is False
    assert by_text["missed"]["overdue"] is True  # skipped day-folder, not dropped
    with pytest.raises(ValueError):
        tf.advance(-1)


def test_tickler_persistence_round_trip(tmp_path):
    tf = tickler.TicklerFile(tmp_path / "t", today=date(2026, 9, 16))
    tf.file("pay rent", date(2026, 9, 20), context="c")
    tf.file("far", date(2027, 2, 1))
    tf.save()
    again = tickler.TicklerFile(tmp_path / "t")
    assert again.today_date == date(2026, 9, 16)
    assert again.pending_count() == 2


# ===========================================================================
# ivy6 — capacity cap, total order, sequential reveal
# ===========================================================================


def test_ivy6_cap_and_total_order_and_sequential_reveal():
    day = ivy6.IvyLeeDay()
    with pytest.raises(ValueError):
        day.plan([f"t{i}" for i in range(7)])  # seven is refused, not squeezed
    assert day.plan(["write", "call", "ship"]) == ["write", "call", "ship"]
    assert day.current() == "write"  # ONLY the current task is revealed
    assert day.remaining() == 3
    assert day.complete() == "call"
    assert day.complete() == "ship"
    assert day.complete() is None
    assert day.is_done()
    assert day.current() is None


def test_ivy6_defer_rolls_to_end_of_day():
    day = ivy6.IvyLeeDay()
    day.plan(["a", "b"])
    assert day.defer() == "b"  # a deliberately set aside, b revealed
    assert day.complete() is None
    report = day.end_day()
    assert report == {"completed": ["b"], "unfinished": ["a"]}
    assert day.phase == "plan"  # ready for tomorrow's planning


def test_ivy6_phases_separate_planning_from_work():
    day = ivy6.IvyLeeDay()
    with pytest.raises(ivy6.PhaseError):
        day.current()  # nothing planned yet
    with pytest.raises(ivy6.PhaseError):
        day.end_day()
    day.plan(["a"])
    with pytest.raises(ivy6.PhaseError):
        day.plan(["b"])  # planning moment is over once work begins
    with pytest.raises(ValueError):
        ivy6.IvyLeeDay().plan([])
    with pytest.raises(ValueError):
        ivy6.IvyLeeDay().plan(["a", "a"])  # duplicates refused


def test_ivy6_roll_forward_carries_unfinished(tmp_path):
    day = ivy6.IvyLeeDay(tmp_path / "day")
    day.plan(["a", "b", "c"])
    day.complete()  # a done; b, c unfinished
    unfinished = day.end_day()["unfinished"]
    assert unfinished == ["b", "c"]
    tomorrow = ivy6.IvyLeeDay()
    assert tomorrow.roll_forward(unfinished, ["d"]) == ["b", "c", "d"]
    assert tomorrow.current() == "b"
    day.save()
    resumed = ivy6.IvyLeeDay(tmp_path / "day")
    assert resumed.phase == "plan"  # end_day had reset it
