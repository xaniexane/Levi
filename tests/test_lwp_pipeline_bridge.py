"""Tests for core/levi/lwp/pipeline_bridge.py — the Direction-1 live bridge.

LAWS under proof:
  1. No verdict, no brief — DRAFT briefs are refused (VerdictGateError).
  2. NO verdict -> compost via REIM, never a ProductionBrief.
  3. YES stages with the proposed name kept as-proposed; RENAME uses his
     rename verbatim — nothing reworded, nothing invented.
  4. Intelligence axis must read OPEN; any declared/unclear placement is
     refused. Ambiguous markers are refused, never guessed.
  5. Lane -> kind mapping is deterministic (A/C -> manuscript, B/D -> prose).
  6. Absent elements ride as None and are listed in receipt.absent.
  7. Fields the parser lifts but the bridge does not stage (canon grounding,
     shelf, cosmology slot) are recorded in receipt.parsed_not_carried —
     nothing is silently dropped; absent-from-the-brief stays the parser's
     None, not a receipt entry.

Zero source changes to machine.py; hermetic (tmp_path briefs only).
"""

import pytest

from levi.lwp.pipeline_bridge import (
    LANE_KIND,
    OPEN_AXIS_ANGLE,
    BridgeReceipt,
    ConceptBrief,
    VerdictGateError,
    brief_to_production_brief,
    parse_concept_brief,
    stage_for_factory,
    verdict_of,
)


def _brief(
    lane="C",
    status="DRAFT — nothing here is canon. Awaiting Chauncey's yes / no / rename.",
    verdict=None,
    proposed_name='"The Star" — working title only.',
    axis="**OPEN — extensible.** Nothing declared; placements are Chauncey's.",
    nature="The one everyone talks to. Not a ruler — a host.",
    typeline="- Species-word: **the companion-role** — the star that hosts.",
    extra="",
):
    lines = [
        "# Concept brief — THE STAR (role)",
        "",
        f"**Status:** {status}",
        "**Date:** 2026-09-21",
        f"**Lane:** {lane} — god tier (the platforms).",
        "**Shelf:** creatures / platform. **Cosmology slot:** the star.",
        f"**Proposed name:** {proposed_name}",
    ]
    if verdict is not None:
        lines.append(f"**Verdict:** {verdict}")
    lines += [
        "",
        "## Nature",
        "",
        nature,
        "",
        "## Typeline sketch (draft — his word settles it)",
        "",
        typeline,
        "",
        "## Intelligence-type axis",
        "",
        axis,
    ]
    if extra:
        lines += ["", extra]
    return "\n".join(lines) + "\n"


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- LAW 1: no verdict, no brief -------------------------------------------


def test_draft_without_verdict_is_refused(tmp_path):
    p = _write(tmp_path, "draft.md", _brief())
    with pytest.raises(VerdictGateError, match="no verdict on record"):
        stage_for_factory(p)


def test_draft_status_alone_never_passes(tmp_path):
    # Even a brief whose Status line says APPROVED is refused without a
    # Verdict marker — status prose is not his recorded verdict.
    p = _write(
        tmp_path,
        "s.md",
        _brief(status="APPROVED (prose only, no marker)"),
    )
    with pytest.raises(VerdictGateError, match="no verdict on record"):
        stage_for_factory(p)


# --- LAW 2: NO -> compost, never a brief ------------------------------------


def test_no_verdict_composts_via_reim(tmp_path):
    p = _write(tmp_path, "denied.md", _brief(verdict="NO"))
    with pytest.raises(VerdictGateError, match="compost via REIM"):
        stage_for_factory(p)


# --- LAW 3: YES keeps the proposal; RENAME is verbatim ----------------------


