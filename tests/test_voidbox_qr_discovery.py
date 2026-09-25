"""Tests for Void Box discovery/distribution QR (qr_discovery.py).

Every QR type gets the full round trip: encode -> scan -> decode ->
verify signature -> tamper refusal. Scannability of the symbol itself
is guaranteed by qr.py's Q3 (zero-remainder check at encode time);
here we prove the PAYLOADS round-trip and refuse tampering.
"""

import pytest

from levi.plaiground import gate
from levi.voidbox.payments.qr import QRCode
from levi.voidbox.payments.qr_discovery import (
    DiscoveryQr,
    QRDistributionError,
    QRError,
    QRTamperError,
    SURFACES,
    verify_laws,
)

_TEST_PIN = "424242"
_TEST_PASSPHRASE = "correct horse battery staple voidbox"


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


@pytest.fixture
def dq(tmp_path):
    _open_gate(tmp_path)
    return DiscoveryQr(_TEST_PASSPHRASE, home=tmp_path)


# -- discovery round trips ------------------------------------------------


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_discovery_roundtrip_all_surfaces(dq, surface):
    text = dq.discovery_text(surface, "feed01")
    qr = QRCode(text, "M")  # the symbol itself is verified at encode
    assert qr.matrix
    parsed_surface, ref = dq.parse_discovery(text)
    assert parsed_surface == surface
    assert ref == "feed01"


def test_discovery_qr_symbol(dq):
    qr = dq.discovery_qr("trending", "now")
    assert qr.version >= 1
    surface, ref = dq.parse_discovery(
        "voidbox://d/T/now/" + qr_text_tag(dq, "trending", "now")
    )
    assert (surface, ref) == ("trending", "now")


def qr_text_tag(dq, surface, ref_id):
    return dq.discovery_text(surface, ref_id).rsplit("/", 1)[1]


def test_discovery_payload_fits_version4(dq):
    # Longest legal payload: 12-char ref id.
    text = dq.discovery_text("collection", "x" * 12)
    assert len(text.encode("utf-8")) <= 62
    QRCode(text, "M")


def test_discovery_unknown_surface_refused(dq):
    with pytest.raises(QRError):
        dq.discovery_text("banking", "feed01")


def test_discovery_bad_ref_refused(dq):
    for bad in ("", "has space", "way-too-long-ref-id", "semi;colon"):
        with pytest.raises(QRError):
            dq.discovery_text("dating", bad)


def test_discovery_tamper_refused(dq):
    text = dq.discovery_text("creators", "summer25")
    # Flip the last tag char.
    tampered = text[:-1] + ("0" if text[-1] != "0" else "1")
    with pytest.raises(QRTamperError):
        dq.parse_discovery(tampered)
    # Swap the ref id (signature no longer matches).
    swapped = text.replace("/summer25/", "/winter25/")
    with pytest.raises(QRTamperError):
        dq.parse_discovery(swapped)
    # Forge a surface code.
    forged = text.replace("/C/", "/D/")
    with pytest.raises(QRTamperError):
        dq.parse_discovery(forged)


def test_discovery_malformed_refused(dq):
    for bad in ("https://example.com", "voidbox://d/C", "voidbox://d/C/x/",
                "voidbox://d/C/x/nothex!!nothex!!nothex!!12"):
        with pytest.raises(QRTamperError):
            dq.parse_discovery(bad)


def test_discovery_cross_key_refused(tmp_path, dq):
    # A payload minted under a different passphrase must not verify.
    _open_gate(tmp_path)
    other = DiscoveryQr("a completely different passphrase", home=tmp_path)
    text = dq.discovery_text("resale", "deals")
    with pytest.raises(QRTamperError):
        other.parse_discovery(text)


# -- app distribution -----------------------------------------------------


def test_app_roundtrip(dq):
    text = dq.app_text("android")
    assert text.startswith("voidbox://get/android/")
    assert dq.parse_app(text) == "android"
    assert dq.app_qr("android").matrix


