"""Tests for levi.demand.competition — competitive edge module.

All network is mocked. Fixture HTML/snapshots are synthetic and clearly
marked as fixtures — nothing here is presented as a real competitor fact.
Hermetic: no real HOME writes (tmp_path store), no network.
"""

import json
import urllib.request

import pytest

from levi.demand import competition as comp


# ---------------------------------------------------------------------------
# Clearly-marked fixtures (synthetic — NOT real competitor data)
# ---------------------------------------------------------------------------

_FIXTURE_HTML_V1 = (
    "<html><head><title>FixtureCo Pricing</title></head>"
    "<body><h1>Plans</h1><p>Starter $10/mo</p>"
    "<script>var x = 1;</script></body></html>"
)
_FIXTURE_HTML_V2 = (
    "<html><head><title>FixtureCo Pricing</title></head>"
    "<body><h1>Plans</h1><p>Starter $12/mo</p><p>Pro $30/mo</p></body></html>"
)


class _FakeResp:
    """Minimal urlopen stand-in (context manager)."""

    def __init__(self, body: str, status: int = 200):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_urlopen_factory(pages, monkeypatch):
    """Map URL -> body (or Exception instance to raise)."""

    def fake_urlopen(req, timeout=15.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url not in pages:
            raise urllib.error.URLError("fixture: unknown url")
        body = pages[url]
        if isinstance(body, Exception):
            raise body
        return _FakeResp(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "competitors"


# ---------------------------------------------------------------------------
# Profile seeding: evidence labels, no deck claims
# ---------------------------------------------------------------------------


def test_seed_profiles_evidence_labeled(store):
    profiles = comp.load_profiles(store)
    assert len(profiles) == 16
    slugs = {p["slug"] for p in profiles}
    assert slugs == {
        "google-trends",
        "exploding-topics",
        "crayon",
        "klue",
        "6sense",
        "cb-insights",
        "trendwatching",
        "trend-hunter",
        "glimpse",
        "answerthepublic",
        "buzzsumo",
        "sparktoro",
        "semrush",
        "similarweb",
        "demandbase",
        "bombora",
    }
    for p in profiles:
        assert p["pages"], f"{p['slug']} has no pages"
        for f in p["facts"]:
            assert f["label"] == "OBSERVED"
            assert f["source"]
            assert f["observed"]
            assert f["confidence"] in ("high", "medium", "low")


def test_deck_market_claims_never_seeded(store):
    comp.load_profiles(store)  # seeds profiles.json
    raw = json.loads((store / "profiles.json").read_text())
    blob = json.dumps(raw)
    for claim in ("4.8B", "33M", "$2.1M ARR", "15-21M", "15–21M"):
        assert claim not in blob


def test_profiles_not_overwritten(store):
    comp.load_profiles(store)
    pfile = store / "profiles.json"
    payload = json.loads(pfile.read_text())
    payload["profiles"] = payload["profiles"][:1]
    pfile.write_text(json.dumps(payload))
    assert len(comp.load_profiles(store)) == 1  # user edits win


# ---------------------------------------------------------------------------
# Fetching: polite, graceful, never raises
# ---------------------------------------------------------------------------


def test_fetch_page_parses_and_hashes(store, monkeypatch):
    _mock_urlopen_factory({"https://fixture.example/p": _FIXTURE_HTML_V1}, monkeypatch)
    rec = comp.fetch_page("https://fixture.example/p")
    assert rec["status"] == 200
    assert "Starter $10/mo" in rec["text"]
    assert "var x = 1" not in rec["text"]  # scripts stripped
    assert rec["sha256"] and rec["chars"] > 0
    assert rec["label"] == "OBSERVED"


def test_fetch_page_failure_is_graceful(store, monkeypatch):
    import urllib.error

    _mock_urlopen_factory(
        {"https://fixture.example/down": urllib.error.URLError("nope")},
        monkeypatch,
    )
    rec = comp.fetch_page("https://fixture.example/down")
    assert rec["status"] is None
    assert rec["text"] == ""
    assert rec["error"]  # failure recorded, not raised


def test_extract_text_strips_markup():
    text = comp._extract_text("<style>.a{}</style><p>Hello&nbsp; <b>World</b></p>")
    assert text == "Hello World"


# ---------------------------------------------------------------------------
# Snapshots + diff (fixture snapshots)
# ---------------------------------------------------------------------------


def _fixture_profile():
    return {
        "slug": "fixtureco",
        "name": "FixtureCo",
        "pages": ["https://fixture.example/pricing"],
    }


def test_track_writes_versioned_snapshots(store, monkeypatch):
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V1}, monkeypatch
    )
    out = comp.snapshot_competitor(_fixture_profile(), store)
    assert out["slug"] == "fixtureco"
    assert out["pages"][0]["status"] == 200
    rows = list((store / "snapshots" / "fixtureco").glob("*.jsonl"))
    assert rows and rows[0].read_text().strip()