def test_yes_verdict_stages_with_proposed_name(tmp_path):
    p = _write(tmp_path, "star.md", _brief(verdict="YES"))
    staged, receipt = stage_for_factory(p)
    assert staged.title == "The Star"  # proposed, as-proposed, his YES kept it
    assert staged.kind == "manuscript"  # lane C -> manuscript
    assert "The one everyone talks to" in staged.brief_text  # nature verbatim
    assert "companion-role" in staged.brief_text  # typeline verbatim
    assert staged.angles == [OPEN_AXIS_ANGLE]
    assert staged.cast_size is None  # never invented
    assert staged.platform is None
    assert isinstance(receipt, BridgeReceipt)
    assert receipt.verdict == "yes"
    assert receipt.approved_name == "The Star"
    assert "cast_size" in " ".join(receipt.absent)  # recorded as not carried


def test_rename_verdict_uses_his_name_verbatim(tmp_path):
    p = _write(
        tmp_path,
        "renamed.md",
        _brief(verdict="RENAME — The Bright Host"),
    )
    staged, receipt = stage_for_factory(p)
    assert staged.title == "The Bright Host"
    assert receipt.verdict == "rename"
    assert receipt.approved_name == "The Bright Host"


def test_rename_without_name_is_refused(tmp_path):
    p = _write(tmp_path, "r.md", _brief(verdict="RENAME"))
    with pytest.raises(VerdictGateError, match="never invents his rename"):
        stage_for_factory(p)


# --- LAW 4: the axis gate ----------------------------------------------------


def test_declared_axis_is_refused(tmp_path):
    p = _write(
        tmp_path,
        "typed.md",
        _brief(
            verdict="YES",
            axis="Type: companion-ai, placed at the park center.",
        ),
    )
    with pytest.raises(VerdictGateError, match="Chauncey's alone"):
        stage_for_factory(p)


def test_absent_axis_is_refused(tmp_path):
    text = _brief(verdict="YES")
    text = text.replace(
        "## Intelligence-type axis\n\n**OPEN — extensible.** Nothing declared; placements are Chauncey's.\n",
        "",
    )
    p = _write(tmp_path, "noaxis.md", text)
    with pytest.raises(VerdictGateError, match="not declared OPEN"):
        stage_for_factory(p)


def test_ambiguous_verdict_is_refused_not_guessed(tmp_path):
    p = _write(tmp_path, "amb.md", _brief(verdict="MAYBE LATER"))
    with pytest.raises(VerdictGateError, match="ambiguous"):
        stage_for_factory(p)


# --- LAW 5: lane -> kind ------------------------------------------------------


@pytest.mark.parametrize(
    "lane,expected",
    [("A", "manuscript"), ("B", "prose"), ("C", "manuscript"), ("D", "prose")],
)
def test_lane_kind_mapping(tmp_path, lane, expected):
    assert LANE_KIND[lane] == expected
    p = _write(tmp_path, f"{lane}.md", _brief(lane=lane, verdict="YES"))
    staged, receipt = stage_for_factory(p)
    assert staged.kind == expected
    assert receipt.kind == expected


def test_unknown_lane_is_refused(tmp_path):
    p = _write(tmp_path, "x.md", _brief(lane="Z", verdict="YES"))
    with pytest.raises(VerdictGateError, match="not A/B/C/D"):
        stage_for_factory(p)


# --- LAW 6: never invent — absent elements ------------------------------------


def test_missing_nature_and_typeline_is_refused(tmp_path):
    text = _brief(verdict="YES")
    for block in (
        "## Nature\n\nThe one everyone talks to. Not a ruler — a host.\n",
        "## Typeline sketch (draft — his word settles it)\n\n- Species-word: **the companion-role** — the star that hosts.\n",
    ):
        text = text.replace(block, "")
    p = _write(tmp_path, "empty.md", text)
    with pytest.raises(VerdictGateError, match="never writes his copy"):
        stage_for_factory(p)


def test_nature_only_stages_with_warning_free_receipt(tmp_path):
    text = _brief(verdict="YES")
    text = text.replace(
        "## Typeline sketch (draft — his word settles it)\n\n- Species-word: **the companion-role** — the star that hosts.\n\n",
        "",
    )
    p = _write(tmp_path, "nature-only.md", text)
    staged, receipt = stage_for_factory(p)
    assert "The one everyone talks to" in staged.brief_text
    assert "companion-role" not in staged.brief_text  # absent, not invented
    assert staged.validate().title == "The Star"