def test_app_tamper_refused(dq):
    text = dq.app_text("android")
    with pytest.raises(QRTamperError):
        dq.parse_app(text[:-1] + ("0" if text[-1] != "0" else "1"))


def test_distribution_unset_refused_with_remedy(dq):
    with pytest.raises(QRDistributionError) as exc:
        dq.distribution_url("android")
    assert "configure_distribution" in str(exc.value)


def test_distribution_configure_and_resolve(dq):
    dq.configure_distribution("https://example.invalid/vb/")
    assert dq.distribution_url("android") == "https://example.invalid/vb/android"
    assert dq.distribution_base() == "https://example.invalid/vb"


def test_distribution_bad_url_refused(dq):
    with pytest.raises(QRDistributionError):
        dq.configure_distribution("not-a-url")


# -- creator referrals ----------------------------------------------------


def test_referral_roundtrip(dq):
    text, code = dq.referral_text("creator1")
    assert text.startswith("voidbox://r/")
    assert dq.parse_referral(text) == code
    qr, code2 = dq.referral_qr("creator1")
    assert qr.matrix and len(code2) == 12


def test_referral_codes_unique(dq):
    _, c1 = dq.referral_text("creator1")
    _, c2 = dq.referral_text("creator1")
    assert c1 != c2


def test_referral_tamper_refused(dq):
    text, _ = dq.referral_text("creator1")
    with pytest.raises(QRTamperError):
        dq.parse_referral(text[:-1] + ("0" if text[-1] != "0" else "1"))


def test_referral_attribution_feeds_tier_cut(dq):
    _, code = dq.referral_text("creator1")
    rec = dq.record_referral(code, "newuser9")
    assert rec["referrer_creator_id"] == "creator1"
    assert rec["referred_id"] == "newuser9"
    attrs = dq.attributions_for("creator1")
    assert len(attrs) == 1 and attrs[0]["code"] == code
    assert dq.attributions_for("nobody") == []


def test_referral_unknown_code_refused(dq):
    with pytest.raises(QRError):
        dq.record_referral("AAAAAAAAAAAA", "newuser9")


def test_referral_ledger_survives_reopen(tmp_path):
    _open_gate(tmp_path)
    dq1 = DiscoveryQr(_TEST_PASSPHRASE, home=tmp_path)
    _, code = dq1.referral_text("creator1")
    dq1.lock()
    dq2 = DiscoveryQr(_TEST_PASSPHRASE, home=tmp_path)
    rec = dq2.record_referral(code, "newuser9")
    assert rec["referrer_creator_id"] == "creator1"


# -- share cards ----------------------------------------------------------


def test_share_card_ascii(dq):
    text = dq.discovery_text("chatrooms", "lounge")
    card = dq.share_card("The Lounge", "a Void Box chatroom", text)
    assert "The Lounge" in card and "Void Box" in card
    # The card wraps a real, scannable QR of the same payload.
    assert QRCode(text, "M").matrix


def test_share_card_svg(dq):
    text = dq.discovery_text("channels", "news")
    card = dq.share_card("News", "a Void Box channel", text, card_format="svg")
    assert "<svg" in card and "News" in card


def test_share_card_rejects_foreign_links(dq):
    with pytest.raises(QRError):
        dq.share_card("X", "y", "https://evil.example/")


# -- the gate -------------------------------------------------------------


def test_gate_locked_refuses(tmp_path, dq):
    gate.disable_adult_mode(home=tmp_path)
    with pytest.raises(Exception):
        dq.discovery_text("dating", "tonight")
    with pytest.raises(Exception):
        dq.referral_text("creator1")
    with pytest.raises(Exception):
        dq.app_text("android")


# -- machine-checked laws --------------------------------------------------


def test_verify_laws():
    results = verify_laws()
    assert results, "verify_laws returned nothing"
    failed = [(law, detail) for law, ok, detail in results if not ok]
    assert not failed, "law failures: %s" % failed
