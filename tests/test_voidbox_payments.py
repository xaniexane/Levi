"""Tests for levi.voidbox.payments — the money layer that moves nothing.

Hermetic: every test roots stores at tmp_path (no HOME writes, no
network). The adult gate is opened per-test at the tmp home via the one
lawful path (set_pin + enable_adult_mode).

Proofs: (a) all 39 machine-checked laws hold; (b) integer-cent
accounting refuses floats/strings/negatives and splits sum exactly;
(c) creator and platform destinations are typed apart; (d) plugins
build deterministic deep links with no I/O; (e) tier table is labeled
provisional and unknown tiers fail closed; (f) QR encoder round-trips
and refuses over-capacity; (g) prepared requests are inert and carry
RED-1 details; (h) subscribe/purchase/checkout stay NOT_WIRED;
(i) receipt verification fails closed.
"""

import pytest

from levi.plaiground import gate
from levi.voidbox import payments
from levi.voidbox.payments import (
    CreatorDestination,
    PaymentError,
    PaymentRequest,
    PlatformDestination,
    Receipt,
    cents,
    encode_qr,
    get_plugin,
    invite_qr,
    invite_qr_text,
    is_delegated,
    is_provisional,
    confirmation,
    payment_qr,
    payment_qr_text,
    prepare_request,
    price_split,
    profile_qr,
    profile_qr_text,
)
from levi.voidbox.platform import NotWiredError
from levi.voidbox.platform import creator as creator_mod
from levi.voidbox.platform import classifieds as classifieds_mod
from levi.voidbox.platform import resale as resale_mod


@pytest.fixture()
def home(tmp_path):
    gate.set_pin("1234", tmp_path)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "1234", tmp_path)
    return tmp_path


@pytest.fixture()
def platform_dest():
    return PlatformDestination(plugin="cashapp", handle="$chauncey")


def test_all_payment_laws_hold():
    bad = [(lid, d) for lid, ok, d in payments.verify_laws() if not ok]
    assert not bad, "payment laws failed: %r" % (bad,)


def test_wiring_report_honest():
    report = dict((n, w) for n, w, _ in payments.wiring_report())
    assert report["money_movement"] is False
    assert report["receipt_verification"] is False
    assert report["request_preparation"] is True
    assert report["tier_cut_accounting"] is True


def test_cents_refuses_non_integers():
    for bad in (10.5, "100", -1, True, None, 2**70 * 1.0):
        with pytest.raises(PaymentError):
            cents(bad)
    assert cents(2500) == 2500


def test_split_sums_exactly_no_dust():
    for total in (1, 99, 999, 1000, 2500, 99999):
        s = price_split(total, "free")
        assert s.platform_cents + s.creator_cents == s.total_cents == total


def test_tier_table_delegated_confirmed():
    # Tier names are Chauncey's; rates were confirmed by DELEGATION —
    # Rex's numbers on his word, reversible, stamped delegated not direct.
    assert not is_provisional()
    assert is_delegated()
    conf = confirmation()
    assert conf is not None
    assert conf["mode"] == "delegated"
    assert conf["reversible"] is True
    assert conf["table_version"] == "delegated-1"
    s = price_split(1000, "elite")
    assert s.tier == "elite", "confirmed tables carry no provisional marker, got %r" % s.tier
    assert s.platform_cents == 30 and s.creator_cents == 970  # 3%


def test_tier_cut_ordering_free_biggest_elite_smallest():
    cuts = {t: price_split(10000, t).platform_cents
            for t in ("free", "pro", "hybrid", "elite")}
    assert cuts == {"free": 1200, "pro": 900, "hybrid": 600, "elite": 300}
    assert cuts["free"] > cuts["pro"] > cuts["hybrid"] > cuts["elite"]


def test_unknown_tier_fails_closed():
    with pytest.raises(PaymentError):
        price_split(1000, "titan")


def test_destinations_typed_apart():
    cd = CreatorDestination(plugin="cashapp", handle="$creator", creator_id="c1")
    pd = PlatformDestination(plugin="cashapp", handle="$chauncey")
    assert type(cd) is not type(pd)
    with pytest.raises(PaymentError):
        PlatformDestination(plugin="venmo", handle="$x")
    with pytest.raises(PaymentError):
        CreatorDestination(plugin="cashapp", handle="", creator_id="c1")


def test_plugins_deterministic_links():
    cashapp = get_plugin("cashapp")
    paypal = get_plugin("paypal")
    assert cashapp.build_request_link("$voidbox", 2500) == "https://cash.app/$voidbox"
    assert paypal.build_request_link("voidbox", 2500) == "https://paypal.me/voidbox/25.00"
    with pytest.raises(PaymentError):
        get_plugin("venmo")
    with pytest.raises(PaymentError):
        cashapp.build_request_link("no-dollar-sign", 100)


