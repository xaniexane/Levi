"""Tests for levi.demand.processing — Layer 2 clustering, Layer 3 heuristic
scoring, and the industry heatmap (original design port)."""

from levi.demand import processing
from levi.demand.scoring import DEFAULT_THRESHOLD, DEFAULT_WEIGHTS


def _sig(
    source,
    industry="Technology / SaaS",
    stype="pain_point",
    kw="dispatch",
    summary="i wish dispatch was simpler",
):
    return {
        "id": f"{source}-1",
        "timestamp": "2026-09-21T00:00:00+00:00",
        "source": source,
        "source_name": source,
        "signal_type": stype,
        "industry": industry,
        "confidence": "high",
        "label": "OBSERVED",
        "summary": summary,
        "keywords": [kw],
        "url": "",
        "metadata": {},
    }


# ---- process_signals ----------------------------------------------------------


def test_process_signals_clusters_on_industry_type_keyword():
    a = _sig("social")
    b = _sig("reddit")  # same industry/type/keyword, other source
    clusters = processing.process_signals([a, b])
    assert len(clusters) == 1
    cl = clusters[0]
    assert cl["signal_count"] == 2
    assert cl["multi_source_validated"] is True
    assert cl["confidence"] == "high"  # multi-source boost
    assert cl["label"] == "INFERENCE"


def test_process_signals_splits_on_keyword():
    clusters = processing.process_signals(
        [_sig("social", kw="dispatch"), _sig("social", kw="invoicing")]
    )
    assert len(clusters) == 2


def test_process_signals_single_source_no_boost():
    clusters = processing.process_signals([_sig("social")])
    assert len(clusters) == 1
    assert clusters[0]["multi_source_validated"] is False
    assert clusters[0]["confidence"] == "high"  # source's own confidence kept


def test_process_signals_empty():
    assert processing.process_signals([]) == []


def test_process_signals_missing_keywords():
    sig = _sig("social")
    del sig["keywords"]
    clusters = processing.process_signals([sig])
    assert len(clusters) == 1  # falls back to "general"


# ---- score_cluster (original heuristic formulas) ------------------------------


def _rich_cluster():
    return {
        "cluster_id": "c1",
        "theme": "dispatch pain",
        "industry": "Technology / SaaS",
        "signal_type": "pain_point",
        "signal_count": 5,
        "multi_source_validated": True,
        "confidence": "high",
        "signals": [_sig(f"s{i}") for i in range(5)],
    }


def test_score_cluster_original_formulas():
    opp = processing.score_cluster(_rich_cluster())
    # demand = 40 + 5*8 + 15 = 95; market = 35 + 5*6 = 65;
    # competition = 55 + 10 (pain_point) = 65; velocity = 30 + 50 = 80;
    # feasibility = 70 (Tech/SaaS)
    assert opp["factors"] == {
        "demand": 95.0,
        "market_size": 65.0,
        "competition_gap": 65.0,
        "trend_velocity": 80.0,
        "entry_feasibility": 70.0,
    }
    expected = round(95 * 0.30 + 65 * 0.25 + 65 * 0.20 + 80 * 0.15 + 70 * 0.10, 1)
    assert opp["composite_score"] == expected == 76.8
    assert opp["priority"] == "high"
    assert opp["above_threshold"] is True
    assert opp["threshold"] == DEFAULT_THRESHOLD == 75.0


def test_score_cluster_uses_canonical_weights():
    opp = processing.score_cluster(_rich_cluster())
    assert opp["weights"] == DEFAULT_WEIGHTS
    assert abs(sum(opp["weights"].values()) - 1.0) < 1e-9


def test_score_cluster_priority_bands():
    def opp_with(n, multi=False):
        cl = _rich_cluster()
        cl["signal_count"] = n
        cl["multi_source_validated"] = multi
        cl["signals"] = [_sig(f"s{i}") for i in range(n)]
        return processing.score_cluster(cl)

    assert opp_with(5, True)["priority"] == "high"
    assert opp_with(2)["priority"] == "medium"
    low = processing.score_cluster(
        {**_rich_cluster(), "signal_count": 0, "signal_type": "trend", "signals": []}
    )
    assert low["priority"] == "low"
    assert low["above_threshold"] is False


