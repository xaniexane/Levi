"""Tests for levi.voidbox.platform — the Void Box platform surface.

Hermetic: every test roots stores at tmp_path (no HOME writes, no
network). The adult gate is opened per-test at the tmp home via the one
lawful path (set_pin + enable_adult_mode); the locked-gate tests prove
every public entry refuses without it.

Proofs: (a) the gate refuses on every module without adult mode;
(b) validation fails closed on bad input in every formed model;
(c) dating contact is refused before mutual opt-in and issued after;
(d) matching algorithm raises NotWiredError; (e) chatroom
discovery/listing/join works on the rooms primitive and private rooms
stay invisible; (f) channel post-only roles enforced (owner posts,
subscriber reads, subscriber post refused); (g) creator charging raises
NotWiredError with the RED-1 handoff dict while grants are formed;
(h) classifieds/resale listings validate, expire on read, and
purchase/checkout raise NotWiredError; (i) every module declares
WIRED/NOT_WIRED honestly and every NOT_WIRED capability raises
NotWiredError naming what is missing.
"""

import json

import pytest

from levi.plaiground import gate
from levi.plaiground.gate import GateLockedError
from levi.voidbox import rooms
from levi.voidbox.platform import (
    LAWS as PLATFORM_LAWS,
    NotMutualError,
    NotWiredError,
    PlatformError,
    ProfileNotFoundError,
    verify_laws,
)
from levi.voidbox.platform import channels as channels_mod
from levi.voidbox.platform import chatrooms as chatrooms_mod
from levi.voidbox.platform import classifieds as classifieds_mod
from levi.voidbox.platform import creator as creator_mod
from levi.voidbox.platform import dating as dating_mod
from levi.voidbox.platform import resale as resale_mod
from levi.voidbox.platform.channels import ChannelStore
from levi.voidbox.platform.classifieds import ClassifiedsStore
from levi.voidbox.platform.creator import CreatorStore
from levi.voidbox.platform.dating import DatingStore
from levi.voidbox.platform.resale import ResaleStore
from levi.voidbox.rooms import NotAdminError, RoomStore

_TEST_PIN = "424242"
_TEST_PASSPHRASE = "correct horse battery staple platform"


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


@pytest.fixture
def room_store(tmp_path):
    _open_gate(tmp_path)
    return RoomStore(_TEST_PASSPHRASE, home=tmp_path)


@pytest.fixture
def dating(tmp_path):
    _open_gate(tmp_path)
    return DatingStore(home=tmp_path)


@pytest.fixture
def channel_dir(tmp_path):
    _open_gate(tmp_path)
    return ChannelStore(home=tmp_path)


@pytest.fixture
def creator_store(tmp_path):
    _open_gate(tmp_path)
    return CreatorStore(home=tmp_path)


@pytest.fixture
def classifieds(tmp_path):
    _open_gate(tmp_path)
    return ClassifiedsStore(home=tmp_path)


@pytest.fixture
def resale(tmp_path):
    _open_gate(tmp_path)
    return ResaleStore(home=tmp_path)


# ---------------------------------------------------------------------------
# (a) the gate: every module refuses without adult mode
# ---------------------------------------------------------------------------


def test_gate_locked_dating(tmp_path):
    with pytest.raises(GateLockedError):
        DatingStore(home=tmp_path)


def test_gate_locked_channels(tmp_path):
    with pytest.raises(GateLockedError):
        ChannelStore(home=tmp_path)


def test_gate_locked_creator(tmp_path):
    with pytest.raises(GateLockedError):
        CreatorStore(home=tmp_path)


def test_gate_locked_classifieds(tmp_path):
    with pytest.raises(GateLockedError):
        ClassifiedsStore(home=tmp_path)


def test_gate_locked_resale(tmp_path):
    with pytest.raises(GateLockedError):
        ResaleStore(home=tmp_path)


def test_gate_locked_chatrooms_list(tmp_path):
    with pytest.raises(GateLockedError):
        chatrooms_mod.list_public_rooms(home=tmp_path)