def test_unquoted_proposed_name_uses_text_before_emdash(tmp_path):
    p = _write(
        tmp_path,
        "u.md",
        _brief(verdict="YES", proposed_name="The Star — working title only."),
    )
    staged, _ = stage_for_factory(p)
    assert staged.title == "The Star"


def test_receipt_maps_every_field_to_its_element(tmp_path):
    p = _write(tmp_path, "rc.md", _brief(verdict="YES"))
    _, receipt = stage_for_factory(p)
    for key in ("title", "brief_text", "kind", "angles"):
        assert key in receipt.mapped, f"{key} missing from receipt.mapped"
    assert receipt.source.endswith("rc.md")
    assert receipt.lane == "C"


def test_parser_extracts_only_labeled_fields(tmp_path):
    p = _write(tmp_path, "parse.md", _brief())
    brief = parse_concept_brief(p)
    assert isinstance(brief, ConceptBrief)
    assert brief.lane == "C"
    assert brief.proposed_name == "The Star"
    assert brief.status.startswith("DRAFT")
    assert brief.date == "2026-09-21"
    assert brief.verdict_raw is None  # no marker -> None, never assumed


def test_parser_reads_plain_verdict_line(tmp_path):
    text = _brief(verdict=None, extra="Verdict: yes")
    p = _write(tmp_path, "plain.md", text)
    brief = parse_concept_brief(p)
    assert verdict_of(brief) == ("yes", None)


def test_direct_two_stage_path(tmp_path):
    # parse and stage are separately callable: the two-stage path is a real
    # API surface, not just an internal step of stage_for_factory.
    p = _write(tmp_path, "two.md", _brief(verdict="YES"))
    brief = parse_concept_brief(p)
    staged, receipt = brief_to_production_brief(brief)
    assert staged.title == "The Star"
    assert receipt.verdict == "yes"


def test_real_draft_briefs_all_refused(tmp_path):
    # The six live 2026-09-21 briefs are DRAFT with no verdict marker:
    # the bridge refuses every one of them. (Path resolved relative to the
    # repo root so the test reads the real files, never copies them.)
    from pathlib import Path as _P

    creation = (
        _P(__file__).resolve().parent.parent.parent / "legion-pipeline" / "01-creation"
    )
    briefs = sorted(creation.glob("2026-09-21-*.md"))
    assert len(briefs) == 6, f"expected the six DRAFT briefs, found {len(briefs)}"
    for b in briefs:
        with pytest.raises(VerdictGateError, match="no verdict on record"):
            stage_for_factory(b)


def test_writer_brief_round_trips_labeled_fields(tmp_path):
    # Heading drift fix: the writer's "## Canon grounding (his words + the
    # build)" heading and its combined Shelf/Cosmology-slot line must survive
    # the bridge parse — labeled fields come back, absent stays None.
    from levi.lwp.creation_writer import DraftInput, write_concept_brief

    inp = DraftInput(
        proposed_name="The Test Lantern",
        lane="B — spells/traps",
        nature="A test nature, verbatim.",
        typeline_sketch="THE ASCENT I sketch",
        canon_grounding="Chauncey's words + the build that grounds it.",
        loop_commits=["abc1234"],
        source_label="loop journal test",
        shelf="engines",
        cosmology_slot="spell (an operating pattern, not a being)",
    )
    path, _ = write_concept_brief(inp, tmp_path)
    brief = parse_concept_brief(path)
    assert brief.canon_grounding == "Chauncey's words + the build that grounds it."
    assert brief.shelf == "engines"
    assert brief.cosmology_slot == "spell (an operating pattern, not a being)"


def test_writer_brief_unset_shelf_parses_absent(tmp_path):
    # The writer's "—" placeholder parses back to None, never synthesized.
    from levi.lwp.creation_writer import DraftInput, write_concept_brief

    inp = DraftInput(
        proposed_name="The Bare Lantern",
        lane="C — the platform",
        nature="A test nature.",
        typeline_sketch="a sketch",
        canon_grounding="His words + commit.",
        loop_commits=["abc1234"],
        source_label="loop journal test",
    )
    path, _ = write_concept_brief(inp, tmp_path)
    brief = parse_concept_brief(path)
    assert brief.shelf is None
    assert brief.cosmology_slot is None


