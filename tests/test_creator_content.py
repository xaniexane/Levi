"""Tests for the creator content service (gating invariants).

Not formal proof: invariant tests — publishing gates, grant flows,
revocation, metadata-only list views, SFW/plaiground safety rules.
"""

from __future__ import annotations

import base64

import pytest

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import content as creator_content
from levi.creator import subscriptions as subs
from levi.creator.ai.rules import RulesError
from levi.creator.money import MoneyAuthorization
from levi.creator.store import si_read_all
from levi.plaiground.gate import CONFIRMATION_PHRASE, enable_adult_mode, set_pin


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


@pytest.fixture
def keeper():
    return MoneyAuthorization(authorized_by="chauncey", plan_id="", operation="charge")


@pytest.fixture
def cybrus(iso):
    """Provision the Cybrus choke point for the creator service: the
    additive seed-policy allow rules (levi.creator.router), a starter
    rate-limit tier for the ``creator`` caller, and a service token
    carrying the ``service.call`` scope. Returns the kwargs the guarded
    calls expect (``cybrus_credential=...``)."""
    from levi.creator import router as creator_router
    from levi.cybrus import rate_limits as rl
    from levi.cybrus.tokens import TokenEngine

    creator_router.ensure_creator_routing()
    rl.set_tier(creator_router.CREATOR_CALLER, "starter")
    _, token = TokenEngine().issue(
        scopes=["service.call"],
        ttl_seconds=3600,
        kind="api",
        label="creator service token",
    )
    return {"cybrus_credential": token}


def _enable(home):
    set_pin("test-pin-1234", home=home)
    return enable_adult_mode(CONFIRMATION_PHRASE, "test-pin-1234", home=home)


def _setup(home, track=TRACK_AI):
    p = subs.create_profile("creator1", "Creator One", "bio", "bank-ref-8472", track, home)
    t = subs.add_tier(p["id"], "monthly", 400, "month", track, rank=0, home=home)
    return p, t


# -- Publishing ----------------------------------------------------------


def test_publish_tier_gated_content(home, iso):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Episode 1", "First episode", "post", TRACK_AI,
        home=home, tier_id=t["id"],
    )
    assert item["status"] == "live"
    assert item["gate"]["kind"] == "tier"
    assert item["gate"]["tier_rank"] == 0


def test_publish_requires_exactly_one_gate(home, iso):
    p, t = _setup(home)
    with pytest.raises(creator_content.ContentError):
        creator_content.publish(p["id"], "T", "d", "post", TRACK_AI, home=home)
    with pytest.raises(creator_content.ContentError):
        creator_content.publish(
            p["id"], "T", "d", "post", TRACK_AI, home=home,
            tier_id=t["id"], public=True,
        )


def test_publish_grant_gated_and_public(home, iso):
    p, t = _setup(home)
    g = creator_content.publish(
        p["id"], "PPV", "pay per view", "video", TRACK_AI,
        home=home, grants=["fan1"],
    )
    assert g["gate"]["kind"] == "grant"
    pub = creator_content.publish(
        p["id"], "Free", "everyone", "post", TRACK_AI, home=home, public=True
    )
    assert pub["gate"]["kind"] == "public"


def test_publish_rejects_bad_kind_and_bad_blob(home, iso):
    p, t = _setup(home)
    with pytest.raises(creator_content.ContentError):
        creator_content.publish(
            p["id"], "T", "d", "hologram", TRACK_AI, home=home, public=True
        )
    with pytest.raises(creator_content.ContentError):
        creator_content.publish(
            p["id"], "T", "d", "post", TRACK_AI, home=home,
            public=True, data_b64="not-valid-base64!!!",
        )


def test_publish_stores_blob_through_store(home, iso):
    p, t = _setup(home)
    data = base64.b64encode(b"fake-bytes-for-a-photo").decode("ascii")
    item = creator_content.publish(
        p["id"], "Photo", "a photo", "photo", TRACK_AI,
        home=home, tier_id=t["id"], data_b64=data,
    )
    assert item["blob_id"] is not None
    full = creator_content.list_content(p["id"], TRACK_AI, home)[0]
    assert full["blob_id"] == item["blob_id"]
    assert full["accessible"] is True  # creator's own view


def test_sfw_rules_block_violating_publish(home, iso):
    # L5: the AI-track SFW floor is a publish gate — it cannot be bypassed.
    p, t = _setup(home)
    with pytest.raises(RulesError):
        creator_content.publish(
            p["id"], "How to kill the competition", "violent post", "post",
            TRACK_AI, home=home, public=True,
        )


def test_si_publish_sealed_at_rest(home, iso):
    # L5 + store patterns: the SI track seals payloads; the raw file
    # holds no readable payload.
    _enable(home)
    p, t = _setup(home, TRACK_SI)
    secret = base64.b64encode(b"payload-that-must-not-read-plain").decode("ascii")
    item = creator_content.publish(
        p["id"], "Drop", "a sealed drop", "photo", TRACK_SI,
        home=home, tier_id=t["id"], data_b64=secret,
    )
    assert creator_content.get_item(item["id"], TRACK_SI, home)["id"] == item["id"]
    raw = (home / ".levi" / "creator" / "si" / "content_blobs.jsonl").read_text()
    assert secret not in raw  # sealed, not plaintext at rest


