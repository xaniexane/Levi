"""Tests for the trust module (core/levi/trust/).

This is the proof gate for the laws declared in trust/__init__.py — the
honest inversion of the trust toll (X/Meta paid badges, the rented audience,
the sponsored shelf).
"""

import pytest

from levi.trust.attest import AttestationLedger
from levi.trust.reach import ExplicitReach, FeedItem, PublisherPost


# ---------------------------------------------------------------------------
# LAW 1: payment is never valid proof of identity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payment_proof",
    [
        "payment:card-ending-4242",
        "subscription:meta-verified-monthly",
        "billing:invoice-2026-08",
        "stripe:receipt-pi_123",
        "premium-purchase:x-premium",
        "boost:visibility-pack",
    ],
)
def test_issue_refuses_payment_as_proof(payment_proof):
    ledger = AttestationLedger()
    with pytest.raises(ValueError, match="refused"):
        ledger.issue(claim="entity:alice", proof=payment_proof, issuer="levi-local")
    assert ledger.list_claims() == []  # nothing half-recorded


def test_issue_refuses_empty_fields():
    ledger = AttestationLedger()
    with pytest.raises(ValueError):
        ledger.issue(claim="  ", proof="document:id-shown", issuer="levi-local")
    with pytest.raises(ValueError):
        ledger.issue(claim="entity:alice", proof="  ", issuer="levi-local")
    with pytest.raises(ValueError):
        ledger.issue(claim="entity:alice", proof="document:id-shown", issuer="  ")


# ---------------------------------------------------------------------------
# LAW 2/3/4: verify, chain, revocation.
# ---------------------------------------------------------------------------


def _earned():
    ledger = AttestationLedger()
    return ledger, ledger.issue(
        claim="entity:alice", proof="document:state-id-shown", issuer="keeper"
    )


def test_verify_accepts_earned_badge():
    ledger, badge = _earned()
    ok, reason = ledger.verify(badge.id)
    assert ok is True
    assert "alice" in reason


def test_verify_rejects_unknown_badge():
    ledger, _ = _earned()
    ok, reason = ledger.verify("badge-9999")
    assert ok is False
    assert reason == "unknown badge"


def test_revoked_badge_fails_verify_and_stays_in_ledger():
    ledger, badge = _earned()
    ledger.revoke(badge.id, reason="id was forged")
    ok, reason = ledger.verify(badge.id)
    assert ok is False
    assert reason == "revoked"
    # revocation is public: the record still exists, marked
    assert ledger.list_claims()[0].revoked_at is not None


def test_tampered_receipt_breaks_chain():
    ledger, _ = _earned()
    stored = ledger._badges["badge-0001"]
    from levi.trust.attest import Attestation

    ledger._badges["badge-0001"] = Attestation(
        id=stored.id,
        claim="entity:mallory",  # the quiet edit
        proof=stored.proof,
        issuer=stored.issuer,
        issued_at=stored.issued_at,
        prev_hash=stored.prev_hash,
        revoked_at=stored.revoked_at,
    )
    ok, detail = ledger.verify_chain()
    assert ok is False
    assert "tampered" in detail


def test_export_import_roundtrip_preserves_validity():
    ledger, badge = _earned()
    ledger.issue(claim="entity:bob", proof="community-vouch:3-of-5", issuer="peer")
    bundle = ledger.export_bundle()
    clone = AttestationLedger.import_bundle(bundle)
    ok, _ = clone.verify(badge.id)
    assert ok is True
    assert clone.audit()["verdict"] == "honest"


def test_import_of_tampered_bundle_fails():
    ledger, _ = _earned()
    bundle = ledger.export_bundle()
    bundle["hashes"][0] = "0" * 64  # forge a link
    with pytest.raises(ValueError, match="chain check"):
        AttestationLedger.import_bundle(bundle)


def test_audit_reports_honest_on_clean_ledger():
    ledger, _ = _earned()
    report = ledger.audit()
    assert report["verdict"] == "honest"
    assert report["payment_as_proof"] == []
    assert report["chain_ok"] is True


# ---------------------------------------------------------------------------
# LAW 5: the feed contains only explicitly subscribed publishers.
# ---------------------------------------------------------------------------


def _subscribed_feed():
    feed = ExplicitReach()
    feed.subscribe("pub:alice", label="Alice's notes")
    return feed


def test_build_feed_rejects_non_subscribed_publishers():
    feed = _subscribed_feed()
    posts = [
        PublisherPost(publisher="pub:alice", title="hello", body="world"),
        PublisherPost(publisher="pub:mallory-ads", title="buy now", body="sale"),
    ]
    with pytest.raises(ValueError, match="pub:mallory-ads"):
        feed.build_feed(posts)


def test_build_feed_delivers_subscribed_newest_first():
    feed = _subscribed_feed()
    feed.subscribe("pub:bob")
    posts = [
        PublisherPost(publisher="pub:alice", title="old", body="1", published_at=1.0),
        PublisherPost(publisher="pub:bob", title="new", body="2", published_at=2.0),
    ]
    items = feed.build_feed(posts)
    assert [i.publisher for i in items] == ["pub:bob", "pub:alice"]
    assert all(i.why_shown == "subscribed:" + i.publisher for i in items)


def test_subscribe_refuses_empty_publisher():
    feed = ExplicitReach()
    with pytest.raises(ValueError):
        feed.subscribe("   ")


# ---------------------------------------------------------------------------
# LAW 6: unsubscribing removes reach immediately.
# ---------------------------------------------------------------------------


def test_unsubscribe_removes_reach():
    feed = _subscribed_feed()
    assert feed.unsubscribe("pub:alice") is True
    with pytest.raises(ValueError, match="pub:alice"):
        feed.build_feed([PublisherPost(publisher="pub:alice", title="t", body="b")])


# ---------------------------------------------------------------------------
# LAW 7: audit_insertions flags paid insertions; clean feeds pass.
# ---------------------------------------------------------------------------


def test_audit_passes_on_honest_feed():
    feed = _subscribed_feed()
    items = feed.build_feed(
        [PublisherPost(publisher="pub:alice", title="t", body="b")]
    )
    clean, findings = feed.audit_insertions(items)
    assert clean is True
    assert findings == []


def test_audit_flags_tampered_provenance_strip():
    feed = _subscribed_feed()
    dirty = FeedItem(
        id="post-1",
        publisher="pub:alice",
        title="t",
        body="b",
        published_at=1.0,
        why_shown="sponsored:choice-badge",  # the Amazon's-Choice costume
    )
    clean, findings = feed.audit_insertions([dirty])
    assert clean is False
    assert len(findings) == 1
    assert findings[0]["item"] == "post-1"


def test_reach_state_roundtrip():
    feed = _subscribed_feed()
    clone = ExplicitReach.import_state(feed.export_state())
    assert [s.publisher for s in clone.subscriptions()] == ["pub:alice"]
    items = clone.build_feed(
        [PublisherPost(publisher="pub:alice", title="t", body="b")]
    )
    clean, _ = clone.audit_insertions(items)
    assert clean is True
