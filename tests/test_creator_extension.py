"""Tests for the creator-platform extension: private media, chats, dating privacy."""

from __future__ import annotations

import base64

import pytest

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator.ai import chats as ai_chats
from levi.creator.ai import media as ai_media
from levi.creator.ai.rules import RulesError
from levi.creator.si import chats as si_chats
from levi.creator.si import dating as si_dating
from levi.creator.si import media as si_media
from levi.creator.si import privacy as si_privacy
from levi.creator.si import profiles as si_profiles
from levi.creator.si import subscriptions as si_subscriptions
from levi.creator.money import MoneyAuthorization
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


def _enable(home):
    return enable_adult_mode(CONFIRMATION_PHRASE, home=home)


def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def _auth():
    return MoneyAuthorization(authorized_by="chauncey", plan_id="", operation="charge")


# -- SI media ---------------------------------------------------------------


def test_si_media_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_media.post_media("c1", "photo", "t", "a.jpg", _b64(b"bytes"), home=home)


def test_si_media_private_by_default(home):
    _enable(home)
    m = si_media.post_media("c1", "photo", "Sunset", "sun.jpg", _b64(b"img-bytes"), home=home)
    assert m["track"] == TRACK_SI and m["kind"] == "photo"
    assert m["sha256"]
    # Stranger cannot view; creator can.
    assert si_media.can_view(m["id"], "stranger", home) is False
    with pytest.raises(si_media.AccessDeniedError):
        si_media.view(m["id"], "stranger", home)
    seen = si_media.view(m["id"], "c1", home)
    assert seen["data_b64"] == _b64(b"img-bytes")


def test_si_media_tier_gating(home):
    _enable(home)
    si_profiles.create_profile("creator1", "C One", "creator bio", home)
    tier = si_subscriptions.add_tier("creator1", "Gold", 500, ["perks"], home)
    m = si_media.post_media("creator1", "video", "Vlog", "v.mp4", _b64(b"vid"), tier_id=tier["id"], home=home)
    assert si_media.can_view(m["id"], "sub1", home) is False
    si_subscriptions.subscribe("creator1", tier["id"], "sub1", _auth(), home)
    assert si_media.can_view(m["id"], "sub1", home) is True
    # list_media hides payloads and hides unentitled items.
    metas = si_media.list_media("creator1", "sub1", home)
    assert len(metas) == 1 and "data_b64" not in metas[0]


def test_si_media_per_subscriber_grant_and_revoke(home):
    _enable(home)
    m = si_media.post_media("c1", "photo", "Gift", "g.jpg", _b64(b"px"), home=home)
    si_media.grant_access(m["id"], "c1", "vip1", home)
    assert si_media.can_view(m["id"], "vip1", home) is True
    assert si_media.revoke_access(m["id"], "c1", "vip1", home) is True
    assert si_media.can_view(m["id"], "vip1", home) is False
    with pytest.raises(si_media.AccessDeniedError):
        si_media.grant_access(m["id"], "other_creator", "vip1", home)


def test_si_media_sealed_at_rest(home):
    _enable(home)
    secret = b"top-secret-pixels"
    si_media.post_media("c1", "photo", "T", "t.jpg", _b64(secret), home=home)
    raw = (home / ".levi" / "creator" / "si" / "media.jsonl").read_text()
    assert _b64(secret) not in raw  # payload sealed, never plaintext


def test_si_media_bounds_and_kind_refusals(home):
    _enable(home)
    with pytest.raises(si_media.MediaError):
        si_media.post_media("c1", "audio", "T", "a.mp3", _b64(b"x"), home=home)
    with pytest.raises(BoundsError):
        si_media.post_media("c1", "photo", "dating for teens", "a.jpg", _b64(b"x"), home=home)


# -- SI chats ---------------------------------------------------------------


def test_si_chats_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        si_chats.create_chat("c1", "u1", home)


def test_si_dm_membership_enforced(home):
    _enable(home)
    chat = si_chats.create_chat("c1", "u1", home)
    si_chats.send_chat_message(chat["id"], "c1", "hello there", home)
    assert len(si_chats.chat_thread(chat["id"], "u1", home)) == 1
    with pytest.raises(si_chats.ChatDeniedError):
        si_chats.send_chat_message(chat["id"], "intruder", "let me in", home)
    with pytest.raises(si_chats.ChatDeniedError):
        si_chats.chat_thread(chat["id"], "intruder", home)
    assert si_chats.list_chats("intruder", home) == []


