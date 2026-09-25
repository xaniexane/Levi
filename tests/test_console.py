"""Hermetic tests for the LEVI interactive console (``levi console``).

No network, no real HOME writes: scope/finding stores are bound to tmp
paths and ``run_recon`` is monkeypatched. Menus are driven end-to-end
by monkeypatching ``builtins.input`` with scripted answers.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from levi.bounty.scope import ScopeStore
from levi.bounty.store import FindingStore
from levi.console import screens
from levi.console.app import run
from levi.console.helpers import (
    browser_command,
    paginate,
    resolve_view_arg,
    search_domains,
    stage_for_kind,
    tier_color,
)
from levi.console.screens import SCREENS
from levi.demand.pulse import DemandPulse
from levi.demand.scoring import FACTORS, FactorScore


# ---------------------------------------------------------------------------
# scripted input driver
# ---------------------------------------------------------------------------


class ScriptedInput:
    """Feed scripted answers to builtins.input; EOF when exhausted."""

    def __init__(self, answers):
        self._answers = list(answers)

    def __call__(self, prompt=""):
        if not self._answers:
            raise EOFError("scripted input exhausted")
        return self._answers.pop(0)


def _tty(monkeypatch):
    """Pretend stdin/stdout are interactive."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)


def _fake_domain(i, **kw):
    base = {
        "id": f"domain-{i}",
        "name": f"Domain {i}",
        "defensive_summary": "a defensive summary about networks",
        "detection_notes": "detect things",
        "hardening_notes": "harden things",
        "key_concepts": ["concept-a", "concept-b", "concept-c"],
        "reference": "ref",
        "attack_relevant": False,
        "attack_profile": "",
    }
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# non-TTY guard
# ---------------------------------------------------------------------------


def test_run_refuses_non_tty_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert run() == 1
    assert "levi console needs an interactive terminal." in capsys.readouterr().out