def test_diff_detects_change(store, monkeypatch):
    prof = _fixture_profile()
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V1}, monkeypatch
    )
    comp.snapshot_competitor(prof, store)
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V2}, monkeypatch
    )
    comp.snapshot_competitor(prof, store)

    # check_changes needs profiles present; seed then inject fixture profile
    comp.load_profiles(store)
    pfile = store / "profiles.json"
    payload = json.loads(pfile.read_text())
    payload["profiles"].append(prof)
    pfile.write_text(json.dumps(payload))

    changes = comp.check_changes(store)
    assert len(changes) == 1
    ch = changes[0]
    assert ch["slug"] == "fixtureco"
    assert ch["changed"] is True
    assert ch["label"] == "OBSERVED"
    assert ch["added"] >= 1


def test_diff_no_change_when_identical(store, monkeypatch):
    prof = _fixture_profile()
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V1}, monkeypatch
    )
    comp.snapshot_competitor(prof, store)
    comp.snapshot_competitor(prof, store)

    comp.load_profiles(store)
    pfile = store / "profiles.json"
    payload = json.loads(pfile.read_text())
    payload["profiles"].append(prof)
    pfile.write_text(json.dumps(payload))

    assert comp.check_changes(store) == []


def test_diff_pure_function():
    old = {"text": "a b c", "sha256": "x", "fetched_at": "t1"}
    new = {"text": "a b c", "sha256": "x", "fetched_at": "t2"}
    d = comp.diff_snapshots(old, new)
    assert d["changed"] is False
    new2 = dict(new, text="a b d", sha256="y")
    d2 = comp.diff_snapshots(old, new2)
    assert d2["changed"] is True


# ---------------------------------------------------------------------------
# Gap analysis: DemandPulse column is code-derived only
# ---------------------------------------------------------------------------


def test_feature_matrix_dp_column_from_code(store):
    comp.load_profiles(store)
    matrix = comp.feature_matrix(store)
    by_feature = {r["feature"]: r for r in matrix}
    # Every DP "yes" must cite in-code evidence.
    for r in matrix:
        if r["demandpulse"] == "yes":
            assert r["demandpulse_evidence"], r["feature"]
    # Spot-check real capabilities exist; invented ones don't.
    assert by_feature["five_factor_scoring"]["demandpulse"] == "yes"
    assert by_feature["proactive_alerts"]["demandpulse"] == "yes"
    assert "quantum_telepathy" not in by_feature


def test_feature_matrix_unknowns_not_guessed(store):
    comp.load_profiles(store)
    matrix = comp.feature_matrix(store)
    # Rival cells are only yes/no/partial/n/a/unknown — never blank/guessed.
    allowed = {"yes", "no", "partial", "n/a", "unknown"}
    for r in matrix:
        for k, v in r.items():
            if k in ("feature", "label", "demandpulse", "demandpulse_evidence"):
                continue
            assert v in allowed, (r["feature"], k, v)


# ---------------------------------------------------------------------------
# Proposals: HYPOTHESIS, gated, anchored at $6
# ---------------------------------------------------------------------------


def test_proposals_all_hypothesis_and_gated(store):
    comp.load_profiles(store)
    pkg = comp.propose_upgrades(store, heatmap=None)
    assert pkg["price_anchor_monthly"] == 6.0
    assert pkg["proposals"], "expected at least the pricing/remove proposals"
    kinds = {p["kind"] for p in pkg["proposals"]}
    assert kinds <= {"add", "change", "remove", "reprice"}
    # add/remove/reprice fire deterministically; "change" needs observed
    # page changes or heatmap data (covered below).
    assert {"add", "remove", "reprice"} <= kinds
    for p in pkg["proposals"]:
        assert p["label"] == "HYPOTHESIS"
        assert p["advisory_only"] is True
        assert p["self_applies"] is False
        assert p["requires"] == "founder's explicit word"
        assert p["basis"], "proposal without basis"
        assert p["confidence"] in ("high", "medium", "low")


