"""Tests for revival wave 25 — honest-inversions (a).

Seven modules: free_social_layer, privacy_defaults, transparent_commerce,
creator_economics, honest_personalization, honest_subscriptions, owned_media.
"""

import os

import pytest

from core.levi.revival import free_social_layer as fsl
from core.levi.revival import privacy_defaults as pd
from core.levi.revival import transparent_commerce as tc
from core.levi.revival import creator_economics as ce
from core.levi.revival import honest_personalization as hp
from core.levi.revival import honest_subscriptions as hs
from core.levi.revival import owned_media as om


# --- free_social_layer ---


def test_social_feed_is_chronological_and_unranked():
    layer = fsl.FreeLayer()
    layer.join("a")
    layer.join("b")
    layer.follow("a", "b")
    first = layer.post("b", "hello")
    second = layer.post("b", "world")
    feed = layer.feed("a")
    assert [p.id for p in feed] == [first.id, second.id]
    # no tracking fields on posts
    assert not hasattr(first, "views")
    assert not hasattr(first, "impressions")


def test_social_stated_price_is_nothing_and_true():
    layer = fsl.FreeLayer()
    costs = layer.costs()
    assert costs["money"] == 0.0
    assert costs["tracking_fields"] == []
    assert costs["ads_shown"] == 0
    assert fsl.STATED_PRICE == "nothing"


def test_social_export_and_roundtrip(tmp_path):
    layer = fsl.FreeLayer()
    layer.join("a")
    layer.join("b")
    layer.follow("a", "b")
    layer.post("a", "my post")
    exported = layer.export("a")
    assert exported["follows"] == ["b"]
    assert exported["posts"][0]["body"] == "my post"
    path = str(tmp_path / "layer.json")
    layer.save(path)
    assert os.path.exists(path)
    restored = fsl.FreeLayer.load(path)
    assert [p.body for p in restored.feed("a")] == ["my post"]
    assert restored.feed("a")[0].author == "a"


def test_social_unfollow_is_as_easy_as_follow():
    layer = fsl.FreeLayer()
    layer.join("a")
    layer.join("b")
    layer.follow("a", "b")
    layer.unfollow("a", "b")
    assert layer.feed("a") == []


# --- privacy_defaults ---


def test_privacy_defaults_are_most_private():
    m = pd.PrivacyManifest()
    m.declare(
        "share_analytics",
        "Share usage analytics",
        default=False,
        leaves_device=True,
        probe=lambda: False,
    )
    m.declare(
        "local_history",
        "Keep local history",
        default=True,
        leaves_device=False,
        probe=lambda: True,
    )
    assert m.get("share_analytics") is False
    assert m.get("local_history") is True
    assert m.never_leaves_device() is True


def test_privacy_verify_catches_lying_setting():
    # probe reports reality=True while the setting claims False
    m = pd.PrivacyManifest()
    m.declare(
        "cloud_backup",
        "Back up to cloud",
        default=False,
        leaves_device=True,
        probe=lambda: True,
    )
    mismatches = m.verify()
    assert len(mismatches) == 1
    assert mismatches[0]["name"] == "cloud_backup"
    assert mismatches[0]["claimed"] is False
    assert mismatches[0]["actual"] is True


def test_privacy_verify_clean_when_honest_and_audits_access():
    m = pd.PrivacyManifest()
    m.declare(
        "share_analytics",
        "Share usage analytics",
        default=False,
        leaves_device=True,
        probe=lambda: False,
    )
    assert m.verify() == []
    m.set("share_analytics", True)
    assert m.never_leaves_device() is False
    log = m.audit_log()
    assert len(log) == 1
    assert log[0]["accessor"] == "user"
    assert "when" in log[0]


def test_privacy_describe_lists_everything():
    m = pd.PrivacyManifest()
    m.declare("x", "does x", default=False, leaves_device=False)
    text = m.describe()
    assert "x" in text and "stays on device" in text


# --- transparent_commerce ---


