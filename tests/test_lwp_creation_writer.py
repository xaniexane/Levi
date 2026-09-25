"""Tests for core/levi/lwp/creation_writer.py — Direction-2 DRAFT brief writer.

Covers: the full anatomy lands verbatim; every refusal class fires;
compost-fed marker; no silent overwrites; determinism; and the gate-pair
proof — a written brief is REFUSED by the Direction-1 bridge until Chauncey
marks a verdict (drafts stay DRAFT).
"""

from __future__ import annotations

import pytest

from levi.lwp.creation_writer import (
    DraftError,
    DraftInput,
    brief_slug,
    creation_dir,
    write_concept_brief,
)


def _good(**over) -> DraftInput:
    kw = dict(
        proposed_name="The Paper Lantern",
        lane="B — spells/traps (how things operate inside)",
        nature="A quiet engine that holds one flame steady through the draft.",
        typeline_sketch=(
            "- Species-word: **the lantern-keeper** — the steady flame.\n"
            "- FANG / HIDE: HIDE.\n"
            "- GLOW / SHADOW / SOIL / TIDE / GALE / MYTH: **GLOW**.\n"
            "- THE ASCENT: OPEN — stage assignment is Chauncey's."
        ),
        canon_grounding=(
            "Loop build, core/levi/lwp/reversible.py (commit 993df51): the "
            "palindromic clause pool verified by verify_pool."
        ),
        loop_commits=["993df51"],
        source_label="loop journal 2026-09-23",
        date_str="2026-09-23",
    )
    kw.update(over)
    return DraftInput(**kw)


def test_writes_full_anatomy(tmp_path):
    path, receipt = write_concept_brief(_good(), tmp_path)
    text = path.read_text(encoding="utf-8")
    assert path.name == "2026-09-23-the-paper-lantern.md"
    assert "**Status:** DRAFT" in text
    assert "nothing here is canon" in text
    assert '**Proposed name:** "The Paper Lantern" — working title only' in text
    assert "Chauncey renames" in text
    assert "**Lane:** B — spells/traps" in text
    assert "## Canon grounding (his words + the build)" in text
    assert "993df51" in text  # cited, verbatim
    assert "## Nature" in text
    assert "holds one flame steady" in text
    assert "## Typeline sketch (draft — his word settles it)" in text
    assert "## Intelligence-type axis" in text
    assert "**OPEN — extensible.**" in text
    assert "proposes NO intelligence type" in text
    assert "## Gate" in text
    assert "Nothing moves to 02-factory without his yes / no / rename" in text
    assert "**Verdict:**" not in text  # never written
    assert "Compost-fed" not in text  # off by default
    assert receipt.slug == "the-paper-lantern"
    assert receipt.lane_letter == "B"
    assert receipt.mapped["title"].startswith("proposed name")
    assert any("verdict" in a for a in receipt.absent)
    assert any("cited" in w and "not verified" in w for w in receipt.warnings)


