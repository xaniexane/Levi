"""Hermetic tests for the Galaxy pre-call governor gates
(docs/GALAXY.md "Pre-call governor gates").

``GalaxyServices.call`` must consult ``budgets.authorize()`` and
``cooldowns.acquire(scope=f"galaxy:{port}")`` before invoking a verb,
refusing deny-closed (``BudgetDenied`` / ``CooldownDenied``) — and the
enforcers are injected the way the Meter is. No network, no user HOME
writes.
"""

import json
import sys
import types

import pytest

from levi.galaxy.service import (
    BudgetDenied,
    CooldownDenied,
    GalaxyServices,
)
from levi.governor.cooldown import CooldownManager, Grant
from levi.governor.budgets import BudgetEnforcer
from levi.governor.meter import Meter


def _make_module(name: str, **functions) -> types.ModuleType:
    module = types.ModuleType(name)
    for fname, fn in functions.items():
        setattr(module, fname, fn)
    sys.modules[name] = module
    return module


_calls = {"echo": 0}


def _echo_module():
    def echo(text=""):
        _calls["echo"] += 1
        return f"echo:{text}"

    return _make_module("fake_galaxy_echo_mod", echo=echo)


@pytest.fixture()
def installed(tmp_path):
    _echo_module()
    _calls["echo"] = 0
    home = tmp_path / "home"
    svc = GalaxyServices(
        store_dir=tmp_path / "store",
        meter=Meter(home=home),
        budgets=BudgetEnforcer(home=home),
        cooldowns=CooldownManager(home=home),
    )
    svc.install(
        {
            "id": "budgettest.echo",
            "name": "Echo demo",
            "version": "1.0.0",
            "description": "fake skill package for governor-gate tests",
            "author": "acme",
            "kind": "skill",
            "entry_points": {"echo": "fake_galaxy_echo_mod:echo"},
        },
        source="test",
    )
    cap = svc.issue_capability("test-executor", ["galaxy.budgettest.echo.*"])
    return svc, cap


class _OpenBudgets:
    def authorize(self, extra_tokens=0):
        return True, "within budget"


class _DeniedBudgets:
    def authorize(self, extra_tokens=0):
        return False, "session budget exhausted: 200,000 used of 200,000 tokens"


class _OpenCooldowns:
    def acquire(self, scope, pass_id=None):
        assert scope == "galaxy:budgettest.echo", f"wrong scope {scope!r}"
        return Grant(True, "circuit closed")


class _DeniedCooldowns:
    def acquire(self, scope, pass_id=None):
        return Grant(False, "genuine contention on 'galaxy:budgettest.echo'")


def _call_kwargs(installed):
    _, cap = installed
    return dict(
        args=["hi"],
        capability=cap,
        grantee="test-executor",
    )


def test_call_passes_open_gates(installed):
    svc, _ = installed
    assert (
        svc.call("galaxy.budgettest.echo", "echo", **_call_kwargs(installed))
        == "echo:hi"
    )
    assert _calls["echo"] == 1


def test_call_budget_denied_refuses_without_invoking(installed):
    svc, _ = installed
    svc._budgets = _DeniedBudgets()
    with pytest.raises(BudgetDenied, match="session budget exhausted"):
        svc.call("galaxy.budgettest.echo", "echo", **_call_kwargs(installed))
    assert _calls["echo"] == 0, "verb must not run when the budget gate refuses"


def test_call_cooldown_denied_refuses_without_invoking(installed):
    svc, _ = installed
    svc._budgets = _OpenBudgets()
    svc._cooldowns = _DeniedCooldowns()
    with pytest.raises(CooldownDenied, match="genuine contention"):
        svc.call("galaxy.budgettest.echo", "echo", **_call_kwargs(installed))
    assert _calls["echo"] == 0, "verb must not run when the cool-down gate refuses"


def test_enforcers_are_injected_not_rebuilt(tmp_path):
    home = tmp_path / "home"
    budgets, cooldowns = _OpenBudgets(), _OpenCooldowns()
    svc = GalaxyServices(
        store_dir=tmp_path / "store",
        meter=Meter(home=home),
        budgets=budgets,
        cooldowns=cooldowns,
    )
    assert svc._budgets is budgets
    assert svc._cooldowns is cooldowns


def test_denials_are_metered(tmp_path):
    home = tmp_path / "home"
    svc = GalaxyServices(
        store_dir=tmp_path / "store",
        meter=Meter(home=home),
        budgets=_DeniedBudgets(),
        cooldowns=_OpenCooldowns(),
    )
    cap = svc.issue_capability("metered", ["galaxy.budgettest.nope.*"])
    with pytest.raises(BudgetDenied):
        svc.call("galaxy.budgettest.nope", "echo", capability=cap, grantee="metered")
    ledger = home / ".levi" / "governor" / "usage.jsonl"
    records = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    assert any(r.get("error") == "BudgetDenied" for r in records)


def test_default_real_enforcers_allow_fresh_call(tmp_path):
    _echo_module()
    _calls["echo"] = 0
    home = tmp_path / "home2"
    svc = GalaxyServices(
        store_dir=tmp_path / "store2", meter=Meter(home=home), home=home
    )
    svc.install(
        {
            "id": "budgettest.echo2",
            "name": "Echo demo 2",
            "version": "1.0.0",
            "description": "x",
            "author": "acme",
            "kind": "skill",
            "entry_points": {"echo": "fake_galaxy_echo_mod:echo"},
        },
        source="test",
    )
    cap = svc.issue_capability("e2", ["galaxy.budgettest.echo2.*"])
    assert (
        svc.call(
            "galaxy.budgettest.echo2", "echo", args=["yo"], capability=cap, grantee="e2"
        )
        == "echo:yo"
    )