# -- Listing: metadata-only for the non-entitled -------------------------


def test_list_for_viewer_teases_non_subscribers(home, iso, keeper):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Gated", "gated desc", "post", TRACK_AI,
        home=home, tier_id=t["id"],
    )
    pub = creator_content.publish(
        p["id"], "Free", "free desc", "post", TRACK_AI, home=home, public=True
    )
    rows = creator_content.list_for_viewer(p["id"], "stranger", TRACK_AI, home)
    by_id = {r["id"]: r for r in rows}
    assert by_id[item["id"]]["accessible"] is False
    assert "blob_id" not in by_id[item["id"]]  # payload refs stay out of list views
    assert by_id[pub["id"]]["accessible"] is True


def test_list_for_viewer_grants_subscriber(home, iso, keeper):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Gated", "gated desc", "post", TRACK_AI,
        home=home, tier_id=t["id"],
    )
    subs.subscribe(p["id"], t["id"], "fan1", keeper, TRACK_AI, home)
    rows = creator_content.list_for_viewer(p["id"], "fan1", TRACK_AI, home)
    assert {r["id"]: r for r in rows}[item["id"]]["accessible"] is True


# -- Grants (PPV-style) ---------------------------------------------------


def test_grant_ungrant_flow(home, iso):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "PPV", "one-time", "video", TRACK_AI,
        home=home, grants=["fan1"],
    )
    g1, _ = creator_content.evaluate_gate(
        item, creator_id=p["id"], subscriber_id="fan1",
        tier_rank=None, track=TRACK_AI, home=home,
    )
    assert g1 is True
    creator_content.grant(item["id"], p["id"], "fan2", TRACK_AI, home)
    item = creator_content.get_item(item["id"], TRACK_AI, home)
    assert "fan2" in item["gate"]["subscribers"]
    creator_content.ungrant(item["id"], p["id"], "fan1", TRACK_AI, home)
    item = creator_content.get_item(item["id"], TRACK_AI, home)
    g2, reason = creator_content.evaluate_gate(
        item, creator_id=p["id"], subscriber_id="fan1",
        tier_rank=None, track=TRACK_AI, home=home,
    )
    assert g2 is False
    assert "no grant" in reason


def test_grant_is_creator_only(home, iso):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "PPV", "one-time", "video", TRACK_AI,
        home=home, grants=["fan1"],
    )
    with pytest.raises(creator_content.ContentError):
        creator_content.grant(item["id"], "not-the-creator", "fan9", TRACK_AI, home)


def test_grants_only_on_grant_gated_items(home, iso):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Gated", "d", "post", TRACK_AI, home=home, tier_id=t["id"]
    )
    with pytest.raises(creator_content.ContentError):
        creator_content.grant(item["id"], p["id"], "fan1", TRACK_AI, home)


# -- Revocation -----------------------------------------------------------


def test_revoke_denies_everyone_including_tokens(home, iso, keeper, cybrus):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Gated", "d", "post", TRACK_AI, home=home, tier_id=t["id"]
    )
    subs.subscribe(p["id"], t["id"], "fan1", keeper, TRACK_AI, home)
    tok = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    assert subs.verify_access(tok["token"], item["id"], TRACK_AI, home, **cybrus)["granted"]
    out = creator_content.revoke(item["id"], p["id"], TRACK_AI, home)
    assert out["status"] == "revoked"
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(tok["token"], item["id"], TRACK_AI, home, **cybrus)


def test_revoke_is_creator_only(home, iso):
    p, t = _setup(home)
    item = creator_content.publish(
        p["id"], "Gated", "d", "post", TRACK_AI, home=home, tier_id=t["id"]
    )
    with pytest.raises(creator_content.ContentError):
        creator_content.revoke(item["id"], "not-the-creator", TRACK_AI, home)


# -- Gate evaluation (pure decision logic) --------------------------------


def test_evaluate_gate_matrix(home, iso):
    p, t = _setup(home)
    tier_item = creator_content.publish(
        p["id"], "T", "d", "post", TRACK_AI, home=home, tier_id=t["id"]
    )
    grant_item = creator_content.publish(
        p["id"], "G", "d", "post", TRACK_AI, home=home, grants=["fan1"]
    )
    pub_item = creator_content.publish(
        p["id"], "P", "d", "post", TRACK_AI, home=home, public=True
    )

    def ev(item, sub, rank):
        return creator_content.evaluate_gate(
            item, creator_id=p["id"], subscriber_id=sub,
            tier_rank=rank, track=TRACK_AI, home=home,
        )[0]

    assert ev(tier_item, "fan9", None) is False      # no subscription
    assert ev(tier_item, "fan9", 0) is True           # exact tier rank
    assert ev(tier_item, "fan9", 5) is True           # higher rank includes lower
    assert ev(tier_item, p["id"], None) is True       # creator always sees own
    assert ev(grant_item, "fan1", None) is True       # on the grant list
    assert ev(grant_item, "fan2", None) is False      # not on the grant list
    assert ev(pub_item, "anyone", None) is True       # public
