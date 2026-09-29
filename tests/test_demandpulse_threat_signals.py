"""Tests for threat_signals input guards (wave 4 hardening).

Classification-law tests live in tests/test_cybrus_demand_pairing.py;
this file pins the API-edge behavior: single-string input, None input,
credential presence, and the feed receipt contract.
"""

import pytest

from levi.demandpulse import threat_signals


def test_publish_scan_none_texts_is_honest_silence():
    receipt = threat_signals.publish_scan(None, credential="tok")
    assert receipt["published"] == 0
    assert "nothing published" in receipt["note"]


def test_publish_scan_single_string_is_one_text_not_chars():
    # A single string must not be iterated character-by-character
    # (which would raise ValueError per char in classify_threat).
    receipt = threat_signals.publish_scan(
        "nothing threatening here at all, just a calm sentence",
        credential="tok",
    )
    assert receipt["published"] == 0


def test_publish_scan_rejects_empty_credential():
    with pytest.raises(ValueError, match="credential is required"):
        threat_signals.publish_scan(["text"], credential="")
    with pytest.raises(ValueError, match="credential is required"):
        threat_signals.publish_scan(["text"], credential=None)


def test_classify_threat_rejects_empty_text():
    with pytest.raises(ValueError, match="non-empty string"):
        threat_signals.classify_threat("   ")
    with pytest.raises(ValueError, match="non-empty string"):
        threat_signals.classify_threat(None)


def test_classify_threat_confidence_never_certain():
    inds = threat_signals.classify_threat(
        "You have won the lottery! Claim your prize now, pay the "
        "processing fee via wire transfer immediately."
    )
    assert inds
    assert all(i["confidence"] < 1.0 for i in inds)
    assert all(i["detector"] == threat_signals.DETECTOR for i in inds)
    assert all(len(i["snippet"]) <= threat_signals.SNIPPET_MAX for i in inds)


def test_phishing_needs_a_link():
    no_link = threat_signals.classify_threat(
        "Please verify your account immediately to avoid suspension."
    )
    assert all(i["kind"] != "phishing" for i in no_link)
    with_link = threat_signals.classify_threat(
        "Please verify your account immediately at https://evil.example/login."
    )
    assert any(i["kind"] == "phishing" for i in with_link)
