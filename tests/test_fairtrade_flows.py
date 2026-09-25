"""Tests for the flow declaration ledger (core/levi/fairtrade/flows.py).

The symmetry rule under test: the declarant's OWN collection must be
declared too. A declaration that exempts the rule-maker fails loudly.
"""

import pytest

from levi.fairtrade import (
    FlowError,
    audit_flows,
    declare_flows,
    levi_declaration,
)


def _flow(collector="us", **kw):
    base = {
        "collector": collector,
        "data": "usage analytics",
        "purpose": "improve the product",
        "retention": "90 days, then deleted",
        "user_control": "opt-out in settings",
    }
    base.update(kw)
    return base


# -- deny-closed declaration -------------------------------------------------


def test_declare_flows_rejects_empty_service():
    with pytest.raises(FlowError):
        declare_flows("", [_flow()])
    with pytest.raises(FlowError):
        declare_flows("   ", [_flow()])


def test_declare_flows_rejects_non_list_flows():
    with pytest.raises(FlowError):
        declare_flows("Acme", {"collector": "us"})


def test_declare_flows_rejects_missing_key():
    bad = _flow()
    del bad["purpose"]
    with pytest.raises(FlowError):
        declare_flows("Acme", [bad])


def test_declare_flows_rejects_non_string_value():
    bad = _flow(purpose=42)
    with pytest.raises(FlowError):
        declare_flows("Acme", [bad])


def test_declare_flows_rejects_blank_collector_or_data():
    with pytest.raises(FlowError):
        declare_flows("Acme", [_flow(collector="  ")])
    with pytest.raises(FlowError):
        declare_flows("Acme", [_flow(data="")])


def test_declare_flows_accepts_valid():
    d = declare_flows("Acme", [_flow(), _flow(collector="third-party: ads")])
    assert d["levi_flow_declaration"] == 1
    assert d["service"] == "Acme"
    assert len(d["flows"]) == 2


# -- the symmetry rule --------------------------------------------------------


def test_audit_punishes_missing_self_declaration():
    d = declare_flows(
        "SneakyCo",
        [_flow(collector="third-party: ads", data="ad clicks")],
    )
    rep = audit_flows(d)
    assert rep["score"] == 60  # 100 - 40 asymmetry penalty
    assert rep["verdict"] == "murky"
    sym = [f for f in rep["findings"] if f["check"] == "symmetry"][0]
    assert sym["passed"] is False


def test_audit_accepts_first_party_self_declaration():
    d = declare_flows("HonestCo", [_flow(collector="first-party")])
    rep = audit_flows(d)
    assert rep["self_flows"] == 1
    assert rep["score"] == 100
    assert rep["verdict"] == "transparent"


def test_audit_accepts_service_name_as_self():
    d = declare_flows("HonestCo", [_flow(collector="HonestCo")])
    assert audit_flows(d)["verdict"] == "transparent"


# -- per-flow completeness ----------------------------------------------------


def test_audit_deducts_for_missing_purpose():
    d = declare_flows("Acme", [_flow(purpose="")])
    rep = audit_flows(d)
    assert rep["score"] == 90
    assert any("purpose" in x["reason"] for x in rep["deductions"])


def test_audit_deducts_for_no_user_control():
    d = declare_flows("Acme", [_flow(user_control="none")])
    rep = audit_flows(d)
    assert rep["score"] == 90
    assert rep["verdict"] == "transparent"  # 90 still clears the bar


def test_audit_deducts_for_unstated_retention():
    d = declare_flows("Acme", [_flow(retention="")])
    rep = audit_flows(d)
    assert rep["score"] == 95


def test_audit_deducts_for_unnamed_third_party():
    d = declare_flows("Acme", [_flow(), _flow(collector="third-party")])
    rep = audit_flows(d)
    assert rep["score"] == 95
    assert any("unnamed third-party" in x["reason"] for x in rep["deductions"])


def test_opaque_verdict_for_fully_evasive_declaration():
    d = declare_flows(
        "BlackBox",
        [
            _flow(
                collector="third-party", purpose="", user_control="none", retention=""
            ),
        ],
    )
    rep = audit_flows(d)
    # 40 (asymmetry) + 10 (purpose) + 10 (control) + 5 (retention) + 5 (unnamed) = 70
    assert rep["score"] == 30
    assert rep["verdict"] == "opaque"


def test_audit_rejects_malformed_declaration():
    with pytest.raises(FlowError):
        audit_flows({"nope": True})
    with pytest.raises(FlowError):
        audit_flows({"service": "Acme", "flows": "not-a-list"})
    with pytest.raises(FlowError):
        audit_flows("not-a-dict")


# -- LEVI obeys its own rule ---------------------------------------------------


def test_levi_declaration_is_transparent():
    rep = audit_flows(levi_declaration())
    assert rep["verdict"] == "transparent", rep
    assert rep["score"] == 100
    assert rep["self_flows"] >= 1
