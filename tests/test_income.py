"""Hermetic tests for the income factory (ServicePlan validation, persistence).

No HOME writes (IncomeFactory is constructed with a tmp_path), no network.
"""

import json

import pytest

from levi.income.factory import IncomeFactory, ServicePlan


def test_service_plan_rejects_blank_ids(tmp_path):
    with pytest.raises(ValueError, match="plan id"):
        ServicePlan(id=" ", opportunity_title="t", service="s")
    with pytest.raises(ValueError, match="opportunity_title"):
        ServicePlan(id="p1", opportunity_title="", service="s")
    with pytest.raises(ValueError, match="plan service"):
        ServicePlan(id="p1", opportunity_title="t", service=None)


def test_service_plan_rejects_bad_status_and_steps():
    with pytest.raises(ValueError, match="plan status"):
        ServicePlan(id="p1", opportunity_title="t", service="s", status="shipped")
    with pytest.raises(ValueError, match="offer_steps"):
        ServicePlan(id="p1", opportunity_title="t", service="s", offer_steps="do it")


def test_compose_validates_inputs(tmp_path):
    factory = IncomeFactory(path=tmp_path / "income.json")
    with pytest.raises(ValueError, match="opportunity_title"):
        factory.compose("")
    with pytest.raises(ValueError, match="service"):
        factory.compose("title", service="   ")
    with pytest.raises(ValueError, match="demand_signal_id"):
        factory.compose("title", demand_signal_id=123)
    plan = factory.compose("Modernize bakery site", service="web refresh")
    assert plan.opportunity_title == "Modernize bakery site"
    assert plan.status == "draft"


def test_corrupt_file_warns_and_starts_empty(tmp_path):
    path = tmp_path / "income.json"
    path.write_text("{corrupt", encoding="utf-8")
    with pytest.warns(UserWarning, match="unreadable"):
        factory = IncomeFactory(path=path)
    assert factory.plans == []


def test_corrupt_plan_skipped_not_fatal(tmp_path):
    path = tmp_path / "income.json"
    good = {"id": "p1", "opportunity_title": "t", "service": "s"}
    bad = {"id": "", "opportunity_title": "", "service": ""}
    path.write_text(json.dumps({"plans": [good, bad, 42]}))
    factory = IncomeFactory(path=path)
    assert [p.id for p in factory.plans] == ["p1"]


def test_round_trip_persists_plans(tmp_path):
    path = tmp_path / "income.json"
    factory = IncomeFactory(path=path)
    factory.compose("Bakery site refresh")
    reloaded = IncomeFactory(path=path)
    assert len(reloaded.plans) == 1
    assert reloaded.plans[0].opportunity_title == "Bakery site refresh"