def test_gate_locked_chatrooms_create(room_store, tmp_path):
    # room_store fixture opened the gate at tmp_path; relock by removing
    # the record, then every chatrooms entry must refuse.
    gate.disable_adult_mode(home=tmp_path)
    with pytest.raises(GateLockedError):
        chatrooms_mod.create_chatroom(room_store, "x", "alice", home=tmp_path)
    with pytest.raises(GateLockedError):
        chatrooms_mod.join_chatroom(room_store, "room_nope", "bob", home=tmp_path)


def test_gate_locked_mid_session_dating(dating, tmp_path):
    gate.disable_adult_mode(home=tmp_path)
    with pytest.raises(GateLockedError):
        dating.create_profile("p1", "handle1", "Name")


# ---------------------------------------------------------------------------
# (b) dating: validation fails closed
# ---------------------------------------------------------------------------


def test_dating_create_valid(dating):
    p = dating.create_profile(
        "alice", "alice_99", "Alice",
        bio="Builder, night owl.",
        prefs={"looking_for": ["dating"], "interests": ["rust", "tarot"]},
    )
    assert p["handle"] == "alice_99"
    assert p["prefs"]["looking_for"] == ["dating"]
    assert p["active"] is True


def test_dating_duplicate_handle_refused(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    with pytest.raises(PlatformError):
        dating.create_profile("bob", "alice_99", "Bob")


def test_dating_bad_handles_refused(dating):
    for bad in ["ab", "UPPER HAS SPACE", "x" * 33, ".leading", "trailing-"]:
        with pytest.raises(PlatformError):
            dating.create_profile("p_" + bad.replace(" ", "_")[:8], bad, "N")


def test_dating_bio_cap(dating):
    with pytest.raises(PlatformError):
        dating.create_profile("alice", "alice_99", "Alice", bio="x" * 501)


def test_dating_bad_prefs_refused(dating):
    with pytest.raises(PlatformError):
        dating.create_profile(
            "alice", "alice_99", "Alice",
            prefs={"looking_for": ["not-a-real-option"]},
        )
    with pytest.raises(PlatformError):
        dating.create_profile(
            "alice", "alice_99", "Alice", prefs={"unknown_key": 1}
        )
    with pytest.raises(PlatformError):
        dating.create_profile(
            "alice", "alice_99", "Alice",
            prefs={"interests": ["ok"] * 21},
        )


def test_dating_update_unknown_field_refused(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    with pytest.raises(PlatformError):
        dating.update_profile("alice", handle="newhandle")


def test_dating_missing_profile(dating):
    with pytest.raises(ProfileNotFoundError):
        dating.get_profile("ghost")


# ---------------------------------------------------------------------------
# (c) dating: mutual-opt-in before contact
# ---------------------------------------------------------------------------


def test_dating_one_way_like_never_unlocks_contact(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    dating.create_profile("bob", "bob_42", "Bob")
    res = dating.like("alice", "bob")
    assert res["mutual"] is False
    assert dating.is_mutual("alice", "bob") is False
    assert dating.mutual_matches("alice") == []
    with pytest.raises(NotMutualError):
        dating.request_contact("alice", "bob")


def test_dating_mutual_opt_in_issues_contact(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    dating.create_profile("bob", "bob_42", "Bob")
    dating.like("alice", "bob")
    res = dating.like("bob", "alice")
    assert res["mutual"] is True
    assert dating.is_mutual("alice", "bob") is True
    matches = dating.mutual_matches("alice")
    assert [m["profile_id"] for m in matches] == ["bob"]
    grant = dating.request_contact("alice", "bob")
    assert grant["mutual"] is True
    assert grant["grant"].startswith("contact_")


def test_dating_unlike_breaks_mutuality(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    dating.create_profile("bob", "bob_42", "Bob")
    dating.like("alice", "bob")
    dating.like("bob", "alice")
    assert dating.is_mutual("alice", "bob") is True
    out = dating.unlike("alice", "bob")
    assert out["withdrawn"] is True
    assert dating.is_mutual("alice", "bob") is False
    with pytest.raises(NotMutualError):
        dating.request_contact("alice", "bob")


def test_dating_self_like_refused(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    with pytest.raises(PlatformError):
        dating.like("alice", "alice")


def test_dating_like_missing_profile_refused(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    with pytest.raises(ProfileNotFoundError):
        dating.like("alice", "ghost")


# ---------------------------------------------------------------------------
# (d) dating: matching algorithm NOT_WIRED
# ---------------------------------------------------------------------------


def test_dating_match_score_not_wired(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    dating.create_profile("bob", "bob_42", "Bob")
    with pytest.raises(NotWiredError) as exc:
        dating.match_score("alice", "bob")
    assert "compatibility model" in str(exc.value.missing)


def test_dating_discovery_feed_not_wired(dating):
    dating.create_profile("alice", "alice_99", "Alice")
    with pytest.raises(NotWiredError) as exc:
        dating.discovery_feed("alice")
    assert "match_score" in str(exc.value.missing)


# ---------------------------------------------------------------------------
# (e) chatrooms on the rooms primitive
# ---------------------------------------------------------------------------


def test_chatroom_create_list_join(room_store, tmp_path):
    meta = chatrooms_mod.create_chatroom(room_store, "void-lounge", "alice",
                                        home=tmp_path)
    assert meta["public"] is True
    listed = chatrooms_mod.list_public_rooms(home=tmp_path)
    ids = [r["room_id"] for r in listed]
    assert meta["room_id"] in ids
    summary = next(r for r in listed if r["room_id"] == meta["room_id"])
    assert summary["member_count"] == 1
    assert "wrapped_epochs" not in summary  # metadata only, no key material
    joined = chatrooms_mod.join_chatroom(room_store, meta["room_id"], "bob",
                                         home=tmp_path)
    assert joined["members"]["bob"]["active"] is True
    # joiner can post and read through the surface
    env = chatrooms_mod.post_message(room_store, meta["room_id"], "bob",
                                     "hello void", home=tmp_path)
    opened = chatrooms_mod.read_message(room_store, meta["room_id"], "alice",
                                        env, home=tmp_path)
    assert opened["plaintext"] == b"hello void"


def test_chatroom_private_room_not_listed_and_join_refused(room_store, tmp_path):
    priv = room_store.create_room("secret", "alice", public=False)
    listed = chatrooms_mod.list_public_rooms(home=tmp_path)
    assert priv["room_id"] not in [r["room_id"] for r in listed]
    with pytest.raises(NotAdminError):
        chatrooms_mod.join_chatroom(room_store, priv["room_id"], "bob",
                                    home=tmp_path)


def test_chatroom_leave(room_store, tmp_path):
    meta = chatrooms_mod.create_chatroom(room_store, "void-lounge", "alice",
                                        home=tmp_path)
    chatrooms_mod.join_chatroom(room_store, meta["room_id"], "bob",
                                home=tmp_path)
    left = chatrooms_mod.leave_chatroom(room_store, meta["room_id"], "bob",
                                        home=tmp_path)
    assert left["members"]["bob"]["active"] is False


# ---------------------------------------------------------------------------
# (f) channels: admin-post, subscriber-read
# ---------------------------------------------------------------------------


def test_channel_post_only_owner(channel_dir, room_store):
    chan = channel_dir.create_channel(room_store, "vera", "night-signal",
                                      "broadcasts only")
    assert chan["owner_id"] == "vera"
    # subscriber joins first — the rooms primitive's L4 means a member can
    # only open envelopes sealed at/after their join epoch, so the post
    # under test must come after the subscribe.
    channel_dir.subscribe(room_store, chan["channel_id"], "fan1")
    env = channel_dir.post(room_store, chan["channel_id"], "vera",
                           "first broadcast")
    opened = channel_dir.read(room_store, chan["channel_id"], "fan1", env)
    assert opened["plaintext"] == b"first broadcast"
    # subscriber post refused — admin-post only
    with pytest.raises(NotAdminError):
        channel_dir.post(room_store, chan["channel_id"], "fan1", "hijack")
    # non-member read refused by the primitive
    with pytest.raises(Exception):
        channel_dir.read(room_store, chan["channel_id"], "stranger", env)


def test_channel_list_and_archive(channel_dir, room_store):
    chan = channel_dir.create_channel(room_store, "vera", "night-signal")
    listed = channel_dir.list_channels()
    assert [c["channel_id"] for c in listed] == [chan["channel_id"]]
    assert "room_id" in listed[0]
    channel_dir.archive_channel(chan["channel_id"], "vera")
    assert channel_dir.list_channels() == []
    # archived channel refuses new subscribers
    with pytest.raises(PlatformError):
        channel_dir.subscribe(room_store, chan["channel_id"], "fan2")


def test_channel_archive_only_owner(channel_dir, room_store):
    chan = channel_dir.create_channel(room_store, "vera", "night-signal")
    with pytest.raises(NotAdminError):
        channel_dir.archive_channel(chan["channel_id"], "mallory")


# ---------------------------------------------------------------------------
# (g) creator: grants formed, charging NOT_WIRED
# ---------------------------------------------------------------------------


def test_creator_profile_and_tiers(creator_store):
    c = creator_store.create_creator("vera", "vera_makes", "Vera")
    assert c["handle"] == "vera_makes"
    with pytest.raises(PlatformError):
        creator_store.create_creator("vera2", "vera_makes", "Vera Two")
    tier = creator_store.define_tier(
        "vera", "tier_gold", "Gold", 999, billing="monthly",
        perks=["early access", "chat badge"],
    )
    assert tier["price_cents"] == 999
    # validation fails closed
    with pytest.raises(PlatformError):
        creator_store.define_tier("vera", "t2", "Bad", -100)
    with pytest.raises(PlatformError):
        creator_store.define_tier("vera", "t2", "Bad", 100, billing="weekly")
    with pytest.raises(PlatformError):
        creator_store.define_tier("vera", "t2", "Bad", 100,
                                  perks=["p"] * 21)
    retired = creator_store.retire_tier("vera", "tier_gold")
    assert retired["retired"] is True
    assert creator_store.list_tiers("vera") == []
    assert len(creator_store.list_tiers("vera", include_retired=True)) == 1


def test_creator_subscribe_not_wired(creator_store):
    creator_store.create_creator("vera", "vera_makes", "Vera")
    creator_store.define_tier("vera", "tier_gold", "Gold", 999)
    with pytest.raises(NotWiredError) as exc:
        creator_store.subscribe("fan1", "vera", "tier_gold")
    err = exc.value
    assert err.capability == "creator.subscribe"
    assert "RED-1" in err.missing
    # the handoff dict rides on the error, exact and pending
    d = err.details
    assert d["ceremony"] == "RED-1"
    assert d["kind"] == "subscription_purchase"
    assert d["status"] == "pending_enforcement"
    assert d["amount_cents"] == 999
    assert d["creator_id"] == "vera"
    assert d["subscriber_id"] == "fan1"


def test_creator_grant_formed_with_red1_hook(creator_store):
    creator_store.create_creator("vera", "vera_makes", "Vera")
    creator_store.define_tier("vera", "tier_gold", "Gold", 999)
    grant = creator_store.grant_subscription(
        "vera", "fan1", "tier_gold", granted_by="vera", note="comped"
    )
    assert grant["status"] == "active"
    assert grant["red1_details"]["ceremony"] == "RED-1"
    assert grant["red1_details"]["status"] == "pending_enforcement"
    subs = creator_store.active_subscriptions("fan1")
    assert [g["tier_id"] for g in subs] == ["tier_gold"]
    # grant by non-creator refused
    with pytest.raises(NotAdminError):
        creator_store.grant_subscription(
            "vera", "fan2", "tier_gold", granted_by="mallory"
        )
    # revoke marks, never deletes
    revoked = creator_store.revoke_subscription("vera", "fan1", "tier_gold",
                                                by="vera")
    assert revoked["status"] == "revoked"
    assert creator_store.active_subscriptions("fan1") == []


# ---------------------------------------------------------------------------
# (h) classifieds: validation, expiry, purchase NOT_WIRED
# ---------------------------------------------------------------------------


def test_classifieds_validation(classifieds):
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "", "desc")
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "t" * 81, "desc")
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "title", "desc", price_cents=-5)
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "title", "desc", category="nope")
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "title", "desc",
                                 location_shape="x" * 81)
    with pytest.raises(PlatformError):
        classifieds.post_listing("s1", "title", "desc", duration_days=0)
    good = classifieds.post_listing(
        "s1", "Bike for sale", "Well kept.", price_cents=15000,
        category="goods", location_shape="Springfield",
    )
    assert good["status"] == "active"
    assert good["expires_at"] > good["posted_at"]


def _force_expire(store_path, listing_id, key="listings"):
    p = store_path
    data = json.loads(p.read_text(encoding="utf-8"))
    data[key][listing_id]["expires_at"] = "2000-01-01T00:00:00+00:00"
    p.write_text(json.dumps(data), encoding="utf-8")


def test_classifieds_expiry_on_read(classifieds, tmp_path):
    listing = classifieds.post_listing("s1", "Bike", "desc")
    store_path = (tmp_path / ".levi" / "voidbox" / "platform"
                  / "classifieds.json")
    _force_expire(store_path, listing["listing_id"])
    fetched = classifieds.get_listing(listing["listing_id"])
    assert fetched["status"] == "expired"
    assert classifieds.active_listings() == []


def test_classifieds_expire_only_seller(classifieds):
    listing = classifieds.post_listing("s1", "Bike", "desc")
    with pytest.raises(PlatformError):
        classifieds.expire_listing("mallory", listing["listing_id"])
    out = classifieds.expire_listing("s1", listing["listing_id"])
    assert out["status"] == "expired"
    assert out["withdrawn_early"] is True
    assert classifieds.active_listings() == []
    # record persists — nothing thrown away
    assert classifieds.get_listing(listing["listing_id"])["status"] == "expired"


def test_classifieds_purchase_not_wired(classifieds):
    listing = classifieds.post_listing("s1", "Bike", "desc", price_cents=15000)
    with pytest.raises(NotWiredError) as exc:
        classifieds.purchase("buyer1", listing["listing_id"])
    err = exc.value
    assert err.capability == "classifieds.purchase"
    d = err.details
    assert d["ceremony"] == "RED-1"
    assert d["kind"] == "listing_purchase"
    assert d["status"] == "pending_enforcement"
    assert d["amount_cents"] == 15000
    assert d["seller_id"] == "s1"
    assert d["buyer_id"] == "buyer1"


def test_classifieds_category_filter(classifieds):
    classifieds.post_listing("s1", "Bike", "desc", category="goods")
    classifieds.post_listing("s1", "Guitar lessons", "desc",
                             category="services")
    assert len(classifieds.active_listings()) == 2
    assert len(classifieds.active_listings(category="services")) == 1


# ---------------------------------------------------------------------------
# (i) resale: validation, expiry, checkout NOT_WIRED
# ---------------------------------------------------------------------------


def test_resale_validation(resale):
    with pytest.raises(PlatformError):
        resale.post_listing("v1", "Widget", "desc", price_cents=0,
                            quantity=1)
    with pytest.raises(PlatformError):
        resale.post_listing("v1", "Widget", "desc", price_cents=500,
                            quantity=0)
    with pytest.raises(PlatformError):
        resale.post_listing("v1", "Widget", "desc", price_cents=500,
                            quantity=1, unit="crate")
    with pytest.raises(PlatformError):
        resale.post_listing("v1", "Widget", "desc", price_cents=1.99,
                            quantity=1)
    good = resale.post_listing(
        "v1", "Widget", "desc", price_cents=500, quantity=3, unit="each",
        location_shape="Springfield",
    )
    assert good["status"] == "active"
    assert good["quantity"] == 3


def test_resale_expiry_on_read(resale, tmp_path):
    listing = resale.post_listing("v1", "Widget", "desc", price_cents=500,
                                  quantity=1)
    store_path = tmp_path / ".levi" / "voidbox" / "platform" / "resale.json"
    _force_expire(store_path, listing["listing_id"])
    fetched = resale.get_listing(listing["listing_id"])
    assert fetched["status"] == "expired"
    assert resale.active_listings() == []


def test_resale_checkout_not_wired(resale):
    listing = resale.post_listing("v1", "Widget", "desc", price_cents=500,
                                  quantity=2, unit="each")
    with pytest.raises(NotWiredError) as exc:
        resale.checkout("buyer1", listing["listing_id"])
    err = exc.value
    assert err.capability == "resale.checkout"
    d = err.details
    assert d["ceremony"] == "RED-1"
    assert d["kind"] == "resale_checkout"
    assert d["status"] == "pending_enforcement"
    assert d["amount_cents"] == 500
    assert d["quantity"] == 2
    assert d["vendor_id"] == "v1"


def test_resale_vendor_filter_and_withdraw(resale):
    a = resale.post_listing("v1", "Widget", "d", price_cents=500, quantity=1)
    resale.post_listing("v2", "Gadget", "d", price_cents=700, quantity=1)
    assert len(resale.active_listings(vendor_id="v1")) == 1
    resale.expire_listing("v1", a["listing_id"])
    assert resale.active_listings(vendor_id="v1") == []
    with pytest.raises(PlatformError):
        resale.expire_listing("mallory", a["listing_id"])


# ---------------------------------------------------------------------------
# (j) honest wiring declarations everywhere
# ---------------------------------------------------------------------------


def test_every_module_declares_laws_and_wiring():
    for mod in (dating_mod, chatrooms_mod, channels_mod, creator_mod,
                classifieds_mod, resale_mod):
        assert isinstance(mod.LAWS, tuple) and len(mod.LAWS) > 0, mod.__name__
        report = mod.wiring_report()
        assert isinstance(report, list) and len(report) > 0
        for cap, wired, detail in report:
            assert isinstance(cap, str) and isinstance(wired, bool)
            # every NOT_WIRED capability names what is missing
            assert wired or (isinstance(detail, str) and len(detail) > 0), (
                mod.__name__, cap,
            )


def test_platform_laws_present():
    assert len(PLATFORM_LAWS) >= 6
    ids = [lid for lid, _ in PLATFORM_LAWS]
    assert ids == ["L1", "L2", "L3", "L4", "L5", "L6"]


def test_verify_laws_all_hold(tmp_path):
    _open_gate(tmp_path)
    # touch each store so the platform dir exists with records
    DatingStore(home=tmp_path)
    results = verify_laws(home=tmp_path)
    assert len(results) > 0
    failed = [(lid, detail) for lid, ok, detail in results if not ok]
    assert failed == [], failed


def test_every_not_wired_capability_raises(tmp_path):
    """The load-bearing honesty test: each NOT_WIRED capability in each
    module's wiring_report raises NotWiredError when invoked."""
    _open_gate(tmp_path)
    store = RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    d = DatingStore(home=tmp_path)
    d.create_profile("alice", "alice_99", "Alice")
    d.create_profile("bob", "bob_42", "Bob")
    c = CreatorStore(home=tmp_path)
    c.create_creator("vera", "vera_makes", "Vera")
    c.define_tier("vera", "tier_gold", "Gold", 999)
    cl = ClassifiedsStore(home=tmp_path)
    listing = cl.post_listing("s1", "Bike", "desc", price_cents=15000)
    r = ResaleStore(home=tmp_path)
    rlisting = r.post_listing("v1", "Widget", "d", price_cents=500,
                              quantity=1)
    not_wired_calls = {
        ("dating", "match_score"): lambda: d.match_score("alice", "bob"),
        ("dating", "discovery_feed"): lambda: d.discovery_feed("alice"),
        ("creator", "subscribe"): lambda: c.subscribe("fan1", "vera",
                                                       "tier_gold"),
        ("classifieds", "purchase"): lambda: cl.purchase(
            "buyer1", listing["listing_id"]),
        ("resale", "checkout"): lambda: r.checkout(
            "buyer1", rlisting["listing_id"]),
    }
    for mod in (dating_mod, chatrooms_mod, channels_mod, creator_mod,
                classifieds_mod, resale_mod):
        for cap, wired, detail in mod.wiring_report():
            if wired:
                continue
            key = (mod.__name__.split(".")[-1], cap)
            assert key in not_wired_calls, "untested NOT_WIRED: %s" % (key,)
            with pytest.raises(NotWiredError) as exc:
                not_wired_calls[key]()
            assert exc.value.missing, key  # names what is missing
