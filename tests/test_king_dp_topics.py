"""DemandPulse → content pipeline wiring: determinism, dedup, traceability, gate."""

import json

from levi.king import dp_topics as dp


def _fixture(path):
    data = {
        "signals": [
            {
                "id": "sig-1",
                "need": "I need help scheduling shifts for my crew",
                "kind": "OBSERVED",
                "confidence": 0.8,
                "seen_count": 50,
            },
            {
                "id": "sig-2",
                "need": "I need answers now so I can get this thing done",
                "kind": "HYPOTHESIS",
                "confidence": 0.35,
                "seen_count": 1,
            },
        ],
        "opportunities": [
            {"id": "opp-1", "title": "Local tutoring", "worth": 0.64},
        ],
        "score_cards": [
            {"opportunity_id": "card-1", "title": "Shift planner", "composite": 68.5},
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _all_ids(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = {s["id"] for s in data["signals"]}
    ids |= {o["id"] for o in data["opportunities"]}
    ids |= {c["opportunity_id"] for c in data["score_cards"]}
    return ids


def test_construction_gate_holds():
    dp.validate_static()  # raises SystemExit on violation
    assert len(dp.VOICE_WORDS) == len(set(dp.VOICE_WORDS))
    assert len(dp.STOPWORDS) == len(set(dp.STOPWORDS))


def test_ranking_is_deterministic_and_best_first(tmp_path):
    fx = _fixture(tmp_path / "dp.json")
    data = dp.read_demand_pulse(fx)
    first = [c["signal_id"] for c in dp.rank_candidates(data)]
    second = [c["signal_id"] for c in dp.rank_candidates(data)]
    assert first == second
    # OBSERVED 0.8-confidence signal outranks the HYPOTHESIS one
    assert first.index("sig-1") < first.index("sig-2")


def test_every_pack_traces_to_a_real_signal(tmp_path):
    fx = _fixture(tmp_path / "dp.json")
    ids = _all_ids(fx)
    res = dp.generate_dp_packs(
        platforms=("x", "facebook", "tiktok"),
        per_platform=2,
        demand_path=fx,
        round_label="dp-test",
        ts="2026-09-23T00:00:00Z",
    )
    assert res["packs"], "expected packs from the fixture"
    for pack in res["packs"]:
        assert pack["demand_signal_id"] in ids
        assert pack["signal_kind"] in ("signal", "opportunity", "score_card")
        assert pack["round"] == "dp-test"
        assert pack["ts"] == "2026-09-23T00:00:00Z"
        assert pack["score"]["composite"] >= dp.GATE_THRESHOLD


def test_dedup_no_repeated_angles(tmp_path):
    fx = _fixture(tmp_path / "dp.json")
    ledger = dp.DedupLedger()
    kwargs = dict(
        platforms=("x", "facebook"),
        per_platform=10,  # exhaust all candidates in run 1
        demand_path=fx,
        ts="2026-09-23T00:00:00Z",
        ledger=ledger,
    )
    run1 = dp.generate_dp_packs(round_label="dp-a", **kwargs)
    run2 = dp.generate_dp_packs(round_label="dp-b", **kwargs)
    assert run1["packs"], "first run should ship packs"
    assert run2["packs"] == [], "second run must ship nothing new"
    assert run2["dupes_skipped"] > 0
    fps = [dp.pack_fingerprint(p["platform"], p["caption"]) for p in run1["packs"]]
    assert len(fps) == len(set(fps)), "no repeated angles within a run"


def test_gate_rejects_weak_draft(tmp_path):
    fx = tmp_path / "weak.json"
    fx.write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "id": "weak-1",
                        "need": "",
                        "kind": "HYPOTHESIS",
                        "confidence": 0.0,
                        "seen_count": 0,
                    }
                ],
                "opportunities": [],
                "score_cards": [],
            }
        ),
        encoding="utf-8",
    )
    res = dp.generate_dp_packs(
        platforms=("x",), per_platform=1, demand_path=fx, ts="2026-09-23T00:00:00Z"
    )
    assert res["packs"] == []
    assert res["rejected"], "weak draft must be recorded, not silently dropped"
    assert any("weak-1" in r["demand_signal_id"] for r in res["rejected"])


def test_gate_rejects_off_voice_draft():
    gate = dp.passes_gate(
        "Hello friends! Today I will share some generic marketing tips.",
        ["scheduling", "shifts"],
        "x",
    )
    assert not gate["pass"]
    assert gate["score"]["composite"] < dp.GATE_THRESHOLD


def test_determinism_byte_identical(tmp_path):
    fx = _fixture(tmp_path / "dp.json")
    kwargs = dict(
        platforms=("x", "facebook", "tiktok"),
        per_platform=1,
        demand_path=fx,
        round_label="dp-det",
        ts="2026-09-23T00:00:00Z",
    )
    a = dp.generate_dp_packs(**kwargs)
    b = dp.generate_dp_packs(**kwargs)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_missing_demand_file_yields_nothing(tmp_path):
    res = dp.generate_dp_packs(
        platforms=("x",),
        demand_path=tmp_path / "nope.json",
        ts="2026-09-23T00:00:00Z",
    )
    assert res["packs"] == []
    assert res["candidates_considered"] == 0


def test_king_social_dp_wiring(tmp_path):
    """King.social_dp routes the top demand signal into the review queue."""
    from levi.king import King

    fx = _fixture(tmp_path / "dp.json")
    import levi.king.dp_topics as dp_mod

    orig = dp_mod.DEFAULT_DEMAND_PATH
    dp_mod.DEFAULT_DEMAND_PATH = fx
    try:
        king = King(data_dir=tmp_path / "king", story_fabric=None, model_engine=None)
        out = king.social_dp(platform="x", round_label="dp-wire")
    finally:
        dp_mod.DEFAULT_DEMAND_PATH = orig
    assert "queued for review" in out
    assert "demand-pulse:" in out
    pending = king.review.pending
    assert len(pending) == 1
    assert pending[0]["note"].startswith("demand:")
    assert "round:dp-wire" in pending[0]["note"]


def test_king_social_dp_empty_demand(tmp_path):
    from levi.king import King

    import levi.king.dp_topics as dp_mod

    orig = dp_mod.DEFAULT_DEMAND_PATH
    dp_mod.DEFAULT_DEMAND_PATH = tmp_path / "missing.json"
    try:
        king = King(data_dir=tmp_path / "king", story_fabric=None, model_engine=None)
        out = king.social_dp(platform="x")
    finally:
        dp_mod.DEFAULT_DEMAND_PATH = orig
    assert "nothing queued" in out
    assert king.review.pending == []