def test_commerce_rejects_asymmetric_flow_at_registration():
    with pytest.raises(tc.FrictionAsymmetryError):
        tc.Flow(name="trap", signup_steps=1, cancel_steps=5, price_cents=999)
    # symmetric flows are fine
    flow = tc.Flow(name="fair", signup_steps=2, cancel_steps=2, price_cents=500)
    assert flow.cancel_steps <= flow.signup_steps


def test_commerce_one_click_cancel_with_receipt():
    shop = tc.Commerce()
    shop.register_flow(
        tc.Flow(name="pro", signup_steps=1, cancel_steps=1, price_cents=1200)
    )
    sub = shop.subscribe("pro", "chauncey")
    assert shop.is_active(sub.id) is True
    receipt = shop.cancel(sub.id)
    assert shop.is_active(sub.id) is False
    assert receipt.final_charge_cents == 0
    assert receipt.subscription_id == sub.id
    # second cancel is idempotent, not a trap
    receipt2 = shop.cancel(sub.id)
    assert receipt2.subscription_id == sub.id


def test_commerce_friction_report_states_steps():
    shop = tc.Commerce()
    shop.register_flow(
        tc.Flow(name="basic", signup_steps=3, cancel_steps=1, price_cents=100)
    )
    report = shop.friction_report()
    assert report[0]["signup_steps"] == 3
    assert report[0]["cancel_steps"] == 1
    assert shop.max_exit_steps() == 1


# --- creator_economics ---


def test_creator_payout_uses_published_rate_card():
    ledger = ce.CreatorLedger(ce.RateCard(per_unit_cents=10, quality_bonus_cents=5))
    ledger.register_creator("mae")
    ledger.record_delivery(ce.Delivery(creator="mae", units=100, saves=40, finishes=60))
    # weight = (40+60)/(2*100) = 0.5 -> base 1000 + bonus int(100*5*0.5)=250
    assert ledger.payout_cents("mae") == 1250


def test_creator_quality_weight_is_public_bounded_formula():
    assert ce.quality_weight(0, 0, 10) == 0.0
    assert ce.quality_weight(10, 10, 10) == 1.0
    # over-signal clamps to 1.0, never above
    assert ce.quality_weight(100, 100, 10) == 1.0
    assert ce.quality_weight(0, 0, 0) == 0.0


def test_creator_audience_is_portable_and_breakdown_checks_math():
    ledger = ce.CreatorLedger(ce.RateCard(per_unit_cents=10, quality_bonus_cents=5))
    ledger.register_creator("mae")
    ledger.add_audience("mae", "fan1")
    ledger.add_audience("mae", "fan2")
    ledger.record_delivery(ce.Delivery(creator="mae", units=10, saves=5, finishes=5))
    assert ledger.export_audience("mae") == ["fan1", "fan2"]
    lines = ledger.payout_breakdown("mae")
    assert len(lines) == 1
    assert lines[0]["total_cents"] == lines[0]["base_cents"] + lines[0]["bonus_cents"]
    assert ledger.payout_cents("mae") == lines[0]["total_cents"]
    assert "Same card for everyone" in ledger.rate_card.describe()


# --- honest_personalization ---


def test_personalization_learns_inspects_and_explains():
    profile = hp.TasteProfile()
    profile.observe({"synth": 1.0, "jazz": 0.2}, liked=True)
    profile.observe({"synth": 1.0}, liked=True)
    assert profile.score({"synth": 1.0}) > profile.score({"jazz": 1.0})
    inspected = dict(profile.inspect())
    assert inspected["synth"] > 0
    explanation = profile.explain({"synth": 1.0, "jazz": 1.0})
    assert explanation[0][0] == "synth"


def test_personalization_user_can_tune_remove_wipe():
    profile = hp.TasteProfile()
    profile.observe({"synth": 1.0}, liked=True)
    profile.tune("synth", -1.0)
    assert profile.score({"synth": 1.0}) == -1.0
    profile.remove("synth")
    assert profile.score({"synth": 1.0}) == 0.0
    profile.observe({"jazz": 1.0}, liked=True)
    profile.wipe()
    assert profile.inspect() == []
    assert profile.observations == 0
    with pytest.raises(ValueError):
        profile.tune("jazz", 5.0)


