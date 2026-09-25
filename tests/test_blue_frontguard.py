"""BLUE-1 batch B: FRONT-GUARD regression proofs (RED-1 G1–G6).

Each attack below is CLOSED by commit 2ab7da65 ("FRONT rule-evasion
hardening (RED-1 G1-G6) + R11 publisher-namespace gate"). Every test
proves the attack closure AND the legitimate counterpart, so the fixes
cannot be read as "block everything".

Glyph: 💉 | Agent: cfbc6fb1-6ab7-451d-8c11b83ab41 | 2026-09-23
"""

import pytest

from levi.cybrus import front


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _msg(**kw):
    d = {
        "id": "m1",
        "channel": "email",
        "from": "",
        "subject": "",
        "body": "",
        "urls": [],
        "attachments": [],
    }
    d.update(kw)
    return d


def _rules(**kw):
    return front.screen_message(_msg(**kw))["rules"]


# ---------------------------------------------------------------------------
# G1 — brand display-name with a space no longer evades R01
# ---------------------------------------------------------------------------

def test_blue_g1_spaced_brand_display_name_fires_r01():
    rules = _rules(**{"from": "Pay Pal <billing@evil.com>"})
    assert "R01" in rules


def test_blue_g1_legit_brand_display_name_clean_of_r01():
    rules = _rules(**{"from": "PayPal <billing@paypal.com>",
                     "subject": "Your receipt",
                     "body": "Thanks for your purchase."})
    assert "R01" not in rules


# ---------------------------------------------------------------------------
# G2 — adjacent-transposition lookalike domains fire R02 (Damerau)
# ---------------------------------------------------------------------------

def test_blue_g2_transposed_lookalike_fires_r02():
    rules = _rules(**{"from": "support@paypla.com"})
    assert "R02" in rules


def test_blue_g2_legit_brand_domain_clean_of_r02():
    rules = _rules(**{"from": "support@paypal.com",
                     "subject": "hello",
                     "body": "your statement is ready"})
    assert "R02" not in rules


# ---------------------------------------------------------------------------
# G3 — brand-as-subdomain-of-attacker fires R02; brand's own subdomain OK
# ---------------------------------------------------------------------------

def test_blue_g3_brand_under_attacker_domain_fires_r02():
    rules = _rules(**{"from": "support@paypal.evil.com"})
    assert "R02" in rules


def test_blue_g3_legit_brand_subdomain_clean_of_r02():
    rules = _rules(**{"from": "noreply@login.paypal.com",
                     "subject": "security alert",
                     "body": "a new device signed in"})
    assert "R02" not in rules


# ---------------------------------------------------------------------------
# G4 — trailing space/dot on attachment names no longer evades R06
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["invoice.exe ", "malware.exe."])
def test_blue_g4_padded_risky_attachment_fires_r06(name):
    receipt = front.screen_message(_msg(attachments=[name]))
    assert "R06" in receipt["rules"]


def test_blue_g4_legit_attachment_clean_of_r06():
    receipt = front.screen_message(_msg(attachments=["report.pdf"]))
    assert "R06" not in receipt["rules"]


# ---------------------------------------------------------------------------
# G5/G6 — non-dict inputs quarantine (R99), never CLEAN
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, [], "hello", 42])
def test_blue_g5g6_non_message_quarantines_r99(bad):
    receipt = front.screen_message(bad)
    assert receipt["verdict"] == "QUARANTINE"
    assert "R99" in receipt["rules"]


def test_blue_g5g6_valid_message_still_screens():
    receipt = front.screen_message(_msg(subject="hi", body="hello"))
    assert receipt["verdict"] in ("CLEAN", "WARN", "QUARANTINE")
    assert "R99" not in receipt["rules"]
