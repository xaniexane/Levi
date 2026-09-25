"""Hermetic tests for the `levi lwp` press console and run persistence.

No network, no real HOME writes (HOME is monkeypatched to tmp_path), no
randomness: every assertion is deterministic. All example data is synthetic.
"""

import json
from types import SimpleNamespace

import pytest

from levi.cli.main import cmd_lwp
from levi.lwp.machine import ContentMachine, ProductionBrief


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
        run=None,
        proposal=None,
        note="",
        count=3,
        seed=7,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _brief_args(**kw):
    d = dict(
        lwp_action="brief",
        title="Console Test",
        text="A short honest brief for the console test.",
        kind="prose",
    )
    d.update(kw)
    return _ns(**d)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # DEFAULT_LEDGER is bound at import time; rebind it for hermetic tests.
    import levi.lwp.machine as machine_mod

    monkeypatch.setattr(
        machine_mod,
        "DEFAULT_LEDGER",
        tmp_path / ".levi" / "lwp_machine" / "ledger.jsonl",
    )
    return tmp_path


def _pending_proposal(home):
    store = home / ".levi" / "lwp_machine" / "ledger.store.json"
    payload = json.loads(store.read_text(encoding="utf-8"))
    for rid, rd in payload["runs"].items():
        if rd.get("pending_proposal_id"):
            return rid, rd["pending_proposal_id"]
    raise AssertionError("no pending proposal in store")


# -- console: brief --------------------------------------------------------


def test_cli_brief_runs_line_and_halts_at_draft_assembly(home, capsys):
    cmd_lwp(_brief_args())
    out = capsys.readouterr().out
    assert "awaiting_approval" in out
    assert "draft_assembly" in out
    assert "levi lwp approve --proposal" in out


def test_cli_brief_rejects_bad_kind(home, capsys):
    cmd_lwp(_brief_args(kind="pamphlet"))
    out = capsys.readouterr().out
    assert out.startswith("lwp: ")
    assert "kind must be one of" in out


# -- console: full human-gated flow across invocations ---------------------


def test_cli_full_flow_brief_approve_publish(home, capsys):
    cmd_lwp(_brief_args(kind="reversible", target_words=2))
    capsys.readouterr()
    rid, pid = _pending_proposal(home)

    # Fresh console invocations approve every human gate in turn:
    # draft assembly, one mandella stake per pair pass, then the seal.
    approvals = 0
    while pid is not None:
        cmd_lwp(_ns(lwp_action="approve", proposal=pid, note="keeper: approved"))
        capsys.readouterr()
        approvals += 1
        assert approvals <= 10, "approval chain did not terminate"
        try:
            rid2, pid = _pending_proposal(home)
        except AssertionError:
            pid = None
    assert approvals == 4  # draft_assembly, mandella x2, publish_ready seal
    assert rid2 == rid

    # Sealed: now publish.
    cmd_lwp(_ns(lwp_action="publish", run=rid, note="keeper release"))
    out = capsys.readouterr().out
    assert out.startswith("published 'Console Test'")

    # The reversible draft pressed real books.
    cmd_lwp(_ns(lwp_action="status", run=rid, text=True))
    out = capsys.readouterr().out
    assert "Book 1" in out and "Book 2" in out
    assert "26-clause pool" in out


def test_cli_deny_stops_run(home, capsys):
    cmd_lwp(_brief_args())
    capsys.readouterr()
    rid, pid = _pending_proposal(home)
    cmd_lwp(_ns(lwp_action="deny", proposal=pid, note="keeper: no"))
    assert "denied" in capsys.readouterr().out
    cmd_lwp(_ns(lwp_action="publish", run=rid))
    assert "was denied" in capsys.readouterr().out


def test_cli_publish_before_seal_refused(home, capsys):
    cmd_lwp(_brief_args())
    capsys.readouterr()
    rid, _pid = _pending_proposal(home)
    cmd_lwp(_ns(lwp_action="publish", run=rid))
    out = capsys.readouterr().out
    assert out.startswith("lwp: ")
    assert "not sealed" in out


def test_cli_status_lists_pending(home, capsys):
    cmd_lwp(_brief_args())
    capsys.readouterr()
    cmd_lwp(_ns(lwp_action="status"))
    out = capsys.readouterr().out
    assert "proposal" in out and "draft_assembly" in out


def test_cli_status_empty(home, capsys):
    cmd_lwp(_ns(lwp_action="status"))
    assert "no proposals awaiting approval" in capsys.readouterr().out


# -- console: press + seats -------------------------------------------------


def test_cli_press_prints_books(home, capsys):
    cmd_lwp(_ns(lwp_action="press", count=2, seed=7))
    out = capsys.readouterr().out
    assert "— Book 1 (" in out and "— Book 2 (" in out
    assert "Dawn breaks, breaks dawn." in out


def test_cli_seats(home, capsys):
    cmd_lwp(_ns(lwp_action="seats"))
    out = capsys.readouterr().out
    for stage in ("ideation", "drafting", "revision", "polish", "publish_ready"):
        assert stage in out


# -- machine: persistence ----------------------------------------------------


def _brief():
    return ProductionBrief(
        title="Persistence Test",
        brief_text="A short honest brief for the persistence test.",
        kind="prose",
        direction="forward",
        phase="gold_push",
        power="gain",
    )


def test_store_roundtrip_across_machine_instances(tmp_path):
    led = tmp_path / "ledger.jsonl"
    m1 = ContentMachine(ledger_path=led)
    run = m1.run_brief(_brief())
    pid = run.pending_proposal_id

    m2 = ContentMachine(ledger_path=led)  # fresh instance, same ledger
    assert m2.get_run(run.run_id).status == "awaiting_approval"
    run2 = m2.approve(pid, note="keeper: draft it")
    assert [r.stage for r in run2.records][:2] == [
        "draft_assembly",
        "echo_mandella:pass1",
    ]

    # Walk every remaining human gate across a third instance: one mandella
    # stake per pair pass, then the publish-ready seal. The run seals.
    m3 = ContentMachine(ledger_path=led)
    run3 = m3.get_run(run.run_id)
    approvals = 0
    while run3.pending_proposal_id:
        run3 = m3.approve(run3.pending_proposal_id, note="keeper: approved")
        approvals += 1
        assert approvals <= 10, "approval chain did not terminate"
    assert approvals == 3  # mandella:pass1, mandella:pass2, publish_ready seal
    assert run3.status == "sealed"
    assert run3.pending_stage is None


def test_store_is_per_ledger_file(tmp_path):
    m1 = ContentMachine(ledger_path=tmp_path / "a.jsonl")
    m1.run_brief(_brief())
    m2 = ContentMachine(ledger_path=tmp_path / "b.jsonl")
    assert m2.pending() == []
    assert list(m2._runs) == []


def test_store_file_written_beside_ledger(tmp_path):
    led = tmp_path / "ledger.jsonl"
    ContentMachine(ledger_path=led).run_brief(_brief())
    store = tmp_path / "ledger.store.json"
    assert store.exists()
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 1
    assert payload["policy"]["pending"]
