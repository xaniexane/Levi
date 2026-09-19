"""Tests for the Dweller re-chartered as purgatory-dweller, Leviathan-class.

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path. The
fog sweep is skipped in ledger tests (``include_fog=False``) to keep
them fast; one test exercises the fog realm live.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from levi.automation.hitl import auto_approve, auto_deny
from levi.dweller import charter
from levi.dweller.cli import cmd_dweller, register_dweller_parser
from levi.dweller.purgatory import (
    gather_purgatory,
    read_dead_letters,
    read_unborn,
    render_ledger,
    tending_log,
)
from levi.dweller.tend import (
    compost_review,
    redrive_dead_letter,
    release_dead_letter,
    unborn_watch,
)
from levi.nexus.bus import Nexus
from levi.nexus.envelope import Envelope
from levi.si_team.roles import DWELLER_CHARTER


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolated LEVI_HOME."""
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


@pytest.fixture()
def docs(tmp_path):
    """Minimal concept inventory with UNBORN rows."""
    d = tmp_path / "DREAM_PRODUCTS.md"
    d.write_text(
        "# Inventory\n\n"
        "| Concept | What it was | Status | Notes |\n"
        "|---|---|---|---|\n"
        "| Alpha | First mind | UNBORN | Never built. Needs a build wave. |\n"
        "| Nexus | Connector | LIVE | Working organ. |\n"
        "| Omega | Judge | UNBORN | Platform partial; mind unborn. |\n",
        encoding="utf-8",
    )
    return d


def _seed_dead_letter(home: Path) -> None:
    nexus = Nexus(home=home)
    env = Envelope(
        from_organ="alpha",
        to_organ="no-such-organ",
        kind="consult",
        payload={"q": "x"},
    )
    nexus.dead_letter(env, "unknown organ: no-such-organ")


# ---------------------------------------------------------------------------
# charter identity
# ---------------------------------------------------------------------------


def test_charter_is_leviathan_class_purgatory_dweller():
    charter.assert_identity()
    assert charter.CLASS == "leviathan-class"
    assert charter.EPITHET == "purgatory-dweller"
    assert len(charter.PURGATORY_REALMS) == 5


def test_roster_charter_rechartered():
    assert DWELLER_CHARTER.name == "dweller"
    assert "purgatory" in DWELLER_CHARTER.mandate.lower()
    assert "leviathan" in DWELLER_CHARTER.mandate.lower()
    assert any("permission gate" in b for b in DWELLER_CHARTER.boundaries)
    assert any("receipt" in b for b in DWELLER_CHARTER.boundaries)
    assert "Levi or LEVI" in " ".join(DWELLER_CHARTER.boundaries)


# ---------------------------------------------------------------------------
# purgatory ledger
# ---------------------------------------------------------------------------


def test_empty_purgatory_renders_cleanly(home, docs):
    ledger = gather_purgatory(base=home, docs_path=docs, include_fog=False)
    realms = {r["realm"]: r for r in ledger["realms"]}
    assert set(realms) == {
        "dead-letters",
        "compost",
        "denied-gates",
        "unborn",
    }
    # only the fixture's two unborn wait; the other realms are quiet
    assert ledger["waiting"] == 2
    assert realms["dead-letters"]["count"] == 0
    assert realms["compost"]["count"] == 0
    assert realms["denied-gates"]["count"] == 0
    # unreachable sources are reported, not fabricated
    assert realms["dead-letters"]["status"] == "unreachable"
    text = render_ledger(ledger)
    assert "nothing waiting" in text
    assert "Alpha" in text and "Omega" in text


def test_dead_letters_aggregated(home):
    _seed_dead_letter(home)
    entries, status, note = read_dead_letters(home)
    assert status == "live"
    assert len(entries) == 1
    assert entries[0]["reason"] == "unknown organ: no-such-organ"
    ledger = gather_purgatory(base=home, include_fog=False)
    realms = {r["realm"]: r for r in ledger["realms"]}
    assert realms["dead-letters"]["count"] == 1
    text = render_ledger(ledger)
    assert "alpha → no-such-organ" in text
    assert "unknown organ" in text


def test_denied_gates_source_honest(home):
    # automation persists no gate receipts — the ledger says so, honestly
    from levi.dweller.purgatory import read_denied_gates

    entries, status, note = read_denied_gates(home)
    assert status == "live"
    assert "no gate receipts" in note


def test_unborn_parsed_from_inventory(docs):
    entries, status, note = read_unborn(docs)
    assert status == "live"
    names = [e["name"] for e in entries]
    assert names == ["Alpha", "Omega"]
    assert "2 unborn" in note


def test_unborn_missing_inventory_reports_unreachable(tmp_path):
    entries, status, note = read_unborn(tmp_path / "nope.md")
    assert status == "unreachable"
    assert entries == []