def test_personalization_recommend_is_reproducible():
    profile = hp.TasteProfile()
    profile.observe({"synth": 1.0}, liked=True)
    candidates = {
        "a": {"synth": 1.0},
        "b": {"jazz": 1.0},
        "c": {"synth": 0.5},
    }
    first = profile.recommend(candidates)
    second = profile.recommend(candidates)
    assert first == second
    assert first[0][0] == "a"


# --- honest_subscriptions ---


def test_subscription_price_locked_against_later_rises():
    billing = hs.Billing()
    billing.define_plan(hs.Plan(name="plus", price_cents=500, blurb="Plus plan"))
    sub = billing.subscribe("plus", "chauncey")
    billing.define_plan(hs.Plan(name="plus", price_cents=900, blurb="Plus plan"))
    assert billing.my_price(sub.id) == 500
    advertised = {p["plan"]: p["price_cents"] for p in billing.plans()}
    assert advertised["plus"] == 900  # new signups see the new price


def test_tier_change_requires_explicit_consent():
    billing = hs.Billing()
    billing.define_plan(hs.Plan(name="basic", price_cents=100))
    billing.define_plan(hs.Plan(name="pro", price_cents=1000))
    sub = billing.subscribe("basic", "chauncey")
    with pytest.raises(hs.MigrationRefused):
        billing.change_tier(sub.id, "pro")
    with pytest.raises(hs.MigrationRefused):
        billing.change_tier(sub.id, "pro", consent=False)
    moved = billing.change_tier(sub.id, "pro", consent=True)
    assert moved.plan_name == "pro"
    assert billing.my_price(sub.id) == 1000
    assert moved.consent_log[0]["consent"] == "explicit"


def test_subscription_cancel_is_immediate():
    billing = hs.Billing()
    billing.define_plan(hs.Plan(name="basic", price_cents=100))
    sub = billing.subscribe("basic", "chauncey")
    receipt = billing.cancel(sub.id)
    assert billing.is_active(sub.id) is False
    assert receipt["final_bill_cents"] == 0
    assert receipt["subscription_id"] == sub.id


# --- owned_media ---


def test_owned_media_ingest_play_verify():
    lib = om.Library()
    data = b"\x00\x01fake-bytes-of-a-song"
    item = lib.ingest("song.bin", data, media_type="audio/mpeg")
    assert item.size == len(data)
    # play returns the actual bytes; no license machinery exists
    assert lib.play("song.bin") == data
    assert not hasattr(lib, "check_license")
    assert lib.verify() == []


def test_owned_media_receipt_has_no_expiry():
    lib = om.Library()
    lib.ingest("film.bin", b"film-bytes")
    receipt = lib.ownership_receipt("film.bin")
    assert receipt["expires"] is None
    assert receipt["license_required"] is False
    assert receipt["owner"] == "you"
    assert len(receipt["sha256"]) == 64


def test_owned_media_export_and_roundtrip(tmp_path):
    lib = om.Library()
    lib.ingest("song.bin", b"\x00\x01song-bytes")
    out = str(tmp_path / "song.bin")
    lib.export("song.bin", out)
    with open(out, "rb") as fh:
        assert fh.read() == b"\x00\x01song-bytes"
    sidecar = str(tmp_path / "library.json")
    lib.save(sidecar)
    restored = om.Library.load(sidecar)
    assert restored.play("song.bin") == b"\x00\x01song-bytes"
    assert restored.verify() == []


def test_owned_media_verify_catches_corruption():
    lib = om.Library()
    lib.ingest("song.bin", b"original-bytes")
    # simulate bit rot behind the library's back
    lib._items["song.bin"].data = b"tampered-bytes"
    corrupted = lib.verify()
    assert len(corrupted) == 1
    assert corrupted[0]["name"] == "song.bin"
