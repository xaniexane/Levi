"""Batch D (data-products, slots 61-72) tests.

Registry presence, per-generator run() smoke (dry-run + real), dry-run
safety (no deliverable files), entry-price bounds (doctrine: $1-5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.income.engine import REGISTRY, run_generator

import levi.income.gen_data  # noqa: F401  (self-registers on import)

BATCH_D = [
    ("habit-tracker-kit", 61, 3.0),
    ("budget-ledger-builder", 62, 2.0),
    ("price-watchlist", 63, 3.0),
    ("reading-log-atlas", 64, 2.0),
    ("workout-planner-pack", 65, 4.0),
    ("meal-prep-planner", 66, 4.0),
    ("invoice-aging-tracker", 67, 5.0),
    ("content-calendar-forge", 68, 3.0),
    ("kpi-dashboard-text", 69, 4.0),
    ("survey-tally-engine", 70, 2.0),
    ("inventory-ledger-kit", 71, 5.0),
    ("subscription-auditor", 72, 3.0),
]


@pytest.fixture(autouse=True)
def _levi_home(monkeypatch, tmp_path):
    """Keep every run log and artifact inside a temp LEVI_HOME."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _work(gid: str, home: Path) -> Path:
    return home / ".levi" / "income" / "work" / gid


def test_batch_d_registered_all_slots():
    assert len({slot for _, slot, _ in BATCH_D}) == 12
    ids = [gid for gid, _, _ in BATCH_D]
    assert len(set(ids)) == 12, "generator ids must be globally unique"
    for gid, slot, price in BATCH_D:
        gen = REGISTRY.get(gid)
        assert gen.kind == "data-product", gid
        assert REGISTRY.slot_of(gid) == slot, gid
        assert gen.entry_price_usd == price, gid
        assert gen.version == "1.0.0", gid


def test_entry_prices_within_doctrine():
    for gid, _, price in BATCH_D:
        assert price is not None, gid
        assert 1.0 <= price <= 5.0, f"{gid}: {price} outside $1-5 doctrine"


@pytest.mark.parametrize("gid,slot,price", BATCH_D)
def test_run_smoke_dry_and_real(gid, slot, price, tmp_path):
    dry = run_generator(gid, dry_run=True, params={})
    assert dry["generator_id"] == gid
    assert dry["dry_run"] is True
    assert dry["quoted_amount_usd"] == price
    assert 1.0 <= dry["quoted_amount_usd"] <= 5.0
    assert dry["produced"], "dry run must report what it WOULD produce"

    real = run_generator(gid, dry_run=False, params={})
    assert real["generator_id"] == gid
    assert real["dry_run"] is False
    assert real["quoted_amount_usd"] == price
    assert real["produced"]
    work = _work(gid, tmp_path)
    assert work.is_dir(), f"{gid}: work dir missing"
    for p in real["produced"]:
        assert Path(p).is_file(), f"{gid}: missing artifact {p}"
    assert any(Path(p).suffix == ".csv" for p in real["produced"]), \
        f"{gid}: data-product must produce at least one CSV"


@pytest.mark.parametrize("gid,slot,price", BATCH_D)
def test_dry_run_writes_no_deliverables(gid, slot, price, tmp_path):
    run_generator(gid, dry_run=True, params={})
    work = _work(gid, tmp_path)
    assert not work.exists() or not any(work.iterdir()), \
        f"{gid}: dry run leaked deliverable files"


def test_budget_ledger_honors_user_params(tmp_path):
    rec = run_generator(
        "budget-ledger-builder",
        dry_run=False,
        params={
            "month": "2026-09",
            "income": [{"source": "job", "amount": 1000.0}],
            "expenses": [{"name": "rent", "amount": 700.0, "category": "housing"}],
        },
    )
    work = _work("budget-ledger-builder", tmp_path)
    ledger = (work / "ledger.csv").read_text()
    assert "job" in ledger and "rent" in ledger
    assert "savings (auto-assigned)" in ledger  # zero-based remainder
    summary = (work / "budget_summary.txt").read_text()
    assert "PASS" in summary
    assert rec["quoted_amount_usd"] == 2.0


def test_invoice_aging_flags_overdue(tmp_path):
    run_generator(
        "invoice-aging-tracker",
        dry_run=False,
        params={
            "as_of": "2026-09-17",
            "invoices": [
                {"id": "A1", "client": "X", "issued": "2026-01-01",
                 "due": "2026-02-01", "amount": 500.0, "paid": 0.0},
                {"id": "A2", "client": "Y", "issued": "2026-09-01",
                 "due": "2026-10-01", "amount": 100.0, "paid": 100.0},
            ],
        },
    )
    aging = (_work("invoice-aging-tracker", tmp_path) / "aging.csv").read_text()
    assert "A1" in aging and "90+" in aging
    assert "A2" not in aging  # paid in full -> excluded


def test_subscription_auditor_detects_recurring(tmp_path):
    run_generator("subscription-auditor", dry_run=False, params={})
    work = _work("subscription-auditor", tmp_path)
    subs = (work / "subscriptions.csv").read_text()
    assert "streamflix" in subs and "monthly" in subs
    assert "domainreg" in subs and "yearly" in subs
    report = (work / "audit_report.txt").read_text()
    assert "monthly burn" in report


def test_survey_tally_numeric_path(tmp_path):
    run_generator(
        "survey-tally-engine",
        dry_run=False,
        params={"question": "Rate us 1-5", "responses": ["5", "4", "5", "3", "5"]},
    )
    report = (_work("survey-tally-engine", tmp_path) / "survey_report.txt").read_text()
    assert "mean" in report and "median" in report


def test_kpi_dashboard_has_sparklines(tmp_path):
    run_generator("kpi-dashboard-text", dry_run=False, params={})
    dash = (_work("kpi-dashboard-text", tmp_path) / "kpi_dashboard.txt").read_text()
    assert any(ch in dash for ch in "▁▂▃▄▅▆▇█")
    assert "7d:" in dash