def test_compost_fed_marker(tmp_path):
    path, _ = write_concept_brief(_good(compost_fed=True), tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "**Compost-fed:** yes" in text
    assert "Never a revival of denied copy" in text


def test_gate_note_appends(tmp_path):
    path, _ = write_concept_brief(
        _good(gate_note="Honest limit: the flame is a metaphor, not a model."),
        tmp_path,
    )
    text = path.read_text(encoding="utf-8")
    assert "Honest limit: the flame is a metaphor" in text


def test_denied_by_him_is_refused(tmp_path):
    with pytest.raises(DraftError, match="denied.*compost"):
        write_concept_brief(_good(denied_by_him=True), tmp_path)


@pytest.mark.parametrize(
    "field",
    ["proposed_name", "nature", "typeline_sketch", "canon_grounding", "source_label"],
)
def test_empty_required_fields_refused(tmp_path, field):
    with pytest.raises(DraftError, match="cites, never supplies"):
        write_concept_brief(_good(**{field: "  "}), tmp_path)


def test_no_commits_refused(tmp_path):
    with pytest.raises(DraftError, match="no loop commits"):
        write_concept_brief(_good(loop_commits=[]), tmp_path)


def test_bad_commit_hash_refused(tmp_path):
    with pytest.raises(DraftError, match="not a short hex hash"):
        write_concept_brief(_good(loop_commits=["not-a-hash"]), tmp_path)


def test_bad_lane_refused(tmp_path):
    with pytest.raises(DraftError, match="does not start with a letter"):
        write_concept_brief(_good(lane="spells and traps"), tmp_path)


def test_lane_letter_lowercase_ok(tmp_path):
    _, receipt = write_concept_brief(_good(lane="c — fields"), tmp_path)
    assert receipt.lane_letter == "C"


def test_sealed_ordinal_refused(tmp_path):
    with pytest.raises(DraftError, match="ordinal of the eleven"):
        write_concept_brief(
            _good(nature="The first of the eleven speaks through the flame."),
            tmp_path,
        )


def test_sealed_list_refused(tmp_path):
    with pytest.raises(DraftError, match="lists the eleven"):
        write_concept_brief(
            _good(typeline_sketch="The eleven: keeper, herald, smith."),
            tmp_path,
        )


def test_sealed_law_mention_allowed(tmp_path):
    """The law itself is not a claim — 'the eleven stay sealed' passes."""
    path, _ = write_concept_brief(
        _good(
            nature="The eleven stay sealed — no names, no order. "
            "This brief names nothing."
        ),
        tmp_path,
    )
    assert path.exists()


def test_intelligence_type_claim_refused(tmp_path):
    with pytest.raises(DraftError, match="intelligence type or placement"):
        write_concept_brief(
            _good(nature="Its intelligence type is herald."),
            tmp_path,
        )


def test_declared_name_refused(tmp_path):
    with pytest.raises(DraftError, match="smuggles a declaration"):
        write_concept_brief(_good(proposed_name="The Sealed Lantern"), tmp_path)


def test_existing_file_never_overwritten(tmp_path):
    write_concept_brief(_good(), tmp_path)
    with pytest.raises(DraftError, match="never silently overwritten"):
        write_concept_brief(_good(), tmp_path)
    text = (tmp_path / "2026-09-23-the-paper-lantern.md").read_text()
    assert "holds one flame steady" in text  # original intact


def test_deterministic_bytes(tmp_path):
    p1, _ = write_concept_brief(_good(), tmp_path / "a")
    p2, _ = write_concept_brief(_good(), tmp_path / "b")
    assert p1.read_bytes() == p2.read_bytes()


def test_slug():
    assert brief_slug("The Brain-Voice") == "the-brain-voice"
    assert brief_slug("  Whisper Organ  ") == "whisper-organ"


def test_bad_date_refused(tmp_path):
    with pytest.raises(DraftError, match="YYYY-MM-DD"):
        write_concept_brief(_good(date_str="Sept 23"), tmp_path)


def test_creation_dir_points_at_real_01_creation():
    assert creation_dir().name == "01-creation"


def test_direction1_bridge_refuses_written_brief(tmp_path):
    """The gate pair holds: a written brief is DRAFT, and the Direction-1
    bridge refuses it with 'no verdict on record' until he marks one."""
    from levi.lwp.pipeline_bridge import (
        VerdictGateError,
        _axis_is_open,
        parse_concept_brief,
        verdict_of,
    )

    path, _ = write_concept_brief(_good(), tmp_path)
    brief = parse_concept_brief(path)
    assert brief.proposed_name == "The Paper Lantern"
    assert brief.lane == "B"
    assert _axis_is_open(brief)  # the axis reads OPEN, as the writer emits
    with pytest.raises(VerdictGateError, match="no verdict on record"):
        verdict_of(brief)
