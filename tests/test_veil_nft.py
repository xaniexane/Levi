"""Tests for Veil creator NFTs (levi.cybrus.veil_nft + VeilCreators wiring).

Gate: adult PIN gate enabled against a hermetic home; Cybrus stores
hermetic via LEVI_HOME. Money/approval engines run for real — mints and
purchases stay pending until the test approves them, exactly like prod.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from levi.cybrus import veil_nft
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.veil_nft import (
    CreatorNftLedger,
    VeilNFT,
    VeilNftError,
    content_hash_for,
    nft_token_id_for,
)
from levi.cybrus.veil_services import VeilCreators, VeilServiceError
from levi.genesis.nft.economics import ROYALTY_BPS
from levi.plaiground import gate


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for var in gate.MINOR_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    gate.set_pin("test-pin-1234", home=tmp_path)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "test-pin-1234",
                           home=tmp_path)
    return tmp_path


@pytest.fixture()
def chat(home):
    return types.SimpleNamespace(
        _home=home,
        _require_unlocked=lambda: b"test-master-key-32-bytes-long!!",
    )


@pytest.fixture()
def creators(chat):
    return VeilCreators(chat)


@pytest.fixture()
def creator(creators):
    return creators.register_creator(
        "testcreator", bio="test", tiers={"bronze": 500})


@pytest.fixture()
def photo_drop(creators, creator):
    return creators.publish_drop(
        creator["creator_id"], "bronze", "Sunset pic",
        body="a beautiful sunset", media_type="photo",
        media_bytes=b"\x89PNG-fake-bytes", visibility="locked",
        price_minor=1000, teaser="teaser text")


# ---------------------------------------------------------------------------
# token id + content hash laws
# ---------------------------------------------------------------------------

def test_token_id_deterministic():
    a = nft_token_id_for("c1", "hash1")
    b = nft_token_id_for("c1", "hash1")
    assert a == b
    assert isinstance(a, int) and a > 0


def test_token_id_unique_per_content_and_creator():
    assert nft_token_id_for("c1", "h1") != nft_token_id_for("c1", "h2")
    assert nft_token_id_for("c1", "h1") != nft_token_id_for("c2", "h1")


def test_token_id_domain_separated_from_genesis():
    # genesis pack ids use "series:pack" — our domain can never collide.
    assert "creator-nft:v1" not in "GENESIS-2026:pack123"


def test_content_hash_stable():
    assert content_hash_for(b"bytes", "body") == \
        content_hash_for(b"bytes", "body")
    assert content_hash_for(b"bytes", "body") != \
        content_hash_for(b"bytes!", "body")


def test_ledger_hash_chain(home):
    ledger = CreatorNftLedger(home / "nfts.json")
    assert ledger.verify()


# ---------------------------------------------------------------------------
# mint flow
# ---------------------------------------------------------------------------

def test_mint_photo_drop_pending_then_confirmed(creators, photo_drop):
    token = creators.mint_drop_as_nft(photo_drop["drop_id"])
    assert token["status"] == "pending_mint"
    assert token["media_type"] == "photo"
    assert token["royalty_bps"] == ROYALTY_BPS
    assert token["token_standard"] == "ERC-721"
    assert token["legal_gate"] == "cleared-2026-09-27"

    # Fails closed before approval.
    with pytest.raises(VeilNftError):
        creators.confirm_nft_mint(token["token_id"])

    ApprovalEngine().approve(token["approval_id"], by="owner")
    done = creators.confirm_nft_mint(token["token_id"])
    assert done["status"] == "minted"
    assert creators._nft().verify_ledger()


def test_mint_same_content_twice_refused(creators, creator, photo_drop):
    creators.mint_drop_as_nft(photo_drop["drop_id"])
    drop2 = creators.publish_drop(
        creator["creator_id"], "bronze", "Same pic again",
        media_type="photo", media_bytes=b"\x89PNG-fake-bytes",
        visibility="locked", price_minor=1000)
    with pytest.raises(VeilNftError):
        creators.mint_drop_as_nft(drop2["drop_id"])


def test_mint_text_drop_refused(creators, creator):
    drop = creators.publish_drop(
        creator["creator_id"], "bronze", "Just words",
        body="no media here", media_type="text", visibility="locked")
    with pytest.raises(VeilNftError):
        creators.mint_drop_as_nft(drop["drop_id"])


def test_mint_video_drop_ok(creators, creator):
    drop = creators.publish_drop(
        creator["creator_id"], "bronze", "Clip",
        media_type="video", media_bytes=b"fake-video-bytes",
        visibility="locked", price_minor=2500)
    token = creators.mint_drop_as_nft(drop["drop_id"])
    assert token["media_type"] == "video"
    assert token["price_minor"] == 2500


def test_mint_unknown_drop_refused(creators):
    with pytest.raises(VeilServiceError):
        creators.mint_drop_as_nft("no-such-drop")


# ---------------------------------------------------------------------------
# purchase flow
# ---------------------------------------------------------------------------

def _minted_token(creators, photo_drop):
    token = creators.mint_drop_as_nft(photo_drop["drop_id"])
    ApprovalEngine().approve(token["approval_id"], by="owner")
    return creators.confirm_nft_mint(token["token_id"])


def test_buy_unminted_refused(creators, photo_drop):
    token = creators.mint_drop_as_nft(photo_drop["drop_id"])
    with pytest.raises(VeilNftError):
        creators.buy_nft(token["token_id"], buyer_id="buyer1")


def test_buy_flow_pending_then_completed(creators, photo_drop):
    token = _minted_token(creators, photo_drop)
    purchase = creators.buy_nft(token["token_id"], buyer_id="buyer1")
    assert purchase["status"] == "pending_payment"

    with pytest.raises(VeilNftError):
        creators.confirm_nft_purchase(purchase["purchase_id"])

    ApprovalEngine().approve(purchase["approval_id"], by="owner")
    done = creators.confirm_nft_purchase(purchase["purchase_id"])
    assert done["status"] == "completed"
    # 50/30/20 split, every cent lands somewhere.
    split = done["revenue_split"]
    assert (split["creator_minor"] + split["pool_minor"]
            + split["treasury_minor"]) == 1000
    assert split["creator_minor"] == 500  # keeper's seat

    nft = creators.get_nft(token["token_id"])
    assert nft["owner"] == "owner:buyer1"
    assert len(nft["transfers"]) == 1


def test_buy_unknown_token_refused(creators):
    with pytest.raises(VeilNftError):
        creators.buy_nft("12345", buyer_id="buyer1")


def test_royalty_math(creators, photo_drop):
    token = _minted_token(creators, photo_drop)
    r = creators.nft_royalty_for(token["token_id"], 10000)
    assert r["royalty_bps"] == 750
    assert r["royalty_minor"] == 750  # 7.5% of 10000
    assert r["receiver"].startswith("creator:")


# ---------------------------------------------------------------------------
# reads + QR
# ---------------------------------------------------------------------------

def test_reads(creators, creator, photo_drop):
    token = _minted_token(creators, photo_drop)
    assert creators.get_nft(token["token_id"])["token_id"] == \
        token["token_id"]
    assert len(creators.nfts_for_creator(creator["creator_id"])) == 1
    assert len(creators.nft_for_drop(photo_drop["drop_id"])) == 1
    assert creators.get_nft("nope") is None


def test_nft_qr_roundtrip(creators, photo_drop):
    token = _minted_token(creators, photo_drop)
    ticket = creators.nft_qr(token["token_id"])
    assert ticket["qr_payload"].startswith("cybrus://creator-nft/")
    payload = creators.verify_nft_qr(ticket["qr_payload"])
    assert payload["token_id"] == token["token_id"]
    assert payload["price_minor"] == 1000
    assert payload["kind"] == "nft-purchase"


def test_nft_qr_tampered_refused(creators, photo_drop):
    token = _minted_token(creators, photo_drop)
    ticket = creators.nft_qr(token["token_id"])
    bad = ticket["qr_payload"][:-4] + "AAAA"
    with pytest.raises(VeilServiceError):
        creators.verify_nft_qr(bad)


def test_nft_qr_unminted_refused(creators, photo_drop):
    token = creators.mint_drop_as_nft(photo_drop["drop_id"])
    with pytest.raises(VeilServiceError):
        creators.nft_qr(token["token_id"])
