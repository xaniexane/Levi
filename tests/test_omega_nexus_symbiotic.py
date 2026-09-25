"""Symbiotic proof for the Nexus organ: guarded routing on the shared substrate.

The invariant under test:

    "Nexus never routes through a source LEVI doesn't own, and never
    routes above the approved ceiling. A refusal is a receipt, not silence."

Proof, honestly named: behavioral tests pinning the refusal paths, the
ceiling gate, the HITL gate, and the sourcing law under
``route_guarded``. This is not a formal verification — it is a
machine-checkable guard over the stated invariant.
"""

import pytest

from levi.revival.omega import nexus as nx
from levi.revival.omega import substrate as sub


def _providers():
    return [
        nx.Provider(
            name="levi-local",
            source=nx.SOURCE_LOCAL,
            kinds=frozenset({"chat", "code", "browser", "irreversible"}),
            cost=1,
            quality=0.6,
        ),
        nx.Provider(
            name="levi-si-cloud",
            source=nx.SOURCE_CLOUD,
            kinds=frozenset({"chat", "code", "vision"}),
            cost=4,
            quality=0.9,
        ),
        nx.Provider(
            name="rival-a",
            source=nx.SOURCE_REFERENCE,
            kinds=frozenset({"chat", "code", "browser", "vision"}),
            cost=1,
            quality=1.0,
        ),
    ]


def _route_receipt(s, receipt_id, kind="route"):
    r = s.get_receipt(receipt_id)
    assert r is not None
    assert r.organ == "nexus"
    assert r.kind == kind
    return r


# ---- assess_task_risk: the documented heuristic ----


def test_risk_plain_task_is_standard():
    assert nx.assess_task_risk({"kinds": {"chat"}}) == "standard"
    assert nx.assess_task_risk({"kinds": set()}) == "standard"
    assert nx.assess_task_risk({}) == "standard"


def test_risk_elevated_kinds():
    for kinds in (
        {"browser"},
        {"payment"},
        {"money"},
        {"write"},
        {"deploy"},
        {"network"},
        {"exec"},
        {"shell"},
    ):
        assert nx.assess_task_risk({"kinds": kinds}) == "elevated", kinds


def test_risk_critical_kinds():
    for kinds in ({"hitl"}, {"irreversible"}, {"external-send"}):
        assert nx.assess_task_risk({"kinds": kinds}) == "critical", kinds


def test_risk_critical_beats_elevated():
    assert nx.assess_task_risk({"kinds": {"browser", "irreversible"}}) == "critical"


def test_risk_explicit_wins_when_valid():
    assert nx.assess_task_risk({"kinds": {"chat"}, "risk": "elevated"}) == "elevated"
    assert nx.assess_task_risk({"kinds": {"browser"}, "risk": "standard"}) == "standard"


def test_risk_invalid_explicit_falls_through_to_heuristic():
    assert nx.assess_task_risk({"kinds": {"browser"}, "risk": "bogus"}) == "elevated"


def test_risk_non_dict_task_raises_loudly():
    with pytest.raises(ValueError):
        nx.assess_task_risk("chat")


# ---- sourcing law under the guard: reference is never chosen ----


def test_reference_never_chosen_even_if_it_covers_everything():
    # rival-a is cheaper, higher quality, covers all kinds — still never
    # operational. A refusal is a receipt, not silence, but here a lawful
    # provider exists so the route must land on LEVI-owned iron.
    s = sub.SharedSubstrate()
    out = nx.route_guarded(s, {"kinds": {"browser"}}, _providers(),
                           approved_by="daemon:test")
    assert out["ok"] is True
    assert out["provider"] in {"levi-local", "levi-si-cloud"}
    assert out["provider"] != "rival-a"
    r = _route_receipt(s, out["receipt_id"])
    assert r.payload["provider"] == out["provider"]


def test_reference_alone_is_a_refusal_receipt_not_silence():
    s = sub.SharedSubstrate()
    providers = [nx.Provider(name="rival-a", kinds=frozenset({"chat"}))]
    out = nx.route_guarded(s, {"kinds": {"chat"}}, providers)
    assert out["ok"] is False
    assert out["refusal"] == "no eligible provider"
    assert out["ceiling"] == "standard"
    r = _route_receipt(s, out["receipt_id"], kind="route_refusal")
    assert r.risk == "standard"
    assert any("reference-only" in x for x in r.payload["exclusions"])


# ---- the ceiling gate: elevated needs a recorded approval ----


def test_elevated_task_without_approval_is_refused_with_receipt():
    s = sub.SharedSubstrate()
    task = {"kinds": {"browser"}}  # elevated by heuristic
    assert nx.assess_task_risk(task) == "elevated"
    out = nx.route_guarded(s, task, _providers())
    assert out["ok"] is False
    assert out["refusal"] == "approval required"
    assert out["ceiling"] == "elevated"
    r = _route_receipt(s, out["receipt_id"], kind="route_refusal")
    assert r.risk == "elevated"
    assert "approval required for ceiling elevated" in r.payload["reason"]
    assert r.payload["task_kinds"] == ["browser"]
    # the refusal is consumable evidence — interrogation never collapses
    assert s.is_consumable(r.id)


