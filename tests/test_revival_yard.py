"""Tests for the revival yard — intake, raising pipeline, the stone ledger.

The binding invariants:
  1. The stone ledger is append-only: nothing is ever deleted, and every
     raising — success or failure — leaves its record.
  2. Failed raisings are composted through REIM, never erased.
  3. Revival laws hold at prove time: stdlib-only, original never copied or
     masked, LEVI-native identity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from levi.revival.yard import (
    Yard,
    YardCandidate,
    YardRefusedError,
    check_revival_laws,
    compost_raising,
    intake_candidates,
    main as yard_main,
)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _write_hunt_fixtures(hunt_home: Path) -> None:
    """Fake a completed hunt wave: build queue + pending archive records."""
    perpetual = hunt_home / ".levi" / "perpetual"
    pending = perpetual / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    queue = [
        {
            "wave_id": "wave-101",
            "record_id": "deadwidget",
            "title": "DeadWidget",
            "kind": "software",
            "rating": "load-bearing",
            "queued_at": "2026-09-17T00:00:00+00:00",
            "status": "queued",
            "hard_route": False,
        },
        {
            "wave_id": "wave-101",
            "record_id": "oldmethod",
            "title": "OldMethod",
            "kind": "method",
            "rating": "useful-pattern",
            "queued_at": "2026-09-17T00:00:00+00:00",
            "status": "queued",
            "hard_route": True,
        },
        {
            "wave_id": "wave-101",
            "record_id": "meretoy",
            "title": "MereToy",
            "kind": "software",
            "rating": "inspirational",  # stays in the Archive — not buildable
            "queued_at": "2026-09-17T00:00:00+00:00",
            "status": "queued",
            "hard_route": False,
        },
    ]
    (perpetual / "build_queue.jsonl").write_text(
        "\n".join(json.dumps(i) for i in queue) + "\n", encoding="utf-8"
    )
    records = [
        {
            "id": "deadwidget",
            "title": "DeadWidget",
            "era": "1991",
            "kind": "software",
            "summary": "a widget toolkit",
            "mechanism": "event wiring by naming convention",
            "decline": "vendor folded",
            "revival_recipe": "rebuild the naming convention",
            "levi_application": "agent ports",
            "sources": ["https://example.invalid/deadwidget"],
            "rating": "load-bearing",
            "status": "dead",
            "provenance": {
                "found_date": "2026-09-17",
                "research_slug": "wave-101",
                "notes": "",
            },
        },
        {
            "id": "oldmethod",
            "title": "OldMethod",
            "era": "1974",
            "kind": "method",
            "summary": "a method",
            "mechanism": "checklists for proofs",
            "decline": "forgotten",
            "revival_recipe": "checklist engine",
            "levi_application": "proving bar",
            "sources": [],
            "rating": "useful-pattern",
            "status": "dead",
            "provenance": {
                "found_date": "2026-09-17",
                "research_slug": "wave-101",
                "notes": "",
            },
        },
    ]
    (pending / "wave-101.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def _yard(tmp_path: Path) -> Yard:
    hunt_home = tmp_path / "hunt"
    _write_hunt_fixtures(hunt_home)
    return Yard(home=tmp_path / "yard"), hunt_home


def _study_ok(yard: Yard, raising_id: str, **over) -> "object":
    kw = dict(
        levi_name="Widgetwright",
        title="Convention-wired agent ports",
        flair="Name a port and it answers — the dead toolkit's trick, LEVI's voice.",
        module="levi.revival.widgetwright",
        what_died="DeadWidget, a 1991 widget toolkit whose vendor folded.",
        decline="The vendor folded; the naming-convention trick died with it.",
        what_it_taught="Event wiring by naming convention — configuration without config files.",
    )
    kw.update(over)
    return yard.study(raising_id, **kw)


# --------------------------------------------------------------------------
# intake — adapts the hunt format, never rewrites it
# --------------------------------------------------------------------------


def test_intake_admits_buildable_finds_only(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    admitted = yard.intake(hunt_home)
    ids = {r.candidate.record_id for r in admitted}
    assert ids == {"deadwidget", "oldmethod"}  # inspirational MereToy stays out
    # enrichment from the pending archive records
    by_id = {r.candidate.record_id: r for r in admitted}
    assert (
        by_id["deadwidget"].candidate.mechanism == "event wiring by naming convention"
    )
    assert by_id["deadwidget"].candidate.decline == "vendor folded"
    assert by_id["deadwidget"].candidate.provenance["research_slug"] == "wave-101"
    assert by_id["oldmethod"].candidate.hard_route is True


def test_intake_is_idempotent(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    first = yard.intake(hunt_home)
    assert len(first) == 2
    second = yard.intake(hunt_home)
    assert second == []


def test_intake_candidates_standalone(tmp_path):
    hunt_home = tmp_path / "hunt"
    _write_hunt_fixtures(hunt_home)
    cands = intake_candidates(hunt_home)
    assert [c.record_id for c in cands] == ["deadwidget", "oldmethod"]
    assert isinstance(cands[0], YardCandidate)


def test_intake_with_empty_queue(tmp_path):
    yard = Yard(home=tmp_path / "yard")
    assert yard.intake(tmp_path / "nope") == []
    assert yard.ledger() == []


# --------------------------------------------------------------------------
# the pipeline: study -> scaffold -> prove -> shelve
# --------------------------------------------------------------------------


def test_full_pipeline_to_shelved(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    events_before = len(yard.ledger())

    r = _study_ok(yard, r.id)
    assert r.stage == "studied"

    target = tmp_path / "revival_modules"
    path = yard.scaffold(r.id, target)
    assert path.exists() and path.name == "widgetwright.py"
    r = yard.get(r.id)
    assert r.stage == "recreating"

    r = yard.prove(r.id, path, evidence="pytest tests/test_revival_yard.py: 24 passed")
    assert r.stage == "green"
    assert "24 passed" in r.evidence

    entry = yard.shelve(r.id)
    assert entry.levi_name == "Widgetwright"
    assert entry.module == "levi.revival.widgetwright"
    assert entry.status == "raised"
    r = yard.get(r.id)
    assert r.stage == "shelved"

    # the stone recorded every transition
    kinds = [e["event"] for e in yard.ledger()]
    assert kinds == ["intake", "intake", "studied", "recreating", "green", "shelved"][
        : len(kinds)
    ] or kinds[-4:] == ["studied", "recreating", "green", "shelved"]
    assert len(yard.ledger()) == events_before + 4

    raised = yard.raised_entries()
    assert len(raised) == 1
    assert raised[0]["entry"]["levi_name"] == "Widgetwright"


def test_stage_transitions_are_guarded(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    with pytest.raises(YardRefusedError):
        yard.scaffold(r.id, tmp_path)  # must study first
    with pytest.raises(YardRefusedError):
        yard.shelve(r.id)  # must prove green first
    with pytest.raises(YardRefusedError):
        yard.study(
            "yard-9999",
            levi_name="X",
            title="T",
            flair="F",
            module="levi.revival.x",
            what_died="D",
            decline="C",
            what_it_taught="Y",
        )


def test_identity_law_starts_at_study(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    with pytest.raises(YardRefusedError):
        _study_ok(
            yard, r.id, levi_name="DeadWidget"
        )  # the original's own name: refused
    with pytest.raises(YardRefusedError):
        _study_ok(
            yard, r.id, module="levi.forge.widgetwright"
        )  # revivals live in levi.revival.*


# --------------------------------------------------------------------------
# the stone: nothing is ever deleted
# --------------------------------------------------------------------------


def test_failed_prove_is_composted_not_deleted(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    _study_ok(yard, r.id)
    target = tmp_path / "revival_modules"
    path = yard.scaffold(r.id, target)
    # poison the module: a third-party import is a mask, not a recreation
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text + "\nimport requests  # the dead original's dependency\n", encoding="utf-8"
    )

    stone_lines_before = len(yard.ledger())
    r = yard.prove(r.id, path)
    assert r.stage == "composted"
    assert r.compost is not None
    assert r.compost["organ"] == "reim"
    assert r.compost["lesson"]

    # the stone only grew; nothing was removed
    ledger = yard.ledger()
    assert len(ledger) == stone_lines_before + 1
    last = ledger[-1]
    assert last["event"] == "composted"
    assert "revival laws violated" in last["detail"]["reason"]
    # the failure stays on the stone forever — even a re-read agrees
    assert len(yard.ledger()) == len(ledger)


def test_compost_command_needs_reason_and_does_not_rewind(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    with pytest.raises(YardRefusedError):
        yard.compost(r.id, "")  # the stone records why — a reason is required
    r = yard.compost(r.id, "the keeper chose a different shape")
    assert r.stage == "composted"
    with pytest.raises(YardRefusedError):
        yard.compost(r.id, "again")  # the stone does not rewind


def test_nothing_deleted_invariant_across_everything(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    counts = []
    counts.append(len(yard.ledger()))
    admitted = yard.intake(hunt_home)
    counts.append(len(yard.ledger()))
    _study_ok(yard, admitted[0].id)
    counts.append(len(yard.ledger()))
    yard.scaffold(admitted[0].id, tmp_path / "mods")
    counts.append(len(yard.ledger()))
    yard.compost(admitted[1].id, "warden's call")
    counts.append(len(yard.ledger()))
    assert counts == sorted(counts), "the stone must never shrink: %r" % counts
    assert counts[-1] > counts[0]


def test_compost_raising_standalone(tmp_path):
    from levi.revival.yard import Raising

    # standalone compost without a yard raising
    cand = YardCandidate(
        wave_id="w", record_id="x", title="Gone", kind="software", rating="load-bearing"
    )
    r = Raising(id="yard-0001", candidate=cand)
    compost = compost_raising(r, "test failure")
    assert compost["organ"] == "reim"
    assert "yard-0001" in compost["what"]
    assert compost["provenance"]["organ"] == "reim"


# --------------------------------------------------------------------------
# revival laws at prove time
# --------------------------------------------------------------------------


def test_laws_catch_manifest_mismatch(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    _study_ok(yard, r.id)
    path = yard.scaffold(r.id, tmp_path / "mods")
    # rewrite the manifest to disagree with the study
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace('"levi_name": "Widgetwright"', '"levi_name": "SomebodyElse"'),
        encoding="utf-8",
    )
    r = yard.prove(r.id, path)
    assert r.stage == "composted"
    assert "manifest" in yard.ledger()[-1]["detail"]["reason"]


def test_laws_refuse_missing_module_file(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    _study_ok(yard, r.id)
    yard.scaffold(r.id, tmp_path / "mods")
    r = yard.prove(r.id, tmp_path / "mods" / "nope.py")
    assert r.stage == "composted"


def test_check_revival_laws_directly(tmp_path):
    cand = YardCandidate(
        wave_id="w",
        record_id="x",
        title="DeadWidget",
        kind="software",
        rating="load-bearing",
    )
    good = tmp_path / "good.py"
    good.write_text(
        '"""doc."""\nfrom __future__ import annotations\nimport json\n'
        '__revival_manifest__ = {"module": "levi.revival.g", "levi_name": "Widgetwright",'
        ' "title": "T", "flair": "F", "origin": "levi-revival/x"}\n',
        encoding="utf-8",
    )
    assert (
        check_revival_laws(
            good,
            cand,
            {
                "module": "m",
                "levi_name": "Widgetwright",
                "title": "T",
                "flair": "F",
                "origin": "o",
            },
        )
        == []
    )
    bad = tmp_path / "bad.py"
    bad.write_text("import requests\n", encoding="utf-8")
    violations = check_revival_laws(bad, cand, {})
    assert any("purity law" in v for v in violations)
    assert any("manifest" in v for v in violations)


def test_scaffold_refuses_dangerous_roots(tmp_path):
    yard, hunt_home = _yard(tmp_path)
    (r,) = [r for r in yard.intake(hunt_home) if r.candidate.record_id == "deadwidget"]
    _study_ok(yard, r.id)
    with pytest.raises(YardRefusedError):
        yard.scaffold(r.id, "/")


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------


def _cli(*args, env_home):
    env = dict(os.environ, LEVI_YARD_HOME=str(env_home))
    old = os.environ.get("LEVI_YARD_HOME")
    os.environ["LEVI_YARD_HOME"] = str(env_home)
    try:
        return yard_main(list(args))
    finally:
        if old is None:
            del os.environ["LEVI_YARD_HOME"]
        else:
            os.environ["LEVI_YARD_HOME"] = old


def test_cli_intake_list_ledger(tmp_path, capsys):
    hunt_home = tmp_path / "hunt"
    _write_hunt_fixtures(hunt_home)
    assert _cli("intake", str(hunt_home), env_home=tmp_path / "yard") == 0
    out = capsys.readouterr().out
    assert "Admitted 2 find(s)" in out
    assert _cli("list", env_home=tmp_path / "yard") == 0
    out = capsys.readouterr().out
    assert "[queued]" in out
    assert _cli("ledger", env_home=tmp_path / "yard") == 0
    out = capsys.readouterr().out
    assert "Nothing here is ever deleted" in out
    assert _cli("bogus", env_home=tmp_path / "yard") == 2