def test_real_briefs_shelf_and_canon_grounding_parse():
    # The six live 2026-09-21 briefs carry the combined Shelf line and the
    # "(his words)" canon-grounding heading — both must parse honestly.
    from pathlib import Path as _P

    creation = (
        _P(__file__).resolve().parent.parent.parent / "legion-pipeline" / "01-creation"
    )
    briefs = sorted(creation.glob("2026-09-21-*.md"))
    assert len(briefs) == 6
    for b in briefs:
        brief = parse_concept_brief(b)
        assert brief.shelf is not None and "**Cosmology" not in brief.shelf, b.name
        assert brief.cosmology_slot is not None, b.name
        assert brief.canon_grounding is not None and brief.canon_grounding, b.name
    star = parse_concept_brief(creation / "2026-09-21-the-star-role.md")
    assert star.shelf == "creatures / platform."
    assert star.cosmology_slot == "the star."
    assert "LEXICON.md" in star.canon_grounding


# --- LAW 7: parsed-but-not-carried is recorded, never dropped ----------------


def test_receipt_records_parsed_not_carried(tmp_path):
    # A fully-labeled brief: canon grounding, shelf, and cosmology slot are
    # parsed and then deliberately NOT staged — the receipt must name all
    # three, and the staged ProductionBrief must not smuggle them in.
    p = _write(
        tmp_path,
        "full.md",
        _brief(
            verdict="YES",
            extra="## Canon grounding (his words)\n\nGrounded in LEXICON.md, per the parse contract.",
        ),
    )
    staged, receipt = stage_for_factory(p)
    prefixes = [e.split(":", 1)[0] for e in receipt.parsed_not_carried]
    assert prefixes == ["canon_grounding", "shelf", "cosmology_slot"], (
        receipt.parsed_not_carried
    )
    for e in receipt.parsed_not_carried:
        assert "not staged" in e or "stays with the brief" in e
    # The staged text is Nature + Typeline verbatim — the lifted fields are
    # not smuggled into title, brief_text, or angles.
    assert "Grounded in LEXICON" not in staged.brief_text
    assert "creatures / platform" not in staged.brief_text
    assert "Grounded in LEXICON" not in staged.title
    assert all("Grounded in LEXICON" not in a for a in staged.angles)
    # The absent list still carries the press-side non-carriage record.
    assert "cast_size" in " ".join(receipt.absent)


def test_receipt_parsed_not_carried_empty_when_brief_carries_none(tmp_path):
    # No canon-grounding section, no Shelf line: nothing parsed, so nothing
    # to record as parsed-not-carried — the list stays empty, honestly.
    text = _brief(verdict="YES").replace(
        "**Shelf:** creatures / platform. **Cosmology slot:** the star.\n",
        "",
    )
    p = _write(tmp_path, "bare.md", text)
    brief = parse_concept_brief(p)
    assert brief.canon_grounding is None
    assert brief.shelf is None
    assert brief.cosmology_slot is None
    _, receipt = stage_for_factory(p)
    assert receipt.parsed_not_carried == []


def test_real_briefs_parse_but_do_not_stage(tmp_path):
    # The six live 2026-09-21 briefs all carry canon grounding, shelf, and
    # cosmology slot — the parse side is rich — but with no verdict on
    # record the gate still refuses every one of them.
    from pathlib import Path as _P

    creation = (
        _P(__file__).resolve().parent.parent.parent / "legion-pipeline" / "01-creation"
    )
    briefs = sorted(creation.glob("2026-09-21-*.md"))
    assert len(briefs) == 6
    for b in briefs:
        brief = parse_concept_brief(b)
        assert any(
            f is not None
            for f in (brief.canon_grounding, brief.shelf, brief.cosmology_slot)
        ), b.name
        with pytest.raises(VerdictGateError, match="no verdict on record"):
            stage_for_factory(b)