def test_run_refuses_non_tty_stdout(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert run() == 1
    assert "levi console needs an interactive terminal." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_search_domains_matches_name_summary_concepts():
    domains = [
        _fake_domain(1, name="Android Security"),
        _fake_domain(2, name="Web Stuff", key_concepts=["xss", "csrf", "sqli"]),
        _fake_domain(3, name="Other", hardening_notes="rotate android keys"),
    ]
    assert [d.id for d in search_domains(domains, "android")] == [
        "domain-1",
        "domain-3",
    ]
    assert [d.id for d in search_domains(domains, "XSS")] == ["domain-2"]
    assert [d.id for d in search_domains(domains, "nope")] == []


def test_search_domains_blank_query_returns_all():
    domains = [_fake_domain(1), _fake_domain(2)]
    assert search_domains(domains, "   ") == domains


def test_paginate_81_entries_15_per_page():
    items = list(range(81))
    page1, total = paginate(items, 1, 15)
    assert (len(page1), total) == (15, 6)
    assert page1[0] == 0
    last, _ = paginate(items, 6, 15)
    assert last == list(range(75, 81))
    clamped, _ = paginate(items, 99, 15)
    assert clamped == list(range(75, 81))
    empty, total_pages = paginate([], 1, 15)
    assert (empty, total_pages) == ([], 0)
    with pytest.raises(ValueError):
        paginate(items, 1, 0)


def test_browser_command_parsing():
    assert browser_command("n") == ("next", "")
    assert browser_command("P") == ("prev", "")
    assert browser_command("s") == ("search", "")
    assert browser_command("b") == ("back", "")
    assert browser_command("q") == ("back", "")
    assert browser_command("c") == ("clear", "")
    assert browser_command("v android-security") == ("view", "android-security")
    assert browser_command("3") == ("view", "3")
    assert browser_command("") == ("invalid", "")
    assert browser_command("xyzzy") == ("invalid", "")


def test_resolve_view_arg_by_row_and_id():
    domains = [_fake_domain(1), _fake_domain(2)]
    page_items = [domains[1]]
    assert resolve_view_arg(domains, page_items, "1") is domains[1]
    assert resolve_view_arg(domains, page_items, "9") is None
    assert resolve_view_arg(domains, page_items, "domain-1") is domains[0]
    assert resolve_view_arg(domains, page_items, "nope") is None


def test_tier_color_and_stage_for_kind():
    assert tier_color("high") == "green"
    assert tier_color("watch") == "yellow"
    assert tier_color("low") == "red"
    assert tier_color("mystery") == "gray"
    assert stage_for_kind("subdomain") == 0
    assert stage_for_kind("open_port") == 1
    assert stage_for_kind("tls_cert") == 1
    assert stage_for_kind("archived_url") == 2
    assert stage_for_kind("possible_exposure") == 2
    assert stage_for_kind("unknown-kind") == 2


def test_screens_registry_contents():
    assert set(SCREENS) == {"security", "bounty", "demand"}
    for _, (title, handler) in SCREENS.items():
        assert isinstance(title, str) and title
        assert callable(handler)
    titles = [t for t, _ in SCREENS.values()]
    assert titles == ["Security index browser", "Bounty recon", "Demand digest"]


# ---------------------------------------------------------------------------
# scripted end-to-end: security browser
# ---------------------------------------------------------------------------


def test_session_open_browser_search_back_quit(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setattr(
        "builtins.input", ScriptedInput(["1", "s", "android", "b", "4"])
    )
    assert run() == 0
    out = capsys.readouterr().out
    assert "Security index" in out
    assert "Android Security" in out  # search hit rendered in the table
    assert "Goodbye." in out


def test_session_browser_view_entry(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setattr("builtins.input", ScriptedInput(["1", "v 1", "", "b", "4"]))
    assert run() == 0
    out = capsys.readouterr().out
    assert "-- detection --" in out
    assert "-- hardening --" in out
    assert "-- key concepts --" in out


def test_session_browser_empty_search_then_quit(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setattr(
        "builtins.input", ScriptedInput(["1", "s", "zzz-no-such-domain", "b", "4"])
    )
    assert run() == 0
    assert "No security domains match" in capsys.readouterr().out


def test_browser_corrupt_catalog_back_to_menu(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setattr(screens, "_load_domains", lambda: None)
    monkeypatch.setattr("builtins.input", ScriptedInput(["1", "", "4"]))
    assert run() == 0  # corrupt index -> message -> back to menu -> quit


# ---------------------------------------------------------------------------
# scripted end-to-end: bounty recon (run_recon monkeypatched)
# ---------------------------------------------------------------------------


def _fake_run_recon(domain, findings=None, **kwargs):
    if findings is not None:
        findings.add(domain, domain, "subdomain", "resolves to 93.184.216.34")
        findings.add(domain, domain, "open_port", "tcp/443 open")
        findings.add(domain, domain, "archived_url", "https://web.archive.org/x")
    return {
        "domain": domain,
        "subdomains": ["www." + domain],
        "hosts_probed": 1,
        "findings_new": 3,
        "errors": ["probe edge: simulated timeout"],
    }


@pytest.fixture()
def hermetic_bounty(monkeypatch, tmp_path):
    """Scope + finding stores bound to tmp paths; recon pipeline stubbed."""
    monkeypatch.setattr(
        screens, "ScopeStore", lambda: ScopeStore(tmp_path / "scopes.json")
    )
    monkeypatch.setattr(
        screens,
        "_LiveFindingStore",
        lambda on_finding: _PatchedLiveStore(on_finding, tmp_path),
    )
    monkeypatch.setattr(screens, "run_recon", _fake_run_recon)
    store = ScopeStore(tmp_path / "scopes.json")
    store.add("example.com")
    return store


class _PatchedLiveStore(FindingStore):
    """FindingStore with the live-feed callback, bound to a tmp path."""

    def __init__(self, on_finding, tmp_path):
        super().__init__(path=tmp_path / "findings.json")
        self._on_finding = on_finding

    def add(self, target, scope, kind, detail, evidence=""):
        finding, is_new = super().add(target, scope, kind, detail, evidence)
        self._on_finding(finding, is_new)
        return finding, is_new


def test_session_bounty_recon_results(monkeypatch, capsys, hermetic_bounty):
    _tty(monkeypatch)
    # 2=bounty, 1=first scope, y=confirm, ""=pause after results, q=back, 4=quit
    monkeypatch.setattr("builtins.input", ScriptedInput(["2", "1", "y", "", "q", "4"]))
    assert run() == 0
    out = capsys.readouterr().out
    assert "Recon results" in out
    assert "open_port" in out
    assert "tcp/443 open" in out
    assert "simulated timeout" in out  # error list rendered


def test_bounty_enroll_new_scope_then_recon(monkeypatch, capsys, tmp_path):
    _tty(monkeypatch)
    monkeypatch.setattr(
        screens, "ScopeStore", lambda: ScopeStore(tmp_path / "scopes.json")
    )
    monkeypatch.setattr(screens, "run_recon", _fake_run_recon)
    monkeypatch.setattr(
        screens,
        "_LiveFindingStore",
        lambda on_finding: _PatchedLiveStore(on_finding, tmp_path),
    )
    # 2=bounty, enroll? y, domain, pick it (1), confirm y, pause "", back q, quit 4
    monkeypatch.setattr(
        "builtins.input",
        ScriptedInput(["2", "y", "Example.COM.", "1", "y", "", "q", "4"]),
    )
    assert run() == 0
    out = capsys.readouterr().out
    assert "Enrolled" in out and "example.com" in out
    assert "Recon results" in out


def test_bounty_enroll_bad_domain_shows_error(monkeypatch, capsys, tmp_path):
    _tty(monkeypatch)
    monkeypatch.setattr(
        screens, "ScopeStore", lambda: ScopeStore(tmp_path / "scopes.json")
    )
    # 2=bounty, enroll? y, bad domain, then blank cancels, then q back... (no scopes -> return to menu), 4 quit
    monkeypatch.setattr(
        "builtins.input",
        ScriptedInput(["2", "y", "not a domain!!", "", "4"]),
    )
    assert run() == 0
    assert "Cannot enroll" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# scripted end-to-end: demand digest
# ---------------------------------------------------------------------------


def _seed_card(pulse: DemandPulse):
    factors = {
        name: FactorScore(name=name, value=80.0, basis=f"basis for {name}")
        for name in FACTORS
    }
    return pulse.score_five_factor("d1", "Test Opportunity", factors)


def test_session_demand_digest_with_cards(monkeypatch, capsys, tmp_path):
    _tty(monkeypatch)
    pulse = DemandPulse(tmp_path / "dp.json")
    _seed_card(pulse)
    monkeypatch.setattr(
        screens, "DemandPulse", lambda: DemandPulse(tmp_path / "dp.json")
    )
    monkeypatch.setattr("builtins.input", ScriptedInput(["3", "", "4"]))
    assert run() == 0
    out = capsys.readouterr().out
    assert "Demand digest" in out
    assert "Test Opportunity" in out
    assert "high" in out  # 80 composite -> high tier


def test_session_demand_digest_empty_state(monkeypatch, capsys, tmp_path):
    _tty(monkeypatch)
    monkeypatch.setattr(
        screens, "DemandPulse", lambda: DemandPulse(tmp_path / "dp.json")
    )
    monkeypatch.setattr("builtins.input", ScriptedInput(["3", "", "4"]))
    assert run() == 0
    assert "No score cards yet" in capsys.readouterr().out


def test_menu_eof_quits_cleanly(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setattr("builtins.input", ScriptedInput([]))
    assert run() == 0