def test_fog_realm_live():
    from levi.dweller.purgatory import read_fog_verdicts

    waiting, status, note = read_fog_verdicts()
    assert status == "live"
    assert "phantom runs" in note
    assert waiting == []  # the sweep is fail-closed; nothing waits


# ---------------------------------------------------------------------------
# tending rites
# ---------------------------------------------------------------------------


def _failure_record(**kw):
    record = {
        "source": "test",
        "what": "watch timed out twice",
        "context": "dweller watch rite",
        "ts": "2026-09-17T00:00:00+00:00",
        "severity": "high",
    }
    record.update(kw)
    return record


def test_compost_review_surfaces_candidates(home):
    receipt = compost_review(
        [_failure_record(), _failure_record(what="watch timed out again")],
        base=home,
    )
    assert receipt["rite"] == "compost-review"
    assert receipt["records_reviewed"] == 2
    assert receipt["genome_candidates"] >= 1  # high severity promotes
    heap = home / ".levi" / "dweller" / "compost.jsonl"
    assert heap.exists()
    assert len(heap.read_text(encoding="utf-8").strip().splitlines()) == 2
    # tending log records the rite
    assert any(r["rite"] == "compost-review" for r in tending_log(home))
    # reviewed compost now waits in the ledger
    ledger = gather_purgatory(base=home, include_fog=False)
    realms = {r["realm"]: r for r in ledger["realms"]}
    assert realms["compost"]["count"] == 2


def test_redrive_denied_gate_stays_put(home):
    _seed_dead_letter(home)
    receipt = redrive_dead_letter(0, responder=auto_deny, base=home)
    assert receipt["decision"] == "denied"
    assert "gate denied" in receipt["note"]
    # the letter is still in the store — the in-between never routes
    # around the human
    entries, _, _ = read_dead_letters(home)
    assert len(entries) == 1
    assert any(r["rite"] == "re-drive-denied" for r in tending_log(home))


def test_redrive_approved_routes(home):
    _seed_dead_letter(home)
    receipt = redrive_dead_letter(0, responder=auto_approve, base=home)
    assert receipt["decision"] == "redriven"
    assert receipt["route"]["status"] == "dead-lettered"  # organ still unknown
    log = tending_log(home)
    assert any(r["rite"] == "re-drive" for r in log)
    # the original letter is marked tended; the re-driven route returned
    # a new dead letter (its organ still does not exist) — purgatory is
    # honest about that too
    ledger = gather_purgatory(base=home, include_fog=False)
    realms = {r["realm"]: r for r in ledger["realms"]}
    assert realms["dead-letters"]["entries"][0]["tended"]["rite"] == "re-drive"
    assert realms["dead-letters"]["count"] == 1


def test_release_is_receipted(home):
    _seed_dead_letter(home)
    receipt = release_dead_letter(0, "superseded by a newer design", base=home)
    assert receipt["decision"] == "released"
    assert receipt["reason"] == "superseded by a newer design"
    assert any(r["rite"] == "release" for r in tending_log(home))


def test_redrive_unknown_index_is_clean_error(home):
    with pytest.raises(KeyError):
        redrive_dead_letter(7, responder=auto_approve, base=home)


def test_unborn_watch_reports_needs(docs):
    watch = unborn_watch(docs)
    assert watch["rite"] == "unborn-watch"
    assert len(watch["unborn"]) == 2
    for item in watch["unborn"]:
        assert item["needs"], "every unborn thing must name what it needs"
        assert "build wave" in item["needs"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse(argv):
    parser = argparse.ArgumentParser(prog="levi")
    sub = parser.add_subparsers(dest="cmd", required=True)
    register_dweller_parser(sub)
    return parser.parse_args(argv)


def test_cli_purgatory(home, docs, capsys):
    rc = cmd_dweller(_parse(["dweller", "purgatory", "--no-fog"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "PURGATORY" in out
    assert "dead-letters" in out


def test_cli_tend_unborn_watch(docs, capsys, monkeypatch):
    # point the rite at the fixture inventory
    import levi.dweller.cli as cli_mod

    monkeypatch.setattr(cli_mod, "unborn_watch", lambda: unborn_watch(docs))
    rc = cmd_dweller(_parse(["dweller", "tend", "unborn-watch"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "unborn-watch" in out


def test_cli_tend_redrive_denied_noninteractive(home, capsys):
    _seed_dead_letter(home)
    # no --yes and non-tty stdin: the console responder denies
    rc = cmd_dweller(_parse(["dweller", "tend", "re-drive", "--index", "0"]))
    assert rc == 1
    out = capsys.readouterr().out
    assert "denied" in out
