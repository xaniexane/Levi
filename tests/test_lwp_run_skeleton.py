"""Tests for the Direction-2 convenience helper (read-only press-run skeleton).

The helper never imports the contested machine: fixtures are plain JSON in
the store's on-disk schema ({"runs": {run_id: {...}}}), written into tmp dirs.
"""

import json
from pathlib import Path

import pytest

from levi.lwp import run_skeleton
from levi.lwp.run_skeleton import (
    DraftSkeleton,
    SkeletonError,
    render_review,
    skeleton_from_store,
)


DRAFT = "The star is a role, not a name.\n\nIt holds the door open and the lantern lit."
BRIEF = {
    "title": "The star role",
    "brief_text": "a short prose about the star",
    "kind": "prose",
}


def _write_store(tmp_path: Path, runs: dict) -> Path:
    store = tmp_path / "ledger.store.json"
    store.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    return store


def _sealed_run(**over) -> dict:
    run = {
        "run_id": "abc12345",
        "status": "sealed",
        "final_text": DRAFT,
        "brief": dict(BRIEF),
        "compost": [],
        "created_at": "2026-09-23T09:00:00Z",
        "records": [],
        "seal": "seal-1",
    }
    run.update(over)
    return run


# -- the happy path ----------------------------------------------------------


def test_sealed_run_lifts_verbatim(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    skel, receipt = skeleton_from_store("abc12345", store)
    assert isinstance(skel, DraftSkeleton)
    # pre-filled from the run's own words, verbatim
    assert skel.nature == DRAFT
    assert skel.typeline_sketch == "The star is a role, not a name."
    assert skel.proposed_name == "The star role"
    assert skel.run_status == "sealed"
    assert skel.draft_words == len(DRAFT.split())
    assert "abc12345" in skel.source_label
    assert skel.compost_fed is False
    # human's fields stay blank
    assert skel.blanks() == ["canon_grounding", "lane", "loop_commits"]
    # receipt names every source and every absence
    assert receipt.mapped["nature"].startswith("run.final_text")
    assert receipt.absent == ["canon_grounding", "lane", "loop_commits"]
    assert any("never verified" in w for w in receipt.warnings)


def test_published_run_is_accepted(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run(status="published")})
    skel, _ = skeleton_from_store("abc12345", store)
    assert skel.run_status == "published"
    assert skel.nature == DRAFT


def test_compost_sets_compost_fed(tmp_path):
    run = _sealed_run(compost=[{"kind": "failed-draft", "kept": "one image"}])
    store = _write_store(tmp_path, {"abc12345": run})
    skel, _ = skeleton_from_store("abc12345", store)
    assert skel.compost_fed is True


# -- staged-by-hand: to_draft_input refuses until the drafter fills the blanks


