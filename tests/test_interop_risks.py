"""Hermetic tests for the strictest-risk-ceiling (levi.interop.risks)."""

import pytest

from levi.interop import risks
from levi.policy.gates import RiskLevel


def test_ceiling_max_wins():
    assert (
        risks.ceiling([RiskLevel.INFO, RiskLevel.CRITICAL, RiskLevel.LOW])
        is RiskLevel.CRITICAL
    )


def test_ceiling_ordering():
    levels = [
        RiskLevel.INFO,
        RiskLevel.LOW,
        RiskLevel.MODERATE,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]
    for i in range(len(levels) - 1):
        assert risks.ceiling([levels[i], levels[i + 1]]) is levels[i + 1]
        assert risks.ceiling([levels[i + 1], levels[i]]) is levels[i + 1]


def test_ceiling_accepts_ints():
    assert risks.ceiling([0, 2, 1]) is RiskLevel.MODERATE


def test_ceiling_accepts_names_case_insensitive():
    assert risks.ceiling(["info", "HIGH"]) is RiskLevel.HIGH
    assert risks.ceiling(["Critical"]) is RiskLevel.CRITICAL


def test_ceiling_single():
    assert risks.ceiling([RiskLevel.LOW]) is RiskLevel.LOW


def test_ceiling_empty_denied():
    with pytest.raises(ValueError):
        risks.ceiling([])


def test_ceiling_unknown_int_denied():
    with pytest.raises(ValueError):
        risks.ceiling([RiskLevel.LOW, 99])


def test_ceiling_unknown_name_denied():
    with pytest.raises(ValueError):
        risks.ceiling(["extreme"])


def test_ceiling_unparseable_type_denied():
    with pytest.raises(ValueError):
        risks.ceiling([None])
    with pytest.raises(ValueError):
        risks.ceiling([True])  # bools are not risk levels


def test_compose_risk_returns_ceiling_and_contributions():
    out = risks.compose_risk(
        {"name": "memory-store", "risk": RiskLevel.LOW},
        {"name": "rag", "risk": "MODERATE"},
        RiskLevel.HIGH,  # bare level, anonymous
    )
    assert out["ceiling"] is RiskLevel.HIGH
    assert out["contributions"]["memory-store"] is RiskLevel.LOW
    assert out["contributions"]["rag"] is RiskLevel.MODERATE
    assert list(out["contributions"].values())[-1] is RiskLevel.HIGH


def test_compose_risk_no_participants_denied():
    with pytest.raises(ValueError):
        risks.compose_risk()


def test_compose_risk_bad_participant_denied():
    with pytest.raises(ValueError):
        risks.compose_risk({"name": "x"})  # no 'risk' key
    with pytest.raises(ValueError):
        risks.compose_risk({"name": "x", "risk": "bogus"})


def test_compose_risk_module_key_alias():
    out = risks.compose_risk({"module": "growth", "risk": 1})
    assert out["ceiling"] is RiskLevel.LOW
    assert out["contributions"]["growth"] is RiskLevel.LOW


def test_lazy_import_does_not_require_gates_at_package_import():
    # risks.py must import cleanly and only touch levi.policy.gates lazily.
    import importlib

    mod = importlib.import_module("levi.interop.risks")
    assert callable(mod.ceiling)
    # the canonical enum is genuinely reused, not redefined
    assert mod._risk_level() is RiskLevel
