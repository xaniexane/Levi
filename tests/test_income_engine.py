"""Engine tests: registry, 70/30 split, pool, honesty rule, runner."""

from __future__ import annotations

import pytest

from levi.income import engine
from levi.income.engine import (
    Generator,
    Registry,
    WorkReport,
    approve_pool_spend,
    pool_balance,
    record_income,
    register,
    run_generator,
    split_income,
)


def _gen(gid="test-gen", kind="micro-tool"):
    def _run(ctx):
        assert "dry_run" in ctx and "levi_home" in ctx
        return WorkReport(
            generator_id=gid,
            produced=["artifact.txt"],
            quoted_amount_usd=3.0,
            notes="ok",
        )

    return Generator(
        id=gid,
        name="Test Generator",
        kind=kind,
        description="engine test fixture",
        run=_run,
        entry_price_usd=3.0,
    )


def test_split_is_70_30():
    s = split_income(100.0)
    assert s == {"keeper": 70.0, "pool": 30.0}


def test_split_rejects_non_positive():
    with pytest.raises(ValueError):
        split_income(0)


def test_register_slot_bounds():
    r = Registry()
    with pytest.raises(ValueError):
        r.register(_gen("a"), 0)
    with pytest.raises(ValueError):
        r.register(_gen("a"), 101)


def test_register_collision_and_dup_id():
    r = Registry()
    r.register(_gen("a"), 5)
    with pytest.raises(ValueError):
        r.register(_gen("b"), 5)
    with pytest.raises(ValueError):
        r.register(_gen("a"), 6)


def test_generator_validates_kind():
    with pytest.raises(ValueError):
        _gen("x", kind="not-a-kind")


def test_record_income_requires_confirmed_basis(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "REGISTRY", Registry())
    register(_gen("g1"), 1)
    with pytest.raises(ValueError):
        record_income("g1", 10.0, "sale", basis="projected")
    with pytest.raises(ValueError):
        record_income("g1", 10.0, "sale", basis="estimated")


def test_record_income_splits_and_pools(monkeypatch, tmp_path):
    import levi.income.engine as eng

    monkeypatch.setattr(eng, "REGISTRY", Registry())
    monkeypatch.setattr(eng, "_home_dir", lambda: tmp_path)
    register(_gen("g2"), 2)
    ev = record_income("g2", 100.0, "sale", basis="confirmed",
                       counterparty="client", note="t")
    assert ev["keeper"] == 70.0 and ev["pool"] == 30.0
    bal = pool_balance()
    assert bal["allocated"] == 30.0 and bal["available"] == 30.0


def test_pool_spend_needs_chauncey(monkeypatch, tmp_path):
    import levi.income.engine as eng

    monkeypatch.setattr(eng, "REGISTRY", Registry())
    monkeypatch.setattr(eng, "_home_dir", lambda: tmp_path)
    register(_gen("g3"), 3)
    record_income("g3", 100.0, "sale", basis="confirmed")
    with pytest.raises(ValueError):
        approve_pool_spend(10.0, "domain", by="levi")
    with pytest.raises(ValueError):
        approve_pool_spend(999.0, "domain", by="chauncey")
    rec = approve_pool_spend(10.0, "domain renewal", by="chauncey")
    assert "MoneyGateway" in rec["movement"]
    assert pool_balance()["available"] == 20.0


def test_run_generator_records_report(monkeypatch, tmp_path):
    import levi.income.engine as eng

    monkeypatch.setattr(eng, "REGISTRY", Registry())
    monkeypatch.setattr(eng, "_home_dir", lambda: tmp_path)
    register(_gen("g4"), 4)
    rec = run_generator("g4", dry_run=True)
    assert rec["produced"] == ["artifact.txt"]
    assert rec["dry_run"] is True


def test_run_generator_rejects_bad_report(monkeypatch):
    def _bad(ctx):
        return {"not": "a WorkReport"}

    g = Generator(id="g5", name="bad", kind="micro-tool",
                  description="bad", run=_bad)
    monkeypatch.setattr(engine, "REGISTRY", Registry())
    register(g, 5)
    with pytest.raises(ValueError):
        run_generator("g5")


def test_advise_entry_price_doctrine():
    p = engine.advise_entry_price(giant_price=200.0)
    assert 1.0 <= p["recommended"] <= 5.0
    assert p["recommended"] < 200.0  # never at/above the giant
