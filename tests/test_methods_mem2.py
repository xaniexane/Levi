"""Hermetic tests for core.levi.methods (memory & retrieval systems, part 2).

triplebook, edgenotch, optical, uniterm, colon, mundaneum, kardex.
Isolated HOME via LEVI_HOME=tmp_path; no network; deterministic.
"""

from __future__ import annotations

import pytest

from core.levi.methods import (
    colon,
    edgenotch,
    kardex,
    mundaneum,
    optical,
    triplebook,
    uniterm,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


# ---- triplebook ------------------------------------------------------------


def test_triplebook_dual_entry_and_trial_balance(home):
    tb = triplebook.TripleBook()
    c0 = tb.jot("call dentist", captured="2026-09-15")
    tb.post(
        triplebook.JournalEntry(
            narrative="dentist call",
            debit_account="calendar:morning",
            credit_account="project:health",
            amount=1.0,
        ),
        from_capture=c0,
    )
    # unbalanced: a commitment with time but no project on the other side yet
    tb.post(
        triplebook.JournalEntry(
            narrative="write report",
            debit_account="calendar:afternoon",
            credit_account="project:report",
        )
    )
    bal = tb.balances()
    assert bal["calendar:morning"] == 1.0 and bal["project:health"] == -1.0
    trial = tb.trial_balance()
    assert trial["balanced"] is True  # books agree mechanically…
    assert (
        "calendar:morning" in trial["unbalanced_accounts"]
    )  # …but accounts don't net out
    assert trial["unposted_captures"] == []  # c0 was posted
    c1 = tb.jot("unposted stray thought")
    assert tb.trial_balance()["unposted_captures"] == [c1]
    tb.save()
    tb2 = triplebook.TripleBook()
    assert len(tb2.giornale) == 2 and len(tb2.memoriale) == 2


def test_triplebook_deny_closed(home):
    tb = triplebook.TripleBook()
    with pytest.raises(ValueError):
        tb.jot("   ")
    with pytest.raises(ValueError):
        tb.post(
            triplebook.JournalEntry(
                narrative="x", debit_account="a", credit_account="a"
            )
        )  # duality: must differ
    with pytest.raises(ValueError):
        tb.post(
            triplebook.JournalEntry(
                narrative="x", debit_account="a", credit_account="b", amount=0
            )
        )
    with pytest.raises(IndexError):
        tb.post(
            triplebook.JournalEntry(
                narrative="x", debit_account="a", credit_account="b"
            ),
            from_capture=99,
        )


# ---- edgenotch --------------------------------------------------------------


def test_edgenotch_needle_sort():
    deck = edgenotch.Deck()
    deck.add_card("n1", "pricing memo", ["negotiation", "pricing", "2024"])
    deck.add_card("n2", "roadmap", ["planning", "2024"])
    deck.add_card("n3", "old pricing", ["pricing", "2023"])
    hits = deck.query(["negotiation", "pricing"])  # AND: two needles
    assert [c.item_id for c in hits] == ["n1"]
    hits = deck.query(["pricing"], op="OR")
    assert [c.item_id for c in hits] == ["n1", "n3"]
    hits = deck.query(["pricing"], op="NOT")
    assert [c.item_id for c in hits] == ["n2"]
    deck.notch("n2", "pricing")
    assert [c.item_id for c in deck.query(["pricing"])] == ["n1", "n2", "n3"]


def test_edgenotch_zatocoding_flagged():
    deck = edgenotch.Deck()
    deck.register_feature("alpha")
    deck.register_feature("beta", share_with="alpha")  # shared hole
    deck.add_card("c1", features=["alpha"])
    assert deck.may_false_drop(["beta"])  # honestly flagged: may false-drop
    assert [c.item_id for c in deck.query(["beta"])] == ["c1"]  # the false drop itself


def test_edgenotch_deny_closed():
    deck = edgenotch.Deck()
    with pytest.raises(KeyError):
        deck.query(["never-notched"])
    with pytest.raises(ValueError):
        deck.query(["x"], op="XOR")
    with pytest.raises(ValueError):
        deck.query([])
    deck.add_card("c1")
    with pytest.raises(ValueError):
        deck.add_card("c1")
    with pytest.raises(KeyError):
        deck.notch("missing", "f")


# ---- optical -----------------------------------------------------------------


def test_optical_coincidence_and_light_table():
    lt = optical.LightTable()
    lt.index_document("d1", ["cognitive load", "worked examples"])
    lt.index_document("d2", ["cognitive load"])
    lt.index_document("d3", ["worked examples", "testing effect"])
    assert lt.coincide(["cognitive load", "worked examples"]) == ["d1"]
    assert lt.coincide(["cognitive load"]) == ["d1", "d2"]
    assert lt.coincide(["nope"]) == []  # blank card blocks all light
    view = lt.view(["cognitive load", "worked examples"])
    assert "AND" in view and "d1" in view


def test_optical_deny_closed():
    lt = optical.LightTable()
    lt.index_document("d1", ["t"])
    with pytest.raises(ValueError):
        lt.index_document("d1", ["t"])  # duplicate doc
    with pytest.raises(KeyError):
        lt.punch("t", "ghost")
    with pytest.raises(ValueError):
        lt.coincide([])
    with pytest.raises(ValueError):
        lt.punch("  ", "d1")


# ---- uniterm -------------------------------------------------------------------


def test_uniterm_postcoordinate_search_with_trace():
    idx = uniterm.UnitermIndex()
    idx.add("e1", ["deadline", "grant", "proposal"], title="grant proposal")
    idx.add("e2", ["deadline", "grant", "rejected"], title="old grant")
    idx.add("e3", ["deadline", "invoice"], title="invoice")
    r = idx.search("deadline AND grant NOT rejected")
    assert r["doc_ids"] == ["e1"]
    assert r["coordination"] == "(('deadline' AND 'grant') AND NOT 'rejected')"
    assert "matched:" in r["trace"] and "e1" in r["trace"]
    r2 = idx.search("grant OR invoice")
    assert r2["doc_ids"] == ["e1", "e2", "e3"]
    r3 = idx.search("(grant OR invoice) AND deadline")
    assert r3["doc_ids"] == ["e1", "e2", "e3"]
    r4 = idx.search("cancer", synonyms={"cancer": ["neoplasm"]})
    assert r4["expanded_terms"] == {"cancer": ["neoplasm"]}  # expansion is explicit


def test_uniterm_deny_closed():
    idx = uniterm.UnitermIndex()
    idx.add("d1", ["a"])
    with pytest.raises(ValueError):
        idx.add("d1", ["b"])  # duplicate
    with pytest.raises(ValueError):
        idx.add("d2", [])  # termless document
    with pytest.raises(ValueError):
        idx.search("")
    with pytest.raises(ValueError):
        idx.search("a AND (b")  # unbalanced parens
    with pytest.raises(ValueError):
        idx.search("AND")


# ---- colon ---------------------------------------------------------------------


def test_colon_pmest_synthesis_and_pivot():
    clf = colon.ColonClassifier()
    n1 = clf.classify(
        "tb-cure",
        Personality="Medicine",
        Matter="Disease",
        Energy="Treatment",
        Space="India",
        Time="1950",
    )
    assert n1 == "Medicine:Disease:Treatment:India:1950"
    assert clf.parse(n1) == {
        "Personality": "Medicine",
        "Matter": "Disease",
        "Energy": "Treatment",
        "Space": "India",
        "Time": "1950",
    }
    clf.classify(
        "tb-prev",
        Personality="Medicine",
        Matter="Disease",
        Energy="Prevention",
        Space="India",
        Time="1950",
    )
    assert clf.pivot("Energy", "treatment") == ["tb-cure"]  # case-insensitive slice
    assert clf.pivot("Space", "India") == ["tb-cure", "tb-prev"]
    assert clf.facet_values("Energy") == ["Prevention", "Treatment"]


def test_colon_domain_facets():
    clf = colon.ColonClassifier(facets=("client", "topic", "method", "year"))
    n = clf.classify(
        "x1", client="acme", topic="pricing", method="interview", year="2024"
    )
    assert n == "acme:pricing:interview:2024"
    with pytest.raises(ValueError):
        clf.classify("x2", client="acme", bogus="z")  # unknown facet rejected
    with pytest.raises(ValueError):
        clf.classify("x3", client="a:b")  # colon in value rejected
    with pytest.raises(ValueError):
        clf.parse("a:b:c")  # wrong segment count


# ---- mundaneum --------------------------------------------------------------------


def test_mundaneum_relational_brief(home):
    m = mundaneum.Mundaneum()
    m.file(
        mundaneum.Card(
            notation="004.738.5",
            subject="remote work",
            relation="supports",
            object="productivity",
            note="my notes: deep-work blocks up 20%",
        )
    )
    m.file(
        mundaneum.Card(
            notation="004.738.5",
            subject="remote work",
            relation="contradicts",
            object="productivity",
            note="study X: junior onboarding slower",
        )
    )
    m.file(
        mundaneum.Card(
            notation="159.9",
            subject="sleep",
            relation="about",
            object="cognition",
            note="unrelated",
        )
    )
    brief = m.brief("remote work")
    assert brief["cards_consulted"] == 2
    assert len(brief["contradictions"]) == 1
    assert len(brief["supporting"]) == 1
    assert "sketch-level" in brief["disclaimer"]
    under = m.under("004.738")
    assert len(under) == 2  # hierarchical retrieval
    m.save()
    m2 = mundaneum.Mundaneum()
    assert len(m2.cards) == 3


def test_mundaneum_deny_closed(home):
    m = mundaneum.Mundaneum()
    with pytest.raises(ValueError):
        m.file(
            mundaneum.Card(notation="abc", subject="s", relation="about", object="o")
        )
    with pytest.raises(ValueError):
        m.file(
            mundaneum.Card(notation="1.2", subject="s", relation="proves", object="o")
        )
    with pytest.raises(ValueError):
        m.under("nope")
    with pytest.raises(ValueError):
        m.about("  ")


# ---- kardex -----------------------------------------------------------------------


def test_kardex_visible_file(home):
    vf = kardex.VisibleFile("subscriptions")
    vf.file_card(
        kardex.VisibleCard(
            entity="domain",
            strip="renews 2026-10-01",
            status="amber",
            updated="2026-09-15",
        )
    )
    vf.file_card(
        kardex.VisibleCard(entity="vpn", strip="paid through 2027", status="green")
    )
    dash = vf.dashboard()
    assert "domain: renews 2026-10-01" in dash and "vpn: paid through 2027" in dash
    assert vf.flagged() == []
    vf.set_status("domain", "red", strip="EXPIRED — renew now", updated="2026-09-15")
    assert [c.entity for c in vf.flagged()] == ["domain"]
    assert vf.pull("vpn").detail == ""
    vf.save()
    vf2 = kardex.VisibleFile("subscriptions")
    assert vf2.pull("domain").status == "red"


def test_kardex_deny_closed(home):
    vf = kardex.VisibleFile("k2")
    with pytest.raises(ValueError):
        vf.file_card(kardex.VisibleCard(entity="  "))
    with pytest.raises(ValueError):
        vf.file_card(kardex.VisibleCard(entity="e", status="purple"))
    with pytest.raises(KeyError):
        vf.pull("ghost")
    with pytest.raises(KeyError):
        vf.remove("ghost")
    vf.file_card(kardex.VisibleCard(entity="e"))
    with pytest.raises(ValueError):
        vf.set_status("e", "purple")
    vf.remove("e")
    assert "e" not in vf.cards