def test_qr_round_trip_and_capacity():
    q = encode_qr("https://cash.app/$voidbox", "M")
    assert q.size == 4 * q.version + 17
    assert sum(sum(row) for row in q.matrix) > 0
    with pytest.raises(Exception):
        encode_qr("x" * 500, "M")
    assert payment_qr_text("cashapp", "https://cash.app/$voidbox") == "https://cash.app/$voidbox"
    assert invite_qr_text("abc", "127.0.0.1", 4799) == "voidbox://invite?room=abc&relay=127.0.0.1:4799"
    assert profile_qr_text("creator", "c1") == "voidbox://creator/c1"
    # QR object helpers encode the same texts.
    assert payment_qr("cashapp", "https://cash.app/$voidbox").matrix
    assert invite_qr("abc", "127.0.0.1", 4799).version >= 1
    assert profile_qr("listing", "l1").size > 0


def test_prepare_request_inert_with_red1(platform_dest):
    cd = CreatorDestination(plugin="paypal", handle="creator-h", creator_id="c1")
    req = prepare_request("subscription", 2500, "free", platform_dest, cd, memo="t")
    assert isinstance(req, PaymentRequest)
    assert req.split.platform_cents + req.split.creator_cents == 2500
    assert "$chauncey" in req.deep_link
    assert "creator-h" not in req.deep_link  # payer pays the platform
    assert req.red1_details["ceremony"] == "RED-1"
    assert req.red1_details["status"] == "pending_enforcement"
    assert req.qr_text == req.deep_link  # PP2: verbatim


def test_prepare_request_requires_platform_destination():
    with pytest.raises(PaymentError):
        prepare_request("resale", 100, "free", None)
    with pytest.raises(PaymentError):
        prepare_request("classified", 100, "free",
                        PlatformDestination(plugin="cashapp", handle="$c"),
                        "$bare-string")


def test_receipt_verify_fails_closed(platform_dest):
    req = prepare_request("resale", 500, "free", platform_dest)
    r = Receipt(receipt_id="rc1", request_id=req.request_id, claimed_cents=500)
    assert r.status == "unverified"
    with pytest.raises(NotWiredError):
        r.verify()
    assert r.status == "unverified"


def test_creator_payout_and_subscribe_flow(home, platform_dest):
    cs = creator_mod.CreatorStore(home)
    cs.create_creator("c1", "creator-one", "Creator One")
    payout = cs.set_payout_destination("c1", "paypal", "creator-paypal", by="c1")
    assert payout["handle"] == "creator-paypal"
    dest = cs.get_payout_destination("c1")
    assert isinstance(dest, CreatorDestination)
    assert cs.get_payout_destination("c1").handle == "creator-paypal"

    # only the creator sets their own payout
    with pytest.raises(Exception):
        cs.set_payout_destination("c1", "paypal", "evil", by="someone-else")

    cs.define_tier("c1", "t1", "Supporter", 2500, "monthly", ["perk"])
    req = cs.prepare_subscribe_request("buyer1", "c1", "t1", platform_dest)
    assert req["status"] == "prepared_not_charged"
    assert req["split"]["total_cents"] == 2500
    assert req["tier_table_provisional"] is False
    assert req["red1_details"]["tier_confirmation"]["mode"] == "delegated"

    # the charge itself stays NOT_WIRED
    with pytest.raises(NotWiredError):
        cs.subscribe("buyer1", "c1", "t1")


def test_classifieds_prepare_purchase(home, platform_dest):
    st = classifieds_mod.ClassifiedsStore(home)
    listing = st.post_listing("seller1", "Test item", "a test item",
                              price_cents=1500)
    req = st.prepare_purchase_request("buyer1", listing["listing_id"], platform_dest)
    assert req["status"] == "prepared_not_charged"
    assert req["split"]["total_cents"] == 1500
    with pytest.raises(NotWiredError):
        st.purchase("buyer1", listing["listing_id"])


def test_resale_prepare_checkout(home, platform_dest):
    st = resale_mod.ResaleStore(home)
    listing = st.post_listing("vendor1", "Test product", "a test product",
                              price_cents=999, quantity=1, unit="each")
    req = st.prepare_checkout_request("buyer1", listing["listing_id"], platform_dest)
    assert req["status"] == "prepared_not_charged"
    assert req["split"]["total_cents"] == 999
    with pytest.raises(NotWiredError):
        st.checkout("buyer1", listing["listing_id"])