def test_si_group_owner_moderation(home):
    _enable(home)
    g = si_chats.create_group("c1", "Inner Circle", ["u1", "u2"], home)
    si_chats.send_chat_message(g["id"], "u1", "hey all", home)
    # Non-owner cannot moderate.
    with pytest.raises(si_chats.ChatDeniedError):
        si_chats.add_member(g["id"], "u1", "u3", home)
    si_chats.add_member(g["id"], "c1", "u3", home)
    # New member can read the thread — membership proven, no denial.
    assert len(si_chats.chat_thread(g["id"], "u3", home)) == 1
    si_chats.remove_member(g["id"], "c1", "u2", home)
    with pytest.raises(si_chats.ChatDeniedError):
        si_chats.send_chat_message(g["id"], "u2", "im back", home)
    # Owner cannot remove themselves.
    with pytest.raises(si_chats.ChatError):
        si_chats.remove_member(g["id"], "c1", "c1", home)
    # Close stops sending, keeps history readable.
    si_chats.close_chat(g["id"], "c1", home)
    with pytest.raises(si_chats.ChatError):
        si_chats.send_chat_message(g["id"], "u1", "too late", home)
    assert len(si_chats.chat_thread(g["id"], "u1", home)) == 1


# -- SI dating privacy --------------------------------------------------------


def _listing(home):
    _enable(home)
    return si_dating.post_listing("poster1", "Coffee first", "good company", "$100 roses", home)


def test_si_public_search_hides_poster_identity(home):
    listing = _listing(home)
    results = si_privacy.public_search("coffee", home)
    assert len(results) == 1
    assert "poster_id" not in results[0]
    assert results[0]["headline"] == "Coffee first"


def test_si_respond_disclosure_gate(home):
    listing = _listing(home)
    # Explicit: hide identity.
    r = si_privacy.respond(listing["id"], "resp1", "interested, discreet", home, reveal_profile=False)
    assert r["displayed_as"].startswith("anon_")
    views = si_privacy.read_responses_for_listing(listing["id"], "poster1", home)
    assert views[0]["from"] == r["displayed_as"]
    assert "responder_id" not in views[0]  # nothing leaks to the poster
    # The responder can still see their own full record.
    mine = si_privacy.read_response(r["id"], "resp1", home)
    assert mine["responder_id"] == "resp1"


def test_si_respond_reveal_true_shows_id(home):
    listing = _listing(home)
    si_privacy.respond(listing["id"], "resp2", "hello", home, reveal_profile=True)
    views = si_privacy.read_responses_for_listing(listing["id"], "poster1", home)
    assert views[0]["from"] == "resp2"


def test_si_response_reads_participant_only(home):
    listing = _listing(home)
    r = si_privacy.respond(listing["id"], "resp1", "hi", home)
    with pytest.raises(si_privacy.PrivacyDeniedError):
        si_privacy.read_response(r["id"], "snooper", home)
    with pytest.raises(si_privacy.PrivacyDeniedError):
        si_privacy.read_responses_for_listing(listing["id"], "snooper", home)


# -- AI mirrors ---------------------------------------------------------------


def test_ai_media_sfw_and_gating(home):
    m = ai_media.post_media("c1", "photo", "Sunset shoot", "s.jpg", _b64(b"px"), home=home)
    assert m["track"] == TRACK_AI
    assert ai_media.can_view(m["id"], "stranger", home) is False
    ai_media.grant_access(m["id"], "c1", "fan1", home)
    assert ai_media.view(m["id"], "fan1", home)["filename"] == "s.jpg"
    with pytest.raises(RulesError):
        ai_media.post_media("c1", "photo", "explicit xxx shoot", "s.jpg", _b64(b"px"), home=home)


def test_ai_chats_membership_and_moderation(home):
    g = ai_chats.create_group("c1", "Fan Club", ["u1"], home)
    ai_chats.send_chat_message(g["id"], "u1", "love the work", home)
    assert len(ai_chats.chat_thread(g["id"], "c1", home)) == 1
    with pytest.raises(ai_chats.ChatDeniedError):
        ai_chats.send_chat_message(g["id"], "snooper", "hi", home)
    with pytest.raises(ai_chats.ChatDeniedError):
        ai_chats.add_member(g["id"], "u1", "u9", home)
    with pytest.raises(RulesError):
        ai_chats.send_chat_message(g["id"], "u1", "send nudes please", home)


# -- Track isolation for the new kinds ------------------------------------------


def test_extension_tracks_never_merge(home):
    _enable(home)
    si_media.post_media("c1", "photo", "T", "t.jpg", _b64(b"x"), home=home)
    ai_media.post_media("c1", "photo", "T", "t.jpg", _b64(b"x"), home=home)
    assert len(si_read_all(home, "media")) == 1
    assert len(ai_read_all(home, "creator_media")) == 1
    si_chats.create_chat("c1", "u1", home)
    ai_chats.create_chat("c1", "u1", home)
    assert len(si_read_all(home, "chats")) == 1
    assert len(ai_read_all(home, "creator_chats")) == 1
