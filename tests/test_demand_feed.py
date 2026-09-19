"""Hermetic tests for the DemandPulse feed (Wave 3).

No HOME writes (LEVI_HOME and HOME are redirected to tmp_path), no network,
no randomness beyond digest ids (pinned explicitly where asserted).
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from levi.demand import feed, si
from levi.demand import ai as ai_bridge
from levi.demand.feed import (
    Digest,
    coerce_candidates,
    curate,
    list_digest_ids,
    load_digest,
    load_latest,
    published_ids,
    render_digest,
    store_digest,
    watch_item,
    watched_ids,
)
from levi.demand.scoring import score_card, tier_for


def _herm(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("HOME", str(home))
    # DemandPulse freezes its store path at import time (pulse.DEFAULT), so
    # redirect that too — otherwise CLI tests would touch the real home.
    import levi.demand.pulse as _pulse

    monkeypatch.setattr(_pulse, "DEFAULT", home / ".levi" / "demand_pulse.json")


def _factors(**over):
    base = {
        "demand": (80, "basis: surveyed 40 users, 32 expressed need"),
        "market_size": (70, "basis: TAM estimate from industry report"),
        "competition_gap": (60, "basis: 3 incumbents, none serve segment X"),
        "trend_velocity": (50, "basis: search interest doubling YoY"),
        "entry_feasibility": (40, "basis: needs 2 engineers, 3 months"),
    }
    base.update(over)
    return base


def _cards():
    return [
        score_card(
            "opp-low",
            "Low thing",
            _factors(
                demand=(30, "basis: weak signal"),
                market_size=(30, "basis: tiny TAM"),
                competition_gap=(30, "basis: crowded"),
                trend_velocity=(30, "basis: flat"),
                entry_feasibility=(30, "basis: hard"),
            ),
        ),  # 30.0 -> low
        score_card(
            "opp-high",
            "High thing",
            _factors(
                demand=(90, "basis: waitlist of 500"),
                market_size=(90, "basis: large TAM"),
                competition_gap=(90, "basis: no incumbents"),
                trend_velocity=(90, "basis: exploding"),
                entry_feasibility=(90, "basis: trivial build"),
            ),
        ),  # 90.0 -> high
        score_card("opp-mid", "Mid thing", _factors()),  # 65.0 -> watch
    ]


# --- ranking / tiering -------------------------------------------------------


def test_digest_ranking_and_tiering_match_scoring(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    digest = curate(_cards(), digest_id="d-rank")
    assert [i["opportunity_id"] for i in digest.items] == [
        "opp-high",
        "opp-mid",
        "opp-low",
    ]
    assert [i["rank"] for i in digest.items] == [1, 2, 3]
    for item in digest.items:
        assert item["tier"] == tier_for(item["composite"])
    assert digest.summary["tiers"] == {"high": 1, "watch": 1, "low": 1}


def test_rank_ties_break_by_opportunity_id(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    a = score_card("opp-a", "A", _factors())
    b = score_card("opp-b", "B", _factors())
    assert a.composite == b.composite
    digest = curate([b, a], digest_id="d-tie")
    assert [i["opportunity_id"] for i in digest.items] == ["opp-a", "opp-b"]


def test_basis_notes_preserved_and_rendered(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    digest = curate(_cards(), digest_id="d-basis")
    mid = next(i for i in digest.items if i["opportunity_id"] == "opp-mid")
    assert mid["factors"][0]["basis"] == "basis: surveyed 40 users, 32 expressed need"
    rendered = render_digest(digest)
    assert "basis: surveyed 40 users, 32 expressed need" in rendered
    assert "Scores are analyst judgments" in rendered


# --- quarantine ----------------------------------------------------------------


def test_basisless_candidate_is_quarantined_not_published(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    factors = _factors()
    factors["demand"] = (80, "   ")  # empty basis -> dishonest
    raw = [{"opportunity_id": "opp-bad", "title": "Bad thing", "factors": factors}]
    cards, quarantined = coerce_candidates(raw)
    assert cards == []
    assert len(quarantined) == 1
    assert "basis" in quarantined[0]["reason"].lower()

    digest = curate(raw=raw, digest_id="d-q")
    assert digest.items == []
    assert len(digest.quarantined) == 1
    assert digest.summary["quarantined"] == 1
    assert "QUARANTINED" in render_digest(digest)


def test_quarantine_covers_bad_values_and_missing_fields(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    factors = _factors()
    factors["demand"] = (120, "basis: too high")  # out of range
    raw = [
        {"opportunity_id": "opp-range", "title": "Range", "factors": factors},
        {"title": "No id", "factors": _factors()},  # missing opportunity_id
        {
            "opportunity_id": "opp-miss",
            "title": "Missing factor",
            "factors": {"demand": (80, "basis: x")},
        },  # wrong factor set
        "not-a-mapping",
    ]
    cards, quarantined = coerce_candidates(raw)
    assert cards == []
    assert len(quarantined) == 4
    assert all(q["reason"] for q in quarantined)


def test_stored_card_form_round_trips_through_coerce(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    card = _cards()[0]
    cards, quarantined = coerce_candidates([card.to_dict()])
    assert quarantined == []
    assert len(cards) == 1
    assert cards[0].composite == card.composite


# --- dedupe --------------------------------------------------------------------


def test_dedupe_across_runs(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d1 = curate(_cards(), digest_id="d-001")
    store_digest(d1)

    d2 = curate(_cards(), digest_id="d-002")
    assert d2.items == []  # all already published
    assert sorted(d2.repeated_ids) == ["opp-high", "opp-low", "opp-mid"]
    assert d2.summary["repeated"] == 3
    store_digest(d2)

    assert published_ids() == {"opp-high", "opp-low", "opp-mid"}
    latest = load_latest()
    assert latest is not None
    assert latest.digest_id == "d-002"
    assert latest.summary["repeated"] == 3


def test_dedupe_within_one_run(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    cards = _cards()
    digest = curate(cards + [cards[0]], digest_id="d-dup")
    assert [i["opportunity_id"] for i in digest.items] == [
        "opp-high",
        "opp-mid",
        "opp-low",
    ]


def test_new_card_after_dedupe_is_published(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store_digest(curate(_cards(), digest_id="d-a"))
    fresh = score_card("opp-new", "New thing", _factors())
    digest = curate([fresh] + _cards(), digest_id="d-b")
    assert [i["opportunity_id"] for i in digest.items] == ["opp-new"]
    assert sorted(digest.repeated_ids) == ["opp-high", "opp-low", "opp-mid"]


# --- JSONL storage round-trip --------------------------------------------------


def test_jsonl_round_trip_under_hermetic_home(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    factors = _factors()
    factors["demand"] = (80, "")
    digest = curate(
        _cards(),
        raw=[{"opportunity_id": "x", "title": "X", "factors": factors}],
        digest_id="d-rt",
    )
    path = store_digest(digest)
    assert path.exists()
    assert path.name == "digest-d-rt.jsonl"

    loaded = load_latest()
    assert loaded is not None
    assert loaded.to_record() == digest.to_record()
    assert load_digest("d-rt").to_record() == digest.to_record()
    assert list_digest_ids() == ["d-rt"]


def test_load_latest_with_no_digests_is_none(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert load_latest() is None
    assert list_digest_ids() == []
    assert published_ids() == set()


def test_digest_record_validation():
    with pytest.raises(ValueError):
        Digest.from_record("not-a-mapping")


# --- watchlist -------------------------------------------------------------------


def test_watch_marking(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert watch_item("opp-high") is True
    assert watch_item("opp-high") is False  # idempotent
    assert watch_item("opp-mid") is True
    assert watched_ids() == ["opp-high", "opp-mid"]

    digest = curate(_cards(), digest_id="d-watch")
    by_id = {i["opportunity_id"]: i for i in digest.items}
    assert by_id["opp-high"]["watched"] is True
    assert by_id["opp-low"]["watched"] is False
    assert digest.summary["watched"] == 2

    with pytest.raises(ValueError):
        watch_item("   ")


def test_watchlist_survives_reload(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    watch_item("opp-x")
    assert watched_ids() == ["opp-x"]  # re-read from disk


# --- SI / ai separation ----------------------------------------------------------


def test_si_is_the_authoritative_native_core():
    assert si.__si_core__ is True
    assert si.curate is feed.curate
    assert si.store_digest is feed.store_digest
    assert si.load_latest is feed.load_latest


def test_si_never_imports_ai():
    import subprocess

    import levi.demand.si as si_mod

    # No import statement may reference the bridge package.
    src = Path(si_mod.__file__).read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*(from|import)\s+levi\.demand\.ai\b", src), (
        "si/ must never import the ai bridge"
    )
    # Fresh interpreter: importing si must not pull ai into sys.modules.
    # (This test file imports the bridge itself, so we check in a child.)
    core = Path(si_mod.__file__).resolve().parents[3]
    env = dict(os.environ, PYTHONPATH=str(core))
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import levi.demand.si; "
            "raise SystemExit('ai leaked' if 'levi.demand.ai' in sys.modules else 0)",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


def test_ai_bridge_is_one_way_dependent_on_si():
    src = Path(ai_bridge.__file__).read_text(encoding="utf-8")
    assert "from levi.demand import si" in src


def test_bridge_label_exact():
    expected = (
        "AI counterpart bridge for demandpulse — conventional-protocol interface; "
        "the SI core is authoritative; this bridge claims nothing"
    )
    assert ai_bridge.BRIDGE_LABEL == expected
    assert ai_bridge.bridge_notice() == expected
    assert expected in (ai_bridge.__doc__ or "")


def test_bridge_tool_schemas_are_mcp_shaped(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    names = {t["name"] for t in ai_bridge.TOOLS}
    assert names == {
        "demandpulse_get_latest_digest",
        "demandpulse_build_digest",
        "demandpulse_watch_item",
        "demandpulse_explain_item",
    }
    for tool in ai_bridge.TOOLS:
        assert tool["description"]
        assert ai_bridge.BRIDGE_LABEL in tool["description"]
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert isinstance(schema.get("properties"), dict)


# --- bridge execution ------------------------------------------------------------


def _seed_digest(monkeypatch, tmp_path, digest_id="d-bridge"):
    _herm(monkeypatch, tmp_path)
    digest = curate(_cards(), digest_id=digest_id)
    store_digest(digest)
    return digest


def test_bridge_get_latest_digest(monkeypatch, tmp_path):
    _seed_digest(monkeypatch, tmp_path)
    env = ai_bridge.execute_tool("demandpulse_get_latest_digest")
    assert env["ok"] is True
    assert env["bridge"] == ai_bridge.BRIDGE_LABEL
    assert env["result"]["digest"]["digest_id"] == "d-bridge"
    assert len(env["result"]["digest"]["items"]) == 3


def test_bridge_get_latest_digest_empty(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    env = ai_bridge.execute_tool("demandpulse_get_latest_digest")
    assert env["ok"] is True
    assert env["result"]["digest"] is None


def test_bridge_unknown_tool_raises():
    with pytest.raises(ValueError):
        ai_bridge.execute_tool("demandpulse_launch_missiles")


def test_bridge_build_digest_quarantines_honestly(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    factors = _factors()
    factors["trend_velocity"] = (50, "")
    env = ai_bridge.execute_tool(
        "demandpulse_build_digest",
        {
            "raw": [{"opportunity_id": "q1", "title": "Q1", "factors": factors}],
            "digest_id": "d-bq",
        },
    )
    assert env["ok"] is True
    assert env["result"]["summary"]["quarantined"] == 1
    assert env["result"]["summary"]["total"] == 0
    assert "QUARANTINED" in env["result"]["rendered"]


def test_bridge_build_digest_with_stored_cards(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    card = _cards()[1]
    env = ai_bridge.execute_tool(
        "demandpulse_build_digest",
        {"cards": [card.to_dict()], "digest_id": "d-bc"},
    )
    assert env["ok"] is True
    assert env["result"]["summary"]["total"] == 1
    latest = load_latest()
    assert latest.digest_id == "d-bc"


def test_bridge_watch_item(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    env = ai_bridge.execute_tool("demandpulse_watch_item", {"item_id": "opp-9"})
    assert env["ok"] is True
    assert env["result"] == {"item_id": "opp-9", "watched": True, "newly_added": True}
    assert watched_ids() == ["opp-9"]

    bad = ai_bridge.execute_tool("demandpulse_watch_item", {"item_id": " "})
    assert bad["ok"] is False
    assert bad["bridge"] == ai_bridge.BRIDGE_LABEL


def test_bridge_explain_item_found_and_missing(monkeypatch, tmp_path):
    _seed_digest(monkeypatch, tmp_path)
    env = ai_bridge.execute_tool("demandpulse_explain_item", {"item_id": "opp-high"})
    assert env["ok"] is True
    assert env["result"]["found"] is True
    assert "basis: waitlist of 500" in env["result"]["explanation"]

    missing = ai_bridge.execute_tool(
        "demandpulse_explain_item", {"item_id": "nope-not-real"}
    )
    assert missing["ok"] is True
    assert missing["result"]["found"] is False  # honest miss, no fabrication


def test_bridge_chat_completion_shape_is_deterministic():
    result = {"ok": True, "answer": 42}
    c1 = ai_bridge.as_chat_completion(result)
    c2 = ai_bridge.as_chat_completion(result)
    assert c1["object"] == "chat.completion"
    assert c1["id"] == c2["id"]
    assert c1["choices"][0]["message"]["role"] == "assistant"
    assert c1["choices"][0]["finish_reason"] == "stop"
    assert json.loads(c1["choices"][0]["message"]["content"]) == result
    assert "no model call" in c1["usage"]["note"]
    assert ai_bridge.as_chat_completion(result, model="x")["model"] == "x"


# --- CLI surface -----------------------------------------------------------------


def test_cli_feed_scores_curates_and_stores(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    rc = main(
        [
            "feed",
            "--title",
            "Taco truck",
            "--ff-demand",
            "80",
            "--ff-market",
            "70",
            "--ff-gap",
            "60",
            "--ff-velocity",
            "50",
            "--ff-feasibility",
            "40",
            "--ff-basis",
            "analyst test basis",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Taco truck" in out
    assert "analyst test basis" in out
    assert "stored:" in out
    assert len(list_digest_ids()) == 1


def test_cli_feed_second_run_dedupes(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    args = [
        "feed",
        "--title",
        "Taco truck",
        "--ff-demand",
        "80",
        "--ff-market",
        "70",
        "--ff-gap",
        "60",
        "--ff-velocity",
        "50",
        "--ff-feasibility",
        "40",
        "--ff-basis",
        "analyst test basis",
    ]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "repeats=1" in out
    assert "items=0" in out


def test_cli_feed_requires_basis(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    rc = main(["feed", "--title", "No basis", "--ff-demand", "80"])
    assert rc == 2
    assert list_digest_ids() == []


def test_cli_feed_with_nothing_to_curate(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    assert main(["feed"]) == 1


def test_cli_digest_shows_latest(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    assert main(["digest"]) == 1  # nothing stored yet
    capsys.readouterr()
    store_digest(curate(_cards(), digest_id="d-cli"))
    assert main(["digest"]) == 0
    out = capsys.readouterr().out
    assert "DemandPulse digest d-cli" in out
    assert "High thing" in out
    assert main(["digest", "--id", "d-cli"]) == 0


def test_cli_watch_marks_item(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    assert main(["watch", "--item", "opp-high"]) == 0
    out = capsys.readouterr().out
    assert "Now watching [opp-high]" in out
    assert main(["watch", "--item", "opp-high"]) == 0
    assert "Already watching" in capsys.readouterr().out
    assert watched_ids() == ["opp-high"]


def test_cli_legacy_scan_still_works(monkeypatch, tmp_path, capsys):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    rc = main(["--scan", "I need help scheduling shifts"])
    assert rc == 0
    assert "Signal" in capsys.readouterr().out


def test_cli_feed_help(monkeypatch, tmp_path):
    from levi.demand.__main__ import main

    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["feed", "--help"])
    assert exc.value.code == 0
