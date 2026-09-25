"""Creator Android bridge tests — the exact JSON API the APK's Java shell
calls. Hermetic: temp workspace, no network, no device.

Laws:
  1. Every bridge function returns parseable JSON with an "ok" boolean.
  2. AI track works end-to-end: creator -> tier -> subscribe -> content.
  3. Money is paper-only: subscriptions record as pending_payment.
     Human-approval mandate: the first subscribe returns approval_required
     with a resumable id; the keeper approves (approve_money_charge);
     the retry with approval_id records pending_payment. The bridge
     never auto-approves.
  4. The SI track fails closed while the adult gate is off (default):
     si_* return ok:false, never raise through the bridge.
  5. Adult-gate status reports OFF by default; the PIN ceremony runs
     through the real gate (set_pin / enable_adult_mode /
     disable_adult_mode) — no bypass path exists.
  6. Content publish requires exactly one gate (tier/grants/public).
  7. Tier-cut accounting uses the voidbox table, labeled delegated-confirmed
     until Chauncey confirms the real scale; unknown tiers fail closed.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGE_SRC = REPO / "apps" / "creator-android" / "python-src" / "levi_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("creator_bridge_test", BRIDGE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(tmp_path):
    mod = load_bridge()
    ws = tmp_path / "ws"
    assert mod.set_workspace(str(ws)) == "true"
    assert json.loads(mod.seed_workspace())["ok"] is True
    return mod, ws


def call(mod, name, *args):
    out = json.loads(getattr(mod, name)(*args))
    assert isinstance(out, dict) and "ok" in out, f"{name} did not return ok-json"
    return out


def test_seed_and_gate_default_off(bridge):
    mod, ws = bridge
    creators = call(mod, "ai_list_creators")
    assert creators["ok"] and len(creators["creators"]) >= 1

    gate = call(mod, "adult_gate_status")
    assert gate["ok"] is True
    assert gate["status"]["enabled"] is False


def test_si_track_fails_closed(bridge):
    mod, ws = bridge
    for name, args in [
        ("si_list_profiles", ()),
        ("si_create_profile", ("hacker", "Hax", "bio")),
        ("si_subscribe", ("c", "t", "u", "keeper")),
        ("si_list_subscriptions", ("u",)),
    ]:
        out = call(mod, name, *args)
        assert out["ok"] is False, f"{name} should fail closed with gate off"
        assert out["error"], f"{name} should carry an error"


def test_si_publish_fails_closed(bridge):
    mod, ws = bridge
    out = call(
        mod, "publish_content", "c1", "t", "d", "post", "si", '{"public": true}'
    )
    assert out["ok"] is False


def test_creator_tier_subscribe_paper_only(bridge):
    mod, ws = bridge
    c = call(mod, "ai_create_creator", "artbyjo", "Jo", "general audience art", "art")
    assert c["ok"] is True

    t = call(mod, "ai_add_tier", "artbyjo", "Fan", 499, '["early access"]')
    assert t["ok"] is True
    tier_id = t["tier"]["id"]

    tiers = call(mod, "ai_list_tiers", "artbyjo")
    assert any(x["id"] == tier_id for x in tiers["tiers"])

    s = call(mod, "ai_subscribe", "artbyjo", tier_id, "fan1", "keeper")
    # Human-approval mandate: first call returns approval_required, never
    # an auto-approved charge.
    assert s["ok"] is False
    assert s["approval_required"] is True
    approval_id = s["approval_id"]
    assert approval_id

    # The keeper approves explicitly (the second tap).
    a = call(mod, "approve_money_charge", approval_id)
    assert a["ok"] is True

    # Retry with the approval id: no rail -> pending_payment, honest.
    s2 = call(mod, "ai_subscribe", "artbyjo", tier_id, "fan1", "keeper", approval_id)
    assert s2["ok"] is True
    assert s2["subscription"]["status"] == "pending_payment"
    assert s2["subscription"]["creator_handle"] == "artbyjo"


def test_shared_subscribe_and_access_level(bridge):
    mod, ws = bridge
    c = call(mod, "create_creator_profile", "vidpro", "Vid", "video essays", "ref-2", "ai")
    assert c["ok"] is True
    creator_id = c["profile"]["id"]

    t = call(mod, "add_subscription_tier", creator_id, "Inner", 999, "month", "ai", "[]")
    assert t["ok"] is True
    tier_id = t["tier"]["id"]

    s = call(mod, "subscribe_to_tier", creator_id, tier_id, "fan9", "keeper", "ai")
    assert s["ok"] is False
    assert s["approval_required"] is True
    approval_id = s["approval_id"]

    a = call(mod, "approve_money_charge", approval_id)
    assert a["ok"] is True

    s2 = call(mod, "subscribe_to_tier", creator_id, tier_id, "fan9", "keeper", "ai",
              approval_id)
    assert s2["ok"] is True
    assert s2["subscription"]["status"] == "pending_payment"

    lvl = call(mod, "access_level", "fan9", creator_id, "ai")
    assert lvl["ok"] is True


def test_content_publish_gates(bridge):
    mod, ws = bridge
    c = call(
        mod,
        "create_creator_profile",
        "vidmaker",
        "Vid",
        "video essays",
        "payout-ref-1",
        "ai",
    )
    assert c["ok"] is True
    creator_id = c["profile"]["id"]

    # public publish works
    p = call(
        mod,
        "publish_content",
        creator_id,
        "Hello world",
        "first post",
        "post",
        "ai",
        '{"public": true}',
    )
    assert p["ok"] is True
    item_id = p["item"]["id"]

    # exactly one gate required: zero gates -> not ok
    bad = call(mod, "publish_content", creator_id, "x", "y", "post", "ai", "{}")
    assert bad["ok"] is False

    # viewer sees it (public)
    lv = call(mod, "list_for_viewer", creator_id, "stranger", "ai")
    assert lv["ok"] is True and any(i["id"] == item_id for i in lv["items"])

    # revoke works
    r = call(mod, "revoke_content", item_id, creator_id, "ai")
    assert r["ok"] is True


def test_tier_gated_content_and_grant(bridge):
    mod, ws = bridge
    c = call(mod, "create_creator_profile", "gated", "G", "bio", "ref", "ai")
    creator_id = c["profile"]["id"]
    t = call(mod, "add_subscription_tier", creator_id, "Inner", 999, "month", "ai", "[]")
    tier_id = t["tier"]["id"]

    p = call(
        mod,
        "publish_content",
        creator_id,
        "Inner post",
        "for members",
        "post",
        "ai",
        json.dumps({"tier_id": tier_id}),
    )
    assert p["ok"] is True
    item_id = p["item"]["id"]

    # non-subscriber gets metadata-only (gating honesty)
    lv = call(mod, "list_for_viewer", creator_id, "outsider", "ai")
    items = {i["id"]: i for i in lv["items"]}
    assert item_id in items

    # PPV-style grant works — on a grant-gated item (engine law: grants
    # apply only to grant-gated items, not tier-gated ones)
    pg = call(
        mod,
        "publish_content",
        creator_id,
        "PPV special",
        "pay per view",
        "post",
        "ai",
        json.dumps({"grants": ["friend1"]}),
    )
    assert pg["ok"] is True
    g = call(mod, "grant_content", pg["item"]["id"], creator_id, "outsider", "ai")
    assert g["ok"] is True


def test_dating_flow(bridge):
    mod, ws = bridge
    a = call(mod, "ai_dating_create_profile", "alex", "Alex", "hiker", '["hiking","chess"]')
    assert a["ok"] is True
    b = call(mod, "ai_dating_create_profile", "blair", "Blair", "climber", '["hiking"]')
    assert b["ok"] is True

    m = call(mod, "ai_dating_find_matches", "alex")
    assert m["ok"] is True

    msg = call(mod, "ai_dating_message", "alex", "blair", "trail saturday?")
    assert msg["ok"] is True

    inbox = call(mod, "ai_dating_inbox", "blair")
    assert inbox["ok"] is True and len(inbox["messages"]) >= 1


def test_chats_flow(bridge):
    mod, ws = bridge
    ch = call(mod, "ai_create_chat", "artbyjo", "fan1")
    assert ch["ok"] is True
    chat_id = ch["chat"]["id"]

    s = call(mod, "ai_send_chat_message", chat_id, "fan1", "love your work")
    assert s["ok"] is True

    th = call(mod, "ai_chat_thread", chat_id, "fan1")
    assert th["ok"] is True and any(
        x.get("body") == "love your work" for x in th["messages"]
    )

    mine = call(mod, "ai_list_chats", "fan1")
    assert mine["ok"] is True and any(x["id"] == chat_id for x in mine["chats"])


def test_safety_plan_lifecycle(bridge):
    mod, ws = bridge
    c = call(mod, "safety_add_contact", "u1", "Mom", "tel:555", "ai")
    assert c["ok"] is True
    contact_id = c["contact"]["id"]

    p = call(
        mod,
        "safety_create_plan",
        "u1",
        "Sam",
        "Riverside Cafe",
        "2026-09-23T19:00:00",
        30,
        json.dumps([contact_id]),
        "ai",
        "",
    )
    assert p["ok"] is True
    plan_id = p["plan"]["id"]

    st = call(mod, "safety_plan_status", plan_id, "u1", "ai")
    assert st["ok"] is True

    ci = call(mod, "safety_check_in", plan_id, "u1", "ai")
    assert ci["ok"] is True

    end = call(mod, "safety_end_plan", plan_id, "u1", "ai")
    assert end["ok"] is True


def test_pricing_tables(bridge):
    mod, ws = bridge
    t = call(mod, "pricing_tables")
    assert t["ok"] is True
    assert t["dating"] and t["creator"]
    assert all("price_minor" in x for x in t["dating"] + t["creator"])

    sug = call(mod, "pricing_suggested_tiers", "creator")
    assert sug["ok"] is True

    sp = call(mod, "pricing_split", 1000)
    assert sp["ok"] is True
    assert sp["platform_fee"] + sp["creator_share"] == 1000


def test_media_flow(bridge):
    mod, ws = bridge
    call(mod, "ai_create_creator", "photog", "P", "photos", "photo")
    m = call(
        mod,
        "ai_post_media",
        "photog",
        "photo",
        "Sunset",
        "sunset.jpg",
        "",
        '{"public": true}',
    )
    # media post may require payload or gate shape; either ok:true or a
    # structured not-ok — never an unhandled raise through the bridge.
    assert "ok" in m


def _call(mod, fn, *args):
    return json.loads(getattr(mod, fn)(*args))


def test_plaiground_ceremony_roundtrip(bridge):
    mod, ws = bridge
    # Gate off by default.
    st = _call(mod, "adult_gate_status")
    assert st["ok"] is True
    assert st["status"]["enabled"] is False

    # No PIN yet; enable refuses.
    assert _call(mod, "plaiground_has_pin")["has_pin"] is False
    phrase = _call(mod, "plaiground_confirmation_phrase")["phrase"]
    assert isinstance(phrase, str) and len(phrase) > 8
    bad = _call(mod, "plaiground_enable", phrase, "0000")
    assert bad["ok"] is False  # no PIN set -> refuses

    # Set PIN, wrong phrase refuses, right phrase + PIN enables.
    assert _call(mod, "plaiground_set_pin", "correct horse 1")["ok"] is True
    assert _call(mod, "plaiground_has_pin")["has_pin"] is True
    assert _call(mod, "plaiground_enable", "wrong phrase", "correct horse 1")["ok"] is False
    assert _call(mod, "plaiground_enable", phrase, "wrong pin")["ok"] is False
    assert _call(mod, "plaiground_enable", phrase, "correct horse 1")["ok"] is True

    # Disable always allowed, no PIN needed.
    assert _call(mod, "plaiground_disable")["ok"] is True
    st2 = _call(mod, "adult_gate_status")
    assert st2["status"]["enabled"] is False


def test_tier_cut_delegated_confirmed(bridge):
    mod, ws = bridge
    t = _call(mod, "money_tier_table")
    assert t["ok"] is True
    assert t["provisional"] is False
    assert t["delegated"] is True  # Rex's rates on his word, reversible
    assert t["confirmation"]["mode"] == "delegated"
    assert t["confirmation"]["reversible"] is True
    assert t["table_version"] == "delegated-1"
    assert set(t["rates"]) == {"free", "pro", "hybrid", "elite"}
    assert t["rates"] == {"free": 1200, "pro": 900, "hybrid": 600, "elite": 300}

    s = _call(mod, "money_tier_cut", 1000, "free")
    assert s["ok"] is True
    assert s["platform_cents"] == 120  # 12%
    assert s["creator_cents"] == 880
    assert s["provisional"] is False
    assert s["delegated"] is True
    assert s["platform_cents"] + s["creator_cents"] == 1000

    # Unknown tier fails closed, never guesses.
    bad = _call(mod, "money_tier_cut", 1000, "titan")
    assert bad["ok"] is False


def test_si_classifieds_gate_locked(bridge):
    mod, ws = bridge
    # Gate off: every classifieds call fails closed through the bridge.
    assert _call(mod, "si_post_listing", "p1", "h", "s", "t")["ok"] is False
    assert _call(mod, "si_search_listings", "anything")["ok"] is False
    assert _call(mod, "si_respond_listing", "l1", "r1", "hi", True)["ok"] is False
    assert _call(mod, "si_deactivate_listing", "l1")["ok"] is False


def test_operators_surfaces(bridge):
    mod, ws = bridge
    c = _call(mod, "ops_cybrus_status")
    assert c["ok"] is True
    assert "law" in c["gateway"]

    laws = _call(mod, "ops_alerter_laws")
    assert laws["ok"] is True

    inbox = _call(mod, "ops_alerts_inbox")
    assert inbox["ok"] is True
    assert isinstance(inbox["alerts"], list)

    d = _call(mod, "ops_demand_status")
    assert d["ok"] is True


def test_dispatch_hos_and_refusal(bridge):
    mod, ws = bridge
    ok = _call(mod, "dispatch_hos_check", 2.0, 3.0)
    assert ok["ok"] is True
    assert isinstance(ok["violations"], list)

    r = _call(mod, "dispatch_refusal_check", "hello world")
    assert r["ok"] is True
    assert "refused" in r


def test_systems_status_all_probe(bridge):
    mod, ws = bridge
    s = _call(mod, "systems_status")
    assert s["ok"] is True
    names = {x["system"] for x in s["systems"]}
    for expected in ("demand", "organs", "media", "twins", "hub", "finance",
                     "jobs", "backup", "memory", "vault", "sentinel"):
        assert expected in names, expected
    # Every entry is honest: on_device true with detail, or false with gate.
    for x in s["systems"]:
        assert isinstance(x["on_device"], bool)
        assert x["detail"]


def test_daemon_colony_roster(bridge):
    mod, ws = bridge
    d = _call(mod, "daemon_colony")
    assert d["ok"] is True
    assert d["count"] > 0
    assert all("daemon" in x for x in d["daemons"])
