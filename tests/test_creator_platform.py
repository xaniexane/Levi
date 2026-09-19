"""Tests for the creator platform (AI reformed / SI gated)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import pricing
from levi.creator.ai import creators as ai_creators
from levi.creator.ai import dating as ai_dating
from levi.creator.ai.rules import RulesError, check_sfw
from levi.creator.money import MoneyAuthorization, charge
from levi.creator.seal import SealError, keeper_key, open_record, seal_record
from levi.creator.si import dating as si_dating
from levi.creator.si import drops as si_drops
from levi.creator.si import messaging as si_messaging
from levi.creator.si import profiles as si_profiles
from levi.creator.si import subscriptions as si_subscriptions
from levi.creator.store import ai_read_all, si_read_all
from levi.plaiground.bounds import BoundsError
from levi.plaiground.gate import (
    CONFIRMATION_PHRASE,
    GateLockedError,
    enable_adult_mode,
)


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def cybrus_tmp(tmp_path, monkeypatch):
    d = tmp_path / "cybrus"
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(d))
    return d


def _enable(home):
    return enable_adult_mode(CONFIRMATION_PHRASE, home=home)


def _keeper_auth():
    return MoneyAuthorization(authorized_by="chauncey", plan_id="", operation="charge")


# -- SI gate law --------------------------------------------------------


def test_si_profile_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_profiles.create_profile("alice", "Alice", "bio", home)


def test_si_listing_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_dating.post_listing("u1", "hi", "seeking", "terms", home)


def test_si_message_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_messaging.send("a", "b", "hello", home)


def test_si_drop_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_drops.post_drop("c", "t", "b", home=home)


def test_si_subscribe_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_subscriptions.subscribe("c", "t1", "s1", _keeper_auth(), home)


def test_si_bounds_refuse_minor_content(home):
    _enable(home)
    with pytest.raises(BoundsError):
        si_profiles.create_profile("alice", "Alice", "dating for teens", home)


def test_si_bounds_refuse_violent_content(home):
    _enable(home)
    with pytest.raises(BoundsError):
        si_messaging.send("a", "b", "i will kill you", home)


# -- SI happy paths (gated) ---------------------------------------------


def test_si_profile_roundtrip(home):
    _enable(home)
    p = si_profiles.create_profile("alice_1", "Alice", "writer and artist", home)
    assert p["track"] == TRACK_SI
    assert p["adult_content"] is True
    assert si_profiles.get_profile("alice_1", home)["handle"] == "alice_1"
    assert len(si_profiles.list_profiles(home)) == 1


def test_si_handle_uniqueness(home):
    _enable(home)
    si_profiles.create_profile("alice_1", "Alice", "bio one", home)
    with pytest.raises(ValueError):
        si_profiles.create_profile("alice_1", "Alice", "bio two", home)


def test_si_dating_flow(home):
    _enable(home)
    listing = si_dating.post_listing("u1", "Evening walks", "good conversation", "respectful only", home)
    assert listing["active"] is True
    found = si_dating.search_listings("walks", home)
    assert len(found) == 1
    resp = si_dating.respond(listing["id"], "u2", "Interested, tell me more", home)
    assert resp["listing_id"] == listing["id"]
    si_dating.deactivate(listing["id"], home)
    assert si_dating.search_listings("walks", home) == []


def test_si_messaging_thread(home):
    _enable(home)
    si_messaging.send("a", "b", "hello there", home)
    si_messaging.send("b", "a", "hi back", home)
    assert len(si_messaging.inbox("b", home)) == 1
    assert len(si_messaging.thread("a", "b", home)) == 2


def test_si_drop_flow(home):
    _enable(home)
    si_profiles.create_profile("creator_1", "Creator", "makes things", home)
    d = si_drops.post_drop("creator_1", "New chapter", "fresh writing", home=home)
    assert d["track"] == TRACK_SI
    assert len(si_drops.list_drops("creator_1", home)) == 1


def test_si_subscribe_records_pending_payment(home, cybrus_tmp):
    _enable(home)
    si_profiles.create_profile("creator_1", "Creator", "makes things", home)
    tier = si_subscriptions.add_tier("creator_1", "monthly", 400, ["early access"], home)
    sub = si_subscriptions.subscribe("creator_1", tier["id"], "fan_1", _keeper_auth(), home)
    assert sub["status"] == "pending_payment"
    assert sub["charge"] == "blocked"
    assert sub["plan_id"].startswith("mpl_")


# -- Sealing (Veil lineage) ----------------------------------------------


def test_seal_roundtrip(home):
    rec = {"a": 1, "b": "two"}
    env = seal_record(rec, home=home, context="creator/si/test")
    assert open_record(env, home=home, context="creator/si/test") == rec


def test_seal_tamper_evident(home):
    env = seal_record({"secret": "sauce"}, home=home, context="creator/si/test")
    import base64

    ct = bytearray(base64.b64decode(env["ct"]))
    ct[0] ^= 0xFF
    env["ct"] = base64.b64encode(bytes(ct)).decode("ascii")
    with pytest.raises(SealError):
        open_record(env, home=home, context="creator/si/test")


def test_seal_wrong_context(home):
    env = seal_record({"x": 1}, home=home, context="creator/si/a")
    with pytest.raises(SealError):
        open_record(env, home=home, context="creator/si/b")


def test_keeper_key_0600(home):
    keeper_key(home)
    p = home / ".levi" / "creator" / "keeper.key"
    assert p.exists()
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_si_store_is_sealed_not_plaintext(home):
    _enable(home)
    si_profiles.create_profile("secret_handle", "Secret", "hidden bio", home)
    raw = (home / ".levi" / "creator" / "si" / "profiles.jsonl").read_text()
    assert "secret_handle" not in raw  # sealed envelope, no plaintext
    assert si_read_all(home, "profiles")[0]["handle"] == "secret_handle"


def test_si_tampered_store_raises(home):
    _enable(home)
    si_profiles.create_profile("alice_1", "Alice", "bio", home)
    p = home / ".levi" / "creator" / "si" / "profiles.jsonl"
    lines = p.read_text().splitlines()
    env = json.loads(lines[0])
    env["mac"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    p.write_text(json.dumps(env) + "\n")
    with pytest.raises(SealError):
        si_read_all(home, "profiles")


# -- Money: Cybrus only, fail-closed ------------------------------------


def test_charge_blocked_no_rail(cybrus_tmp):
    result = charge(
        amount_minor=500, currency="USD", purpose="test",
        identity="tester", authorization=_keeper_auth(),
    )
    assert result["status"] == "blocked"
    assert result["plan_id"].startswith("mpl_")


def test_charge_refused_non_keeper(cybrus_tmp):
    bad = MoneyAuthorization(authorized_by="mallory", plan_id="", operation="charge")
    result = charge(
        amount_minor=500, currency="USD", purpose="test",
        identity="tester", authorization=bad,
    )
    assert result["status"] == "refused"


def test_charge_rejects_bad_amount(cybrus_tmp):
    with pytest.raises(ValueError):
        charge(
            amount_minor=0, currency="USD", purpose="test",
            identity="tester", authorization=_keeper_auth(),
        )


# -- AI track: no gate, SFW rules ---------------------------------------


def test_ai_dating_no_gate_needed(home):
    p = ai_dating.create_profile("jane_doe", "Jane", "hiker", ["hiking"], home)
    assert p["track"] == TRACK_AI
    assert len(ai_dating.list_profiles(home)) == 1


def test_ai_sfw_refuses_explicit(home):
    with pytest.raises(RulesError):
        ai_dating.create_profile("bad_actor", "Bad", "looking for hookups", ["x"], home)


def test_ai_sfw_refuses_explicit_message(home):
    ai_dating.create_profile("a_1", "A", "painter", ["art"], home)
    ai_dating.create_profile("b_1", "B", "writer", ["art"], home)
    with pytest.raises(RulesError):
        ai_dating.send_message("a_1", "b_1", "send nudes please", home)


def test_ai_floor_refuses_violent(home):
    with pytest.raises(RulesError):
        check_sfw("i will kill you", home)


def test_ai_floor_refuses_minor_content(home):
    with pytest.raises(RulesError):
        check_sfw("dating for teens", home)


def test_ai_match_by_shared_interests(home):
    ai_dating.create_profile("a_1", "A", "painter", ["art", "hiking"], home)
    ai_dating.create_profile("b_1", "B", "writer", ["art", "chess"], home)
    ai_dating.create_profile("c_1", "C", "chef", ["cooking"], home)
    matches = ai_dating.find_matches("a_1", home)
    assert len(matches) == 1
    assert matches[0]["profile"]["handle"] == "b_1"
    assert matches[0]["shared_interests"] == ["art"]


def test_ai_creator_flow(home, cybrus_tmp):
    ai_creators.create_creator("maker_1", "Maker", "tutorials", "education", home)
    tier = ai_creators.add_tier("maker_1", "monthly", 400, ["early videos"], home)
    sub = ai_creators.subscribe("maker_1", tier["id"], "fan_9", _keeper_auth(), home)
    assert sub["status"] == "pending_payment"
    drop = ai_creators.post_drop("maker_1", "Lesson 1", "welcome aboard", home)
    assert drop["track"] == TRACK_AI
    assert len(ai_creators.list_drops("maker_1", home)) == 1


def test_ai_creator_sfw_enforced(home):
    with pytest.raises(RulesError):
        ai_creators.create_creator("x_1", "X", "explicit adult content", "x", home)


# -- Track isolation -----------------------------------------------------


def test_tracks_never_merge(home):
    _enable(home)
    si_profiles.create_profile("si_only", "SI", "sealed bio", home)
    ai_dating.create_profile("ai_only", "AI", "clean bio", ["hiking"], home)
    assert ai_read_all(home, "profiles") == []
    assert si_read_all(home, "dating_profiles") == []
    assert all(p["track"] == TRACK_SI for p in si_read_all(home, "profiles"))
    assert all(p["track"] == TRACK_AI for p in ai_read_all(home, "dating_profiles"))


# -- Pricing: two schedules, doctrine-driven ------------------------------


def test_dating_schedule_prices():
    sched = {t.name: t for t in pricing.DATING_SCHEDULE}
    assert sched["day_pass"].price_minor == 100
    assert sched["weekly"].price_minor == 500
    assert sched["monthly"].price_minor == 1200
    assert all(t.track == "dating" for t in pricing.DATING_SCHEDULE)


def test_creator_schedule_prices():
    sched = {t.name: t for t in pricing.CREATOR_SCHEDULE}
    assert sched["taste"].price_minor == 100
    assert sched["monthly"].price_minor == 400
    assert sched["patron"].price_minor == 2000
    assert all(t.track == "creator" for t in pricing.CREATOR_SCHEDULE)


def test_schedules_are_separate_objects():
    assert pricing.DATING_SCHEDULE is not pricing.CREATOR_SCHEDULE
    assert pricing.schedule_for("dating") is pricing.DATING_SCHEDULE
    assert pricing.schedule_for("creator") is pricing.CREATOR_SCHEDULE
    with pytest.raises(ValueError):
        pricing.schedule_for("other")


def test_every_tier_carries_advisor_receipt():
    for t in pricing.DATING_SCHEDULE + pricing.CREATOR_SCHEDULE:
        assert t.receipt["price_minor"] == t.price_minor
        assert "band" in t.receipt and "recommended" in t.receipt
        low, high = t.receipt["band"]
        assert low <= t.price_minor / 100 <= high, t.name


def test_pricing_deterministic():
    again_d = pricing.build_dating_schedule()
    again_c = pricing.build_creator_schedule()
    assert [t.price_minor for t in again_d] == [t.price_minor for t in pricing.DATING_SCHEDULE]
    assert [t.price_minor for t in again_c] == [t.price_minor for t in pricing.CREATOR_SCHEDULE]


def test_platform_cut_undercuts_standard():
    assert pricing.PLATFORM_CUT == 0.12
    assert pricing.PLATFORM_CUT < pricing.GIANT["platform_cut_of"]["rate"] == 0.20
    assert pricing.platform_fee(1200) == 144
    assert pricing.creator_share(1200) == 1056


def test_no_free_core_in_pricing():
    for t in pricing.DATING_SCHEDULE + pricing.CREATOR_SCHEDULE:
        assert t.price_minor > 0