def test_elevated_task_with_approval_routes_and_records_it():
    s = sub.SharedSubstrate()
    out = nx.route_guarded(
        s, {"kinds": {"browser"}}, _providers(), approved_by="daemon:sched-1"
    )
    assert out["ok"] is True
    assert out["ceiling"] == "elevated"
    r = _route_receipt(s, out["receipt_id"])
    assert r.risk == "elevated"
    assert r.approved_by == "daemon:sched-1"


def test_elevated_never_routes_above_ceiling_silently():
    # strictest ceiling wins: even though nexus itself is standard, the
    # elevated task inherits the elevated ceiling.
    s = sub.SharedSubstrate()
    out = nx.route_guarded(s, {"kinds": {"exec"}}, _providers())
    assert out["ok"] is False
    assert out["ceiling"] == "elevated"
    assert len(s.receipts(kind="route")) == 0  # nothing routed


# ---- the HITL gate: critical needs an explicit human hand ----


def test_critical_task_with_plain_approval_is_still_refused():
    s = sub.SharedSubstrate()
    task = {"kinds": {"irreversible"}}
    assert nx.assess_task_risk(task) == "critical"
    out = nx.route_guarded(s, task, _providers(), approved_by="daemon:sched-9")
    assert out["ok"] is False
    assert out["refusal"] == "approval required"
    assert out["ceiling"] == "critical"
    r = _route_receipt(s, out["receipt_id"], kind="route_refusal")
    assert r.risk == "critical"
    assert r.payload["hitl"] is True
    assert "hitl:" in r.payload["reason"]


def test_critical_task_without_any_approval_is_refused():
    s = sub.SharedSubstrate()
    out = nx.route_guarded(s, {"kinds": {"external-send"}}, _providers())
    assert out["ok"] is False
    assert out["refusal"] == "approval required"
    assert out["ceiling"] == "critical"


def test_critical_task_with_hitl_approval_routes_and_marks_hitl():
    s = sub.SharedSubstrate()
    out = nx.route_guarded(
        s, {"kinds": {"irreversible"}}, _providers(), approved_by="hitl:chauncey"
    )
    assert out["ok"] is True
    assert out["ceiling"] == "critical"
    r = _route_receipt(s, out["receipt_id"])
    assert r.risk == "critical"
    assert r.approved_by == "hitl:chauncey"
    assert r.payload["hitl"] is True  # loud: a human hand was on this route


# ---- offline mode stays deny-closed, with a receipt ----


def test_offline_with_no_local_providers_is_a_refusal_receipt():
    s = sub.SharedSubstrate()
    providers = [
        nx.Provider(name="levi-si-cloud", source=nx.SOURCE_CLOUD,
                    kinds=frozenset({"chat"})),
    ]
    out = nx.route_guarded(s, {"kinds": {"chat"}}, providers, mode="offline")
    assert out["ok"] is False
    assert out["refusal"] == "no eligible provider"
    r = _route_receipt(s, out["receipt_id"], kind="route_refusal")
    assert r.payload["mode"] == "offline"
    assert any("LEVI-local only" in x for x in r.payload["exclusions"])


def test_offline_with_local_provider_routes():
    s = sub.SharedSubstrate()
    out = nx.route_guarded(s, {"kinds": {"chat"}}, _providers(), mode="offline")
    assert out["ok"] is True
    assert out["provider"] == "levi-local"


# ---- happy path: standard task, receipt carries the ceiling ----


def test_happy_path_standard_task_records_standard_ceiling():
    s = sub.SharedSubstrate()
    out = nx.route_guarded(s, {"kinds": {"chat"}}, _providers())
    assert out["ok"] is True
    assert out["ceiling"] == "standard"
    assert out["provider"] == "levi-local"  # cheapest covering local wins balanced
    assert 0.0 <= out["confidence"] <= 1.0
    assert out["reasons"]
    r = _route_receipt(s, out["receipt_id"])
    assert r.risk == "standard"
    assert r.approved_by is None  # standard needs no approval
    assert r.payload["mode"] == "balanced"
    assert r.payload["provider"] == "levi-local"
    assert r.payload["confidence"] == out["confidence"]


def test_task_kinds_must_be_covered_by_provider():
    s = sub.SharedSubstrate()
    providers = [
        nx.Provider(name="levi-local", source=nx.SOURCE_LOCAL,
                    kinds=frozenset({"chat"})),
    ]
    out = nx.route_guarded(s, {"kinds": {"chat", "vision"}}, providers)
    assert out["ok"] is False
    assert out["refusal"] == "no eligible provider"
    r = _route_receipt(s, out["receipt_id"], kind="route_refusal")
    assert any("missing kinds" in x for x in r.payload["exclusions"])


# ---- loud failures, unchanged legacy surface ----


def test_unknown_mode_raises_before_any_receipt():
    s = sub.SharedSubstrate()
    with pytest.raises(ValueError, match="unknown mode"):
        nx.route_guarded(s, {"kinds": {"chat"}}, _providers(), mode="warp")
    assert s.receipts() == []


def test_non_dict_task_raises_loudly():
    s = sub.SharedSubstrate()
    with pytest.raises(ValueError, match="task must be a dict"):
        nx.route_guarded(s, "chat", _providers())


def test_legacy_route_signature_still_works():
    # the original policy brain is untouched: route() keeps its shape.
    task = nx.Task(kinds=frozenset({"chat"}))
    routes = nx.route(task, _providers())
    assert routes[0].eligible
    assert routes[0].provider in {"levi-local", "levi-si-cloud"}
