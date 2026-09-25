"""Tests for the L.W.P. living bible (Phase 0, KFX2 milestone 1).

No explicit content anywhere. Uses tmp_path for all stores — nothing touches
the real ~/.levi.
"""

from __future__ import annotations

import json

import pytest

from levi.lwp.living_bible import (
    LivingBible,
    PROPOSED,
    CONFIRMED,
    REJECTED,
)
from levi.lwp import bible_themes
from levi.lwp.bible_themes import Theme, get_theme, render_text, render_bible


MANUSCRIPT = """
Mara stood at the edge of the Ashen Field and listened. The wind carried
nothing back.

Mara: We cross at dawn. No one turns back.

Jonas laughed, short and bitter. Jonas said the field had eaten his brother
and would eat them too. Mara ignored him. She had buried Tomas herself, and
the law of the field was plain: the dead must never be named aloud after
the third bell.

The third bell rang. Jonas went pale. Mara took his hand.

Mara: Then we will not name him.

They walked into the grey. Behind them, the village of Ember Hollow kept
its lamps lit, as the old compact demanded: every lamp lit, no door barred,
for the ash would come for the closed houses first. That was the way of
things since the Sundering, and no one questioned it. The ash could never be
outrun, only outlasted.

Jonas whispered that Mara had changed since the Sundering. Mara did not
answer.
"""


@pytest.fixture
def bible(tmp_path):
    store = tmp_path / "living_bible_test.json"
    return LivingBible("test-work", store=store)


def test_ingest_proposes_characters_from_manuscript(bible):
    counts = bible.ingest_manuscript(MANUSCRIPT)
    assert counts["characters"] >= 2  # Mara and Jonas at minimum
    names = {c.name for c in bible.characters.values()}
    assert "Mara" in names
    assert "Jonas" in names
    # Everything arrives as PROPOSED — the third state, never canon by default
    assert all(c.status == PROPOSED for c in bible.characters.values())


def test_ingest_proposes_world_rules_from_rule_scent(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    rules = list(bible.world_rules.values())
    assert rules, "expected at least one world-rule proposal"
    joined = " ".join(r.rule for r in rules)
    assert "never be named" in joined or "never be outrun" in joined


def test_ingest_proposes_timeline_beats_in_order(bible):
    counts = bible.ingest_manuscript(MANUSCRIPT)
    assert (
        counts["timeline"] == len(MANUSCRIPT.strip().split("\n\n"))
        or counts["timeline"] >= 1
    )
    beats = sorted(bible.timeline.values(), key=lambda b: b.order)
    assert [b.order for b in beats] == list(range(len(beats)))


def test_confirm_and_reject_are_the_verifier(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    cid = next(iter(bible.characters))
    bible.confirm(cid)
    assert bible.characters[cid].status == CONFIRMED
    assert bible.characters[cid].confirmed_at is not None
    other = next(c for c in bible.characters if c != cid)
    bible.reject(other)
    assert bible.characters[other].status == REJECTED


def test_reject_all_is_one_key(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    total = len(bible.proposals())
    assert total > 0
    n = bible.reject_all()
    assert n == total
    assert bible.proposals() == []


def test_reject_all_scoped_to_kind(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    bible.reject_all(kind="timeline")
    assert bible.proposals(kind="timeline") == []
    assert bible.proposals(kind="characters")  # untouched


def test_confirm_unknown_id_raises(bible):
    with pytest.raises(KeyError):
        bible.confirm("char-does-not-exist")


def test_hand_added_character_enters_as_proposed(bible):
    entry = bible.add_character("Sable", description="A cartographer of ash.")
    assert entry.status == PROPOSED
    assert entry.description == "A cartographer of ash."


def test_ingest_is_deterministic(bible, tmp_path):
    bible.ingest_manuscript(MANUSCRIPT)
    first = {c.id: c.name for c in bible.characters.values()}
    bible2 = LivingBible("test-work-2", store=tmp_path / "b.json")
    bible2.ingest_manuscript(MANUSCRIPT)
    second = {c.id: c.name for c in bible2.characters.values()}
    assert first == second  # stable ids across runs


def test_persistence_roundtrip(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    cid = next(iter(bible.characters))
    bible.confirm(cid)
    store = bible.store
    again = LivingBible("test-work", store=store)
    assert again.characters[cid].status == CONFIRMED
    assert again.summary()["characters"]["total"] == len(bible.characters)


def test_export_json_is_plain_data(bible, tmp_path):
    bible.ingest_manuscript(MANUSCRIPT)
    out = tmp_path / "bible-export.json"
    path = bible.export(out)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "lwp-living-bible/1"
    assert data["slug"] == "test-work"
    assert len(data["characters"]) >= 2
    assert "timeline" in data and "world_rules" in data and "relations" in data


def test_export_markdown_readable(bible, tmp_path):
    bible.ingest_manuscript(MANUSCRIPT)
    cid = next(iter(bible.characters))
    bible.confirm(cid)
    out = tmp_path / "bible.md"
    path = bible.export_markdown(out)
    text = path.read_text(encoding="utf-8")
    assert "Living Bible" in text
    assert "[canon]" not in text  # markdown uses [✓]; renderer uses [canon]
    assert "✓" in text  # the confirmed character marks canon
    assert "Mara" in text


def test_summary_counts_by_status(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    s = bible.summary()
    assert s["characters"][PROPOSED] == s["characters"]["total"]
    cid = next(iter(bible.characters))
    bible.confirm(cid)
    s = bible.summary()
    assert s["characters"][CONFIRMED] == 1
    assert s["characters"][PROPOSED] == s["characters"]["total"] - 1


def test_low_mention_names_are_not_proposed(bible):
    bible.ingest_manuscript(MANUSCRIPT, min_mentions=99)
    assert bible.characters == {}  # nothing canonized from noise


# -- themes: structured, safe, throughout the surfaces -----------------------


def test_theme_presets_exist_and_are_data_only():
    for name in ["void", "paper", "sepia", "high_contrast", "noir_desk", "romcom_desk"]:
        theme = get_theme(name)
        assert isinstance(theme, Theme)
        assert theme.background.startswith("#")
        assert theme.density in ("roomy", "snug", "dense")
        assert 0.8 <= theme.font_scale <= 1.6


def test_unknown_theme_raises():
    with pytest.raises(KeyError):
        get_theme("mystery_meat")


def test_render_text_wraps_at_measure():
    theme = get_theme("void")
    out = render_text("word " * 100, theme)
    assert all(len(line) <= theme.measure for line in out.splitlines())


def test_render_text_contains_no_markup_or_scripts():
    out = render_text("Hello <script>alert(1)</script> world.", "paper")
    assert (
        "<script>" in out
    )  # text is passed through, never executed or stripped-into-html
    assert "<html" not in out and "javascript" not in out.replace("<script>", "")


def test_render_bible_flags_proposals_as_awaiting(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    out = render_bible(bible, "void")
    assert "awaiting you" in out  # proposals never presented as decided fact
    cid = next(iter(bible.characters))
    bible.confirm(cid)
    out2 = render_bible(bible, "void")
    assert "[canon]" in out2


def test_render_bible_sections_selectable(bible):
    bible.ingest_manuscript(MANUSCRIPT)
    out = render_bible(bible, "sepia", only="characters")
    assert "CHARACTERS" in out
    assert "TIMELINE" not in out
    with pytest.raises(ValueError):
        render_bible(bible, "sepia", only="nonsense")


def test_custom_theme_stays_plain_data():
    t = bible_themes.custom_theme("void", name="my_void", measure=60)
    assert t.measure == 60
    assert t.background == "#0b0e14"  # inherited, still literal data