def test_score_cluster_labeled_hypothesis_with_basis():
    opp = processing.score_cluster(_rich_cluster())
    assert opp["label"] == "HYPOTHESIS"
    assert "heuristic" in opp["basis"]
    assert opp["status"] == "new"


def test_score_all_sorted_desc():
    rich = _rich_cluster()
    weak = {**_rich_cluster(), "signal_count": 0, "signal_type": "trend", "signals": []}
    a = processing.score_cluster(rich)
    b = processing.score_cluster(weak)
    ranked = processing.score_all([weak, rich])
    assert ranked[0]["composite_score"] >= ranked[1]["composite_score"]
    assert ranked[0]["composite_score"] == a["composite_score"]
    assert ranked[1]["composite_score"] == b["composite_score"]


# ---- industry_heatmap ----------------------------------------------------------


def _opp(industry, score, name):
    return {"industry": industry, "composite_score": score, "name": name}


def test_heatmap_bands():
    heat = processing.industry_heatmap(
        [
            _opp("Technology / SaaS", 70, "A"),
            _opp("Technology / SaaS", 70, "B"),
            _opp("Finance / FinTech", 50, "C"),
            _opp("Health / Wellness", 30, "D"),
        ]
    )
    assert heat["Technology / SaaS"]["heat"] == "green"
    assert heat["Technology / SaaS"]["score"] == 70.0
    assert heat["Technology / SaaS"]["count"] == 2
    assert heat["Technology / SaaS"]["top"] == "A"
    assert heat["Finance / FinTech"]["heat"] == "yellow"
    assert heat["Health / Wellness"]["heat"] == "gray"
    # sectors with no opportunities are gray with count 0
    assert heat["Legal / RegTech"] == {
        "score": 0,
        "count": 0,
        "heat": "gray",
        "top": None,
    }


def test_heatmap_covers_all_twelve_industries():
    heat = processing.industry_heatmap([])
    assert len(heat) == 12
    assert all(v["heat"] == "gray" for v in heat.values())


def test_heatmap_band_edges():
    heat = processing.industry_heatmap([_opp("Technology / SaaS", 65, "A")])
    assert heat["Technology / SaaS"]["heat"] == "green"
    heat = processing.industry_heatmap([_opp("Technology / SaaS", 64.9, "A")])
    assert heat["Technology / SaaS"]["heat"] == "yellow"
    heat = processing.industry_heatmap([_opp("Technology / SaaS", 45, "A")])
    assert heat["Technology / SaaS"]["heat"] == "yellow"
    heat = processing.industry_heatmap([_opp("Technology / SaaS", 44.9, "A")])
    assert heat["Technology / SaaS"]["heat"] == "gray"


# ---- run_scan / load_last_scan --------------------------------------------------


def _canned_ingest(query, focus_industries=None):
    return [_sig("social"), _sig("reddit")]


def test_run_scan_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(processing, "ingest_signals", _canned_ingest)
    monkeypatch.setattr(processing, "DEFAULT_SCAN_PATH", tmp_path / "scan.json")
    result = processing.run_scan("dispatch")
    assert result["query"] == "dispatch"
    assert result["layers"]["ingestion"]["signals_raw"] == 2
    assert result["layers"]["processing"]["clusters"] == 1
    assert result["layers"]["scoring"]["opportunities"] == 1
    assert result["layers"]["command_center"]["ready"] is True
    assert result["sources_live"] == {"social": 1, "reddit": 1}
    assert result["top_opportunity"] is not None
    # persisted for workflow 8
    loaded = processing.load_last_scan(tmp_path / "scan.json")
    assert loaded["query"] == "dispatch"


def test_run_scan_persist_failure_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(processing, "ingest_signals", _canned_ingest)
    monkeypatch.setattr(
        processing, "DEFAULT_SCAN_PATH", tmp_path / "no-such-dir" / "scan.json"
    )
    # parent mkdir should succeed actually; force a real failure instead:
    (tmp_path / "no-such-dir").mkdir()
    import os

    os.chmod(tmp_path / "no-such-dir", 0o400)
    try:
        result = processing.run_scan("dispatch")  # must not raise
        assert result["layers"]["processing"]["clusters"] == 1
    finally:
        os.chmod(tmp_path / "no-such-dir", 0o700)


def test_load_last_scan_missing_or_corrupt(tmp_path):
    assert processing.load_last_scan(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert processing.load_last_scan(bad) is None
