"""Law/guard/proof tests for the DemandPulse outcome ledger (greatness build).

Laws under test:
  O1 append-only JSONL record — corrupt lines skipped, never fatal
  O2 verdicts are Chauncey's — explicit calls only; machine never infers
  O3 calibration is advisory — suggest/effective_markers mutate nothing
  O4 excel is a one-way view — xlsx reflects JSONL; xlsx never read back
  O5 minimal data — rows carry no bodies, no PII

Hermetic: LEVI_OUTCOMES_PATH redirected to tmp — no real ledger touched.
"""

import json

import pytest

from levi.demand import outcomes as omod


@pytest.fixture
def led(monkeypatch, tmp_path):
    p = tmp_path / "outcomes.jsonl"
    monkeypatch.setenv("LEVI_OUTCOMES_PATH", str(p))
    return p


def _card(cid="c1", composite=80.0, tier="high"):
    class C:
        pass
    c = C()
    c.opportunity_id = cid
    c.title = "Test card"
    c.composite = composite
    c.tier = tier
    c.segment = "general"
    c.scored_at = "2026-01-01T00:00:00+00:00"
    return c


# ------------------------------------------------------------- O1: record


def test_record_event_appends_jsonl(led):
    omod.record_event("c1", "sighting", title="T", composite=80.0, tier="high")
    lines = led.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["card_id"] == "c1" and row["event"] == "sighting"
    assert row["composite"] == 80.0


def test_corrupt_line_never_kills_read(led):
    led.write_text(
        '{"card_id": "c1", "event": "sighting"}\nNOT JSON{{{\n'
        '{"card_id": "c2", "event": "bogus"}\n',
        encoding="utf-8",
    )
    rows = omod.read_rows()
    assert [r["card_id"] for r in rows] == ["c1"]  # corrupt + bad-event skipped


def test_record_event_rejects_bad_event(led):
    with pytest.raises(ValueError):
        omod.record_event("c1", "maybe")


def test_record_event_rejects_empty_card_id(led):
    with pytest.raises(ValueError):
        omod.record_event("  ", "sighting")


def test_record_conversion_rejects_non_verdict(led):
    with pytest.raises(ValueError):
        omod.record_conversion("c1", "sighting")
    with pytest.raises(ValueError):
        omod.record_conversion("c1", "stale")


def test_sighting_hook_shape(led):
    omod.record_sighting(_card(), markers=["i need"])
    rows = omod.read_rows()
    assert rows[0]["markers"] == ["i need"]
    assert rows[0]["note"] == "auto: card scored"


# ------------------------------------------------------------- O2: verdicts


def test_no_verdict_without_explicit_call(led):
    omod.record_sighting(_card("c9"))
    assert omod.resolved_pairs() == []  # machine infers nothing
    assert omod.suggest_thresholds(min_resolved=1)["resolved"] == 0


def test_sweep_stale_marks_old_cards(led):
    omod.record_sighting(_card("cold"))
    rep = omod.sweep_stale([_card("cold")], stale_days=30)
    assert rep["staled"] == 1
    terms = {r["card_id"]: r["event"] for r in omod.read_rows()
             if r["event"] in omod.TERMINAL_EVENTS}
    assert terms["cold"] == "stale"


def test_sweep_stale_skips_verdict_cards(led):
    omod.record_sighting(_card("hot"))
    omod.record_conversion("hot", "converted", note="his word")
    rep = omod.sweep_stale([_card("hot")], stale_days=1)
    assert rep["staled"] == 0  # verdict stands; sweep never overwrites


# ------------------------------------------------- O3: advisory only


def test_module_never_imports_scoring_or_pulse():
    src = open(omod.__file__, encoding="utf-8").read()
    assert "levi.demand.scoring" not in src
    assert "levi.demand.pulse" not in src
    assert "from levi.demand import" not in src


def test_suggest_thresholds_thin_ledger_silent(led):
    rep = omod.suggest_thresholds(min_resolved=10)
    assert rep["suggestion"] is None
    assert "thin ledger" in rep["reason"]


def test_suggest_thresholds_advisory_shape(led):
    for i in range(12):
        cid = f"hx{i}"
        comp = 82.0 if i < 6 else 30.0
        omod.record_sighting(_card(cid, composite=comp))
        omod.record_conversion(cid, "converted" if i < 6 else "missed")
    before = led.read_bytes()
    rep = omod.suggest_thresholds(min_resolved=10)
    assert rep["suggestion"] is not None
    assert rep["suggestion"]["threshold"] == 80
    assert led.read_bytes() == before  # suggestion mutated nothing


def test_effective_markers_needs_volume_and_lift(led):
    # 20 resolved on the marker, all converted; 20 resolved elsewhere, all missed
    for i in range(20):
        omod.record_sighting(_card(f"m{i}"), markers=["i need"])
        omod.record_conversion(f"m{i}", "converted")
    for i in range(20):
        omod.record_sighting(_card(f"z{i}"), markers=["other"])
        omod.record_conversion(f"z{i}", "missed")
    eff = omod.effective_markers(min_sightings=20)
    assert [e["marker"] for e in eff] == ["i need"]
    assert eff[0]["lift"] >= 2.0


def test_effective_markers_silent_when_thin(led):
    omod.record_sighting(_card("t1"), markers=["i need"])
    omod.record_conversion("t1", "converted")
    assert omod.effective_markers(min_sightings=20) == []


# ------------------------------------------------- O4: excel is a view


def test_export_xlsx_roundtrip_view(led, tmp_path):
    pytest.importorskip("openpyxl")
    omod.record_sighting(_card("x1", composite=77.0))
    omod.record_conversion("x1", "converted", note="yes")
    out = tmp_path / "view.xlsx"
    got = omod.export_xlsx(out=out)
    assert got == out and out.exists()
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert "outcomes" in wb.sheetnames and "calibration" in wb.sheetnames
    ws = wb["outcomes"]
    assert ws["B2"].value == "x1" and ws["G2"].value == "sighting"


def test_export_csv_fallback(led, tmp_path):
    out = tmp_path / "view.csv"
    got = omod.export_csv(out=out)
    assert got.exists()
    text = out.read_text(encoding="utf-8")
    assert "card_id" in text.splitlines()[0]


# ------------------------------------------------- O5: minimal data


def test_rows_carry_no_bodies(led):
    omod.record_event("c1", "sighting", title="T", note="n" * 9000)
    row = omod.read_rows()[0]
    assert len(row["note"]) <= 500
    assert set(row) <= {
        "card_id", "event", "title", "composite", "tier", "segment",
        "markers", "note", "ts",
    }


def test_render_report_runs(led):
    omod.record_sighting(_card())
    text = omod.render_report()
    assert "outcome ledger" in text and "advisory" in text.lower()
