"""Tests for levi.lwp.chronicle — canon-consistency machinery.

All tests run against a tmp_path home: nothing touches the real ~/.levi.
"""

from pathlib import Path

import pytest

from levi.lwp.chronicle import Chronicle, _content_words, _contradicts_denial
from levi.lwp.living_bible import CONFIRMED, LivingBible, WorldRuleEntry


def make_chronicle(tmp_path: Path, with_bible: bool = True) -> Chronicle:
    bible = None
    if with_bible:
        bible = LivingBible(
            "test-world", store=tmp_path / "bible.json"
        )
    return Chronicle("test-world", home=tmp_path, bible=bible)


def confirm_rule(bible: LivingBible, text: str):
    entry = WorldRuleEntry(id="rule-x", rule=text)
    bible.world_rules[entry.id] = entry
    bible.confirm(entry.id)
    return entry


# ---------------------------------------------------------------------------
# 1. Causal timeline: consequence chains propagate across 3+ links
# ---------------------------------------------------------------------------


def test_consequence_chain_propagates_three_links(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("voyage one")
    e1 = ch.record(doc.id, "the harbor master seals the gates")
    e2 = ch.record(doc.id, "the crew riots at the docks", causes=[e1.id])
    e3 = ch.record(doc.id, "a ship burns in the harbor", causes=[e2.id])
    e4 = ch.record(doc.id, "the fleet sails without orders", causes=[e3.id])

    # direct propagation links
    assert ch.events[e1.id].consequences == [e2.id]
    assert ch.events[e2.id].consequences == [e3.id]
    assert ch.events[e3.id].consequences == [e4.id]
    assert ch.events[e4.id].consequences == []

    # transitive queries across the full chain
    assert ch.downstream(e1.id) == [e2.id, e3.id, e4.id]
    assert ch.upstream(e4.id) == [e3.id, e2.id, e1.id]
    assert ch.downstream(e2.id) == [e3.id, e4.id]
    assert ch.upstream(e1.id) == []


def test_record_rejects_unknown_cause(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("voyage one")
    with pytest.raises(KeyError):
        ch.record(doc.id, "an orphan event", causes=["evt-nope"])


def test_branching_causes_merge(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("two roads")
    a = ch.record(doc.id, "the north road floods")
    b = ch.record(doc.id, "the south road is bandit-held")
    c = ch.record(doc.id, "the caravan turns back", causes=[a.id, b.id])
    assert set(ch.upstream(c.id)) == {a.id, b.id}
    assert ch.events[a.id].consequences == [c.id]
    assert ch.events[b.id].consequences == [c.id]


# ---------------------------------------------------------------------------
# 2. Rolling summary: key facts survive folding
# ---------------------------------------------------------------------------


def test_rolling_summary_retains_key_facts_after_fold(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("session one")
    ch.record(doc.id, "Mara finds the drowned chart")
    ch.record(doc.id, "the tide takes the north pier")
    folded = ch.fold_session(doc.id)
    assert folded == 2
    facts = ch._read_summary_facts()
    assert "Mara finds the drowned chart" in facts
    assert "the tide takes the north pier" in facts
    # the doc still holds the details
    assert ch._doc_path(doc).exists()


def test_rolling_summary_compacts_oldest_past_cap(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("long campaign")
    for i in range(50):
        ch.record(doc.id, f"campaign fact number {i:02d}")
    ch.fold_session(doc.id)
    facts = ch._read_summary_facts()
    # newest facts stay verbatim
    assert "campaign fact number 49" in facts
    assert "campaign fact number 40" in facts
    # oldest compacted into a single carried line
    assert any("Earlier" in f for f in facts)
    assert len([f for f in facts if not f.startswith("_Earlier")]) <= 40


def test_fold_is_idempotent(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("session one")
    ch.record(doc.id, "a single fact")
    assert ch.fold_session(doc.id) == 1
    assert ch.fold_session(doc.id) == 0  # nothing new the second time


# ---------------------------------------------------------------------------
# 3. Rules as data: delete the file, the rule is gone
# ---------------------------------------------------------------------------


def test_deleting_rule_file_removes_rule(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    ch.write_rule_pack(
        "storm-law",
        "Storm Law",
        [
            {
                "id": "no-sailing",
                "asserts": "No ship sails during the red storm",
                "denies": ["ships sail during the red storm"],
            }
        ],
    )
    packs = ch.load_rules()
    assert len(packs) == 1
    assert packs[0]["pack_id"] == "storm-law"

    verdict = ch.check_proposal(
        {"kind": "event", "summary": "the ships sail during the red storm"}
    )
    assert not verdict["accepted"]
    assert any("storm-law/no-sailing" in r for r in verdict["reasons"])

    # delete the data file: the rule is gone, no code changed
    (ch._rules_dir / "storm-law.json").unlink()
    assert ch.load_rules() == []
    verdict = ch.check_proposal(
        {"kind": "event", "summary": "the ships sail during the red storm"}
    )
    assert verdict["accepted"]


def test_malformed_rule_pack_does_not_abort_load(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    ch._rules_dir.mkdir(parents=True, exist_ok=True)
    (ch._rules_dir / "broken.json").write_text("{not json", encoding="utf-8")
    ch.write_rule_pack("good", "Good", [])
    packs = ch.load_rules()
    assert [p["pack_id"] for p in packs] == ["good"]


# ---------------------------------------------------------------------------
# 4. Canon-as-constraint: contradictions rejected with reasons
# ---------------------------------------------------------------------------


def test_canon_check_rejects_contradicting_rule_proposal(tmp_path):
    ch = make_chronicle(tmp_path)
    confirm_rule(ch.bible, "Dragons can never fly.")
    verdict = ch.check_proposal(
        {"kind": "fact", "subject": "dragons", "statement": "the dragons fly over the harbor"}
    )
    assert not verdict["accepted"]
    assert len(verdict["reasons"]) == 1
    assert "bible:rule-x" in verdict["reasons"][0]


def test_canon_check_accepts_agreeing_negation(tmp_path):
    ch = make_chronicle(tmp_path)
    confirm_rule(ch.bible, "Dragons can never fly.")
    verdict = ch.check_proposal(
        {"kind": "fact", "subject": "dragons", "statement": "dragons cannot fly; they walk"}
    )
    assert verdict["accepted"], verdict["reasons"]


def test_canon_check_ignores_unrelated_subject(tmp_path):
    ch = make_chronicle(tmp_path)
    confirm_rule(ch.bible, "Dragons can never fly.")
    verdict = ch.check_proposal(
        {"kind": "fact", "subject": "gulls", "statement": "the gulls fly south for winter"}
    )
    assert verdict["accepted"], verdict["reasons"]


def test_character_identity_conflict_rejected(tmp_path):
    ch = make_chronicle(tmp_path)
    entry = ch.bible.add_character(
        "Mara Vex", description="a cartographer of the drowned coast"
    )
    ch.bible.confirm(entry.id)
    verdict = ch.check_proposal(
        {
            "kind": "character",
            "name": "mara vex",
            "description": "a starship pilot from the orbital ring",
        }
    )
    assert not verdict["accepted"]
    assert any("identity conflict" in r for r in verdict["reasons"])
    assert any(entry.id in r for r in verdict["reasons"])


def test_character_consistent_elaboration_accepted(tmp_path):
    ch = make_chronicle(tmp_path)
    entry = ch.bible.add_character(
        "Mara Vex", description="a cartographer of the drowned coast"
    )
    ch.bible.confirm(entry.id)
    verdict = ch.check_proposal(
        {
            "kind": "character",
            "name": "Mara Vex",
            "description": "a cartographer of the drowned coast who maps the tides",
        }
    )
    assert verdict["accepted"], verdict["reasons"]


def test_event_ordering_conflict_rejected(tmp_path):
    ch = make_chronicle(tmp_path)
    beat_id = "beat-000"
    ch.bible.timeline[beat_id] = __import__(
        "levi.lwp.living_bible", fromlist=["TimelineEntry"]
    ).TimelineEntry(id=beat_id, order=3, summary="the fleet departs at dawn")
    ch.bible.confirm(beat_id)
    verdict = ch.check_proposal(
        {"kind": "event", "summary": "the fleet burns at anchor", "order": 3}
    )
    assert not verdict["accepted"]
    assert any("ordering conflict" in r for r in verdict["reasons"])


def test_propose_writes_clean_character_as_proposed(tmp_path):
    ch = make_chronicle(tmp_path)
    verdict = ch.propose(
        {"kind": "character", "name": "Sable Quinn", "description": "a lighthouse keeper"}
    )
    assert verdict["accepted"]
    assert verdict.get("written") is True
    chars = list(ch.bible.characters.values())
    assert len(chars) == 1
    assert chars[0].status == "proposed"
    assert chars[0].name == "Sable Quinn"


def test_propose_writes_nothing_on_contradiction(tmp_path):
    ch = make_chronicle(tmp_path)
    confirm_rule(ch.bible, "Dragons can never fly.")
    verdict = ch.propose(
        {"kind": "fact", "subject": "dragons", "statement": "the dragons fly over the harbor"}
    )
    assert not verdict["accepted"]
    assert "written" not in verdict
    assert ch.bible.world_rules["rule-x"].status == CONFIRMED  # untouched


def test_unknown_proposal_kind_reported(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    verdict = ch.check_proposal({"kind": "prophecy"})
    assert not verdict["accepted"]
    assert any("unknown proposal kind" in r for r in verdict["reasons"])


# ---------------------------------------------------------------------------
# Lexical machinery unit checks
# ---------------------------------------------------------------------------


def test_content_words_drop_stopwords_and_stem():
    words = _content_words("The dragons fly over the harbor")
    assert "dragon" in words  # stemmed
    assert "fli" in words or "fly" in words  # stemmed
    assert "the" not in words
    assert "over" not in words


def test_contradicts_denial_requires_subject_overlap():
    denial = {"subject": {"dragon"}, "denied": {"fly"}}
    assert _contradicts_denial("the dragons fly high", denial)
    assert _contradicts_denial("the dragon flies at dawn", denial)
    assert not _contradicts_denial("the gulls fly high", denial)
    assert not _contradicts_denial("dragons cannot fly", denial)


# ---------------------------------------------------------------------------
# Local-first hygiene
# ---------------------------------------------------------------------------


def test_records_are_mode_0600(tmp_path):
    import os
    import stat

    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("hygiene")
    ch.record(doc.id, "a quiet fact")
    ch.fold_session(doc.id)
    for path in (ch._store, ch._doc_path(doc), ch._summary_path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"{path} has mode {oct(mode)}"


def test_reload_round_trip(tmp_path):
    ch = make_chronicle(tmp_path, with_bible=False)
    doc = ch.open_doc("round trip")
    e1 = ch.record(doc.id, "first light")
    ch.record(doc.id, "second light", causes=[e1.id])
    ch2 = Chronicle("test-world", home=tmp_path)
    assert set(ch2.events) == set(ch.events)
    assert ch2.events[e1.id].consequences == ch.events[e1.id].consequences
    assert ch2.docs[doc.id].event_ids == doc.event_ids