def test_to_draft_input_refuses_until_blanks_filled(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    skel, _ = skeleton_from_store("abc12345", store)
    with pytest.raises(SkeletonError, match="canon_grounding.*lane.*loop_commits"):
        skel.to_draft_input()


def test_completed_skeleton_hands_a_draft_input(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    skel, _ = skeleton_from_store("abc12345", store)
    skel.canon_grounding = "Chauncey's word 2026-09-20: the star is a role"
    skel.lane = "C — the entrance"
    skel.loop_commits = ["8e8ce12"]
    assert skel.blanks() == []
    inp = skel.to_draft_input()
    assert inp.proposed_name == "The star role"
    assert inp.nature == DRAFT
    assert inp.canon_grounding.startswith("Chauncey's word")
    assert inp.lane.startswith("C")
    assert inp.loop_commits == ["8e8ce12"]
    assert "abc12345" in inp.source_label


def test_completed_skeleton_feeds_the_writer(tmp_path):
    """Skeleton -> drafter fills blanks -> writer emits a DRAFT brief, and
    the Direction-1 bridge still refuses it: the gates hold across machines."""
    from levi.lwp.creation_writer import write_concept_brief
    from levi.lwp.pipeline_bridge import parse_concept_brief, verdict_of

    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    skel, _ = skeleton_from_store("abc12345", store)
    skel.canon_grounding = "Chauncey's word 2026-09-20: the star is a role"
    skel.lane = "C — the entrance"
    skel.loop_commits = ["8e8ce12"]
    out_dir = tmp_path / "01-creation"
    path, receipt = write_concept_brief(skel.to_draft_input(), out_dir)
    assert str(path).endswith(".md")
    # the emitted brief is DRAFT with no verdict — the bridge refuses it
    brief = parse_concept_brief(path)
    with pytest.raises(Exception, match="no verdict on record"):
        verdict_of(brief)


# -- refusals ----------------------------------------------------------------


def test_missing_store_file(tmp_path):
    with pytest.raises(SkeletonError, match="no press store"):
        skeleton_from_store("abc12345", tmp_path / "missing.store.json")


def test_unreadable_store_json(tmp_path):
    bad = tmp_path / "ledger.store.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SkeletonError, match="unreadable"):
        skeleton_from_store("abc12345", bad)


def test_unknown_run(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    with pytest.raises(SkeletonError, match="unknown run"):
        skeleton_from_store("nope0000", store)


@pytest.mark.parametrize(
    "status,match",
    [
        ("running", "sealed press runs only"),
        ("awaiting_approval", "sealed press runs only"),
        ("needs_attention", "sealed press runs only"),
        ("denied", "denied-by-him"),
    ],
)
def test_unsealed_runs_refused(tmp_path, status, match):
    store = _write_store(tmp_path, {"abc12345": _sealed_run(status=status)})
    with pytest.raises(SkeletonError, match=match):
        skeleton_from_store("abc12345", store)


def test_empty_final_text_refused(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run(final_text="  ")})
    with pytest.raises(SkeletonError, match="no assembled draft text"):
        skeleton_from_store("abc12345", store)


def test_brief_without_title_refused(tmp_path):
    run = _sealed_run()
    run["brief"] = {"kind": "prose"}
    store = _write_store(tmp_path, {"abc12345": run})
    with pytest.raises(SkeletonError, match="no brief title"):
        skeleton_from_store("abc12345", store)


# -- read-only proof ---------------------------------------------------------


def test_helper_never_writes_the_store(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    before = store.read_bytes()
    skel, _ = skeleton_from_store("abc12345", store)
    render_review(skel)
    skel.canon_grounding = "x"
    skel.lane = "C"
    skel.loop_commits = ["8e8ce12"]
    skel.to_draft_input()
    assert store.read_bytes() == before


def test_helper_never_imports_the_machine():
    # the store's on-disk JSON contract is the interface; the contested
    # module is never imported. The source itself must not name it.
    src = Path(run_skeleton.__file__).read_text(encoding="utf-8")
    assert "from levi.lwp.machine" not in src
    assert "import levi.lwp.machine" not in src


# -- review sheet ------------------------------------------------------------


def test_render_review_marks_prefilled_and_human_fields(tmp_path):
    store = _write_store(tmp_path, {"abc12345": _sealed_run()})
    skel, _ = skeleton_from_store("abc12345", store)
    sheet = render_review(skel)
    assert "[PRE-FILLED — run's own words] nature:" in sheet
    assert DRAFT.splitlines()[0] in sheet
    assert "[HUMAN NEEDED] canon_grounding: —" in sheet
    assert "[HUMAN NEEDED] lane: —" in sheet
    assert "[HUMAN NEEDED] loop_commits: —" in sheet
    assert "to_draft_input() refuses" in sheet
    # after the drafter fills the blanks, the sheet says so
    skel.canon_grounding = "his words"
    skel.lane = "C"
    skel.loop_commits = ["8e8ce12"]
    sheet = render_review(skel)
    assert "[supplied] canon_grounding: his words" in sheet
    assert "to_draft_input() refuses" not in sheet


# -- defense in depth: the sealed law ---------------------------------------


def test_skeleton_title_tripping_sealed_law_is_refused_by_writer(tmp_path):
    """Defense in depth (queued item): the skeleton lifts the press brief's
    title verbatim — it never invents, never sanitizes. So when a title
    claims an ordinal of the eleven, the WRITER's sealed-law tripwire is the
    gate that refuses the brief at write time. Proven end to end:
    sealed run -> skeleton -> completed skeleton -> writer refusal."""
    from levi.lwp.creation_writer import DraftError, write_concept_brief

    tripping_title = "The Seventh of the Eleven"  # trips _SEALED_ORDINAL
    store = _write_store(
        tmp_path,
        {
            "abc12345": _sealed_run(
                brief={"title": tripping_title, "brief_text": "x", "kind": "prose"}
            )
        },
    )
    skel, _ = skeleton_from_store("abc12345", store)
    # the skeleton lifts verbatim — no law check here, by design
    assert skel.proposed_name == tripping_title
    # the drafter completes the human fields honestly
    skel.canon_grounding = "his words on the matter"
    skel.lane = "C — fields"
    skel.loop_commits = ["f8546896"]
    draft = skel.to_draft_input()
    with pytest.raises(DraftError, match="ordinal of the eleven"):
        write_concept_brief(draft, tmp_path)