def test_reprice_proposals_reason_from_anchor(store):
    comp.load_profiles(store)
    pkg = comp.propose_upgrades(store, heatmap=None)
    reprice = [p for p in pkg["proposals"] if p["kind"] == "reprice"]
    assert reprice
    for p in reprice:
        assert "$6" in p["price_anchor"]
        assert any("$6" in b for b in p["basis"])


def test_moats_are_inference_labeled(store):
    comp.load_profiles(store)
    pkg = comp.propose_upgrades(store, heatmap=None)
    assert pkg["moats"]
    for m in pkg["moats"]:
        assert m["label"] == "INFERENCE"
        assert m["evidence"]


# ---------------------------------------------------------------------------
# Market side: heatmap -> targets, INFERENCE
# ---------------------------------------------------------------------------


def test_target_industries_from_heatmap():
    heatmap = {
        "Technology / SaaS": {
            "score": 70.0,
            "count": 3,
            "heat": "green",
            "top": "opp-a",
        },
        "Health / Wellness": {
            "score": 50.0,
            "count": 1,
            "heat": "yellow",
            "top": "opp-b",
        },
        "Finance / FinTech": {
            "score": 10.0,
            "count": 1,
            "heat": "gray",
            "top": "opp-c",
        },
    }
    res = comp.target_industries(heatmap)
    assert res["label"] == "INFERENCE"
    assert [t["industry"] for t in res["targets"]] == [
        "Technology / SaaS",
        "Health / Wellness",
    ]
    assert all(t["label"] == "INFERENCE" for t in res["targets"])


def test_target_industries_empty_without_scan():
    res = comp.target_industries(None)
    assert res["targets"] == []
    assert "no scan data" in res["note"]


def test_change_proposals_from_observed_changes(store, monkeypatch):
    prof = _fixture_profile()
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V1}, monkeypatch
    )
    comp.snapshot_competitor(prof, store)
    _mock_urlopen_factory(
        {"https://fixture.example/pricing": _FIXTURE_HTML_V2}, monkeypatch
    )
    comp.snapshot_competitor(prof, store)

    comp.load_profiles(store)
    pfile = store / "profiles.json"
    payload = json.loads(pfile.read_text())
    payload["profiles"].append(prof)
    pfile.write_text(json.dumps(payload))

    pkg = comp.propose_upgrades(store, heatmap=None)
    kinds = {p["kind"] for p in pkg["proposals"]}
    assert "change" in kinds
    change_ps = [p for p in pkg["proposals"] if p["kind"] == "change"]
    assert all(p["label"] == "HYPOTHESIS" for p in change_ps)
    assert any("FixtureCo" in p["title"] for p in change_ps)


def test_change_proposals_from_heatmap(store):
    comp.load_profiles(store)
    heatmap = {
        "Technology / SaaS": {
            "score": 70.0,
            "count": 2,
            "heat": "green",
            "top": "opp-a",
        },
    }
    pkg = comp.propose_upgrades(store, heatmap=heatmap)
    change_ps = [p for p in pkg["proposals"] if p["kind"] == "change"]
    assert any("Technology / SaaS" in p["title"] for p in change_ps)


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_gaps_and_propose(store, monkeypatch, capsys):
    _mock_urlopen_factory({}, monkeypatch)
    assert comp.main(["gaps", "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert "demandpulse" in out and "unknown" in out
    assert comp.main(["propose", "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert "HYPOTHESIS" in out and "ADVISORY ONLY" in out


def test_cli_diff_no_changes(store, monkeypatch, capsys):
    _mock_urlopen_factory({}, monkeypatch)
    assert comp.main(["diff", "--store", str(store)]) == 0
    assert "No page changes" in capsys.readouterr().out


def test_cli_track_uses_store(store, monkeypatch, capsys):
    _mock_urlopen_factory({}, monkeypatch)
    # profiles' real pages are unknown to the fixture -> graceful failures
    assert comp.main(["track", "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert "google-trends" in out
