"""Press-line character-cast wiring (levi.lwp.machine + character_graph).

The character graph is the first literary strand wired into the press
line: a manuscript/prose brief may declare ``cast_size`` and the press
mints that many characters at draft assembly — deterministically, after
assembly (so the cast can never perturb the draft), ledger-scoped, and
carried on the assembly receipt into the sealed dossier.

Hermetic: ledger, symbiosis dir, born registry, and the character graph
file all go under tmp_path. No network, no randomness.
"""

import json
from types import SimpleNamespace

import pytest

from levi.lwp.machine import (
    BriefError,
    ContentMachine,
    ProductionBrief,
)
from levi.lwp.character_graph import CharacterGraph


def _brief(**over):
    kw = dict(
        title="The Cast Test",
        brief_text="A manuscript brief that wants a dramatis personae.",
        kind="manuscript",
        direction="forward",
        phase="gold_push",
        power="gain",
    )
    kw.update(over)
    return ProductionBrief(**kw)


def _machine(tmp_path):
    return ContentMachine(ledger_path=tmp_path / "ledger.jsonl")


def _drive_to_sealed(machine, brief, passes=2):
    run = machine.run_brief(brief, passes=passes)
    while machine.pending():
        for p in machine.pending():
            run = machine.approve(p["proposal_id"], note="keeper: approved")
    assert run.status == "sealed"
    return run


def _assembly_record(run):
    recs = [r for r in run.records if r.stage == "draft_assembly"]
    assert len(recs) == 1
    return recs[0]


# -- validation ----------------------------------------------------------


def test_cast_size_validation():
    for bad in (0, -2, 13, 100, True, "3", 2.0):
        with pytest.raises(BriefError):
            _brief(cast_size=bad).validate()
    # cast_size is manuscript/prose only — never silently dropped.
    with pytest.raises(BriefError):
        _brief(kind="social", cast_size=2).validate()
    with pytest.raises(BriefError):
        _brief(kind="reversible", cast_size=2).validate()
    # valid values pass
    _brief(cast_size=1).validate()
    _brief(cast_size=12).validate()
    _brief(kind="prose", cast_size=4).validate()


# -- determinism + draft independence ------------------------------------


def test_cast_mints_deterministically(tmp_path):
    m1, m2 = _machine(tmp_path), _machine(tmp_path)
    r1 = _drive_to_sealed(m1, _brief(cast_size=3))
    r2 = _drive_to_sealed(m2, _brief(cast_size=3))
    ids1 = [c["id"] for c in r1.cast]
    assert len(ids1) == 3
    assert ids1 == [c["id"] for c in r2.cast]
    assert [c["name"] for c in r1.cast] == [c["name"] for c in r2.cast]
    # ids are stable character-graph ids, not run-scoped
    assert all(i.startswith("char.") for i in ids1)
    # the graph persisted ledger-side, hermetic
    graph_path = tmp_path / "ledger.characters.json"
    assert graph_path.exists()
    assert len(CharacterGraph(path=graph_path).nodes) == 3


def test_cast_does_not_perturb_draft(tmp_path):
    m = _machine(tmp_path)
    plain = _drive_to_sealed(m, _brief())
    casted = _drive_to_sealed(m, _brief(cast_size=3))
    assert plain.cast == []
    assert len(casted.cast) == 3
    # identical draft text: cast_size is not part of brief.seed() and the
    # mint runs after assembly.
    assert plain.final_text == casted.final_text
    assert plain.seal == casted.seal


def test_cast_character_shape(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief(cast_size=2))
    for c in run.cast:
        for key in (
            "id",
            "name",
            "drive",
            "wound",
            "method",
            "voice",
            "domain",
            "era",
            "want",
            "need",
        ):
            assert c[key], key
        assert isinstance(c["tells"], list) and c["tells"]


# -- receipt chain + dossier ---------------------------------------------


def test_cast_rides_assembly_receipt(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief(cast_size=2))
    rec = _assembly_record(run)
    receipt = m.policy._receipts[rec.receipt_id]
    assert receipt.details["cast"] == [c["id"] for c in run.cast]
    # other stages carry the empty marker, never someone else's cast
    for r in run.records:
        if r.stage != "draft_assembly":
            assert m.policy._receipts[r.receipt_id].details["cast"] == []


def test_cast_in_seal_dossier(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief(cast_size=2))
    dossier_json, verified, notes = m._seal(run)
    assert verified is True
    dossier = json.loads(dossier_json)
    assert dossier["cast"] == run.cast
    assert len(dossier["cast"]) == 2
    assert any("cast:" in n for n in notes)


def test_no_cast_by_default(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    assert run.cast == []
    rec = _assembly_record(run)
    assert m.policy._receipts[rec.receipt_id].details["cast"] == []
    dossier = json.loads(m._seal(run)[0])
    assert dossier["cast"] == []
    assert not (tmp_path / "ledger.characters.json").exists()


def test_cast_survives_store_reload(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief(cast_size=2))
    run = m.approve(run.pending_proposal_id, note="keeper: assemble it")
    assert len(run.cast) == 2
    # a fresh machine on the same ledger reloads the run with its cast
    m2 = ContentMachine(ledger_path=tmp_path / "ledger.jsonl")
    reloaded = m2.get_run(run.run_id)
    assert [c["id"] for c in reloaded.cast] == [c["id"] for c in run.cast]


# -- console ---------------------------------------------------------------


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import levi.lwp.machine as machine_mod

    monkeypatch.setattr(machine_mod, "DEFAULT_LEDGER", tmp_path / "ledger.jsonl")


def _ns(**kw):
    base = dict(
        lwp_action="status",
        title="",
        text="",
        text_file=None,
        kind="prose",
        platform=None,
        direction="forward",
        phase="gold_push",
        power="gain",
        pov=None,
        genres="",
        target_words=None,
        angle=None,
        cast=None,
        run=None,
        proposal=None,
        note="",
        count=3,
        seed=7,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_cli_brief_cast_plumbing(capsys, home):
    from levi.cli.main import cmd_lwp

    cmd_lwp(
        _ns(
            lwp_action="brief",
            title="Console Cast",
            text="A console brief with a cast.",
            kind="prose",
            cast=2,
        )
    )
    m = ContentMachine()
    pend = m.pending()
    assert len(pend) == 1
    run_id = pend[0]["run_id"]
    # approve the assembly gate; the line runs to the seal gate on its own
    cmd_lwp(_ns(lwp_action="approve", proposal=pend[0]["proposal_id"]))
    m2 = ContentMachine()
    run = m2.get_run(run_id)
    assert run.brief["cast_size"] == 2
    assert len(run.cast) == 2
    # the seal gate, then the status line names the cast
    for p in m2.pending():
        cmd_lwp(_ns(lwp_action="approve", proposal=p["proposal_id"]))
    cmd_lwp(_ns(lwp_action="status", run=run_id))
    out = capsys.readouterr().out
    assert "cast: 2" in out
    assert run.cast[0]["name"] in out


def test_cli_brief_rejects_bad_cast(capsys, home):
    from levi.cli.main import cmd_lwp

    cmd_lwp(
        _ns(
            lwp_action="brief",
            title="Bad Cast",
            text="x",
            kind="social",
            cast=2,
        )
    )
    out = capsys.readouterr().out
    assert "lwp: cast_size applies to manuscript/prose kinds" in out
