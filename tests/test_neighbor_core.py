"""Hermetic tests for the NeighborOS Phase 1 core (post/work/pay/monetize).

No HOME writes: stores are constructed on tmp_path. No network, no
randomness. All example data is synthetic.
"""

import json

import pytest

from levi.neighbor import lift, monetize, pay, policies as policies_mod, post, work
from levi.neighbor.store import Store

NOW = "2026-09-17T15:00:00+00:00"


def _store(tmp_path):
    return Store(tmp_path / "neighbor")


def _policies(store):
    return policies_mod.load_policies(store)


def _publish(store, **kw):
    gig = post.draft_gig(
        title=kw.get("title", "Fix leaky faucet"),
        category=kw.get("category", "plumbing"),
        description=kw.get("description", "drips all night"),
        requester=kw.get("requester", "Ann H"),
        requester_contact=kw.get("contact", "ann@example.com"),
        neighborhood_cell=kw.get("cell", "springfield-test"),
        estimate=kw.get("estimate", 120.0),
    )
    return post.publish_gig(store, gig, confirm=True, now=NOW)


def _worker(store, **kw):
    return work.register_worker(
        store,
        name=kw.get("name", "Bob W"),
        contact=kw.get("contact", "bob@example.com"),
        categories=kw.get("categories", ["plumbing"]),
        home_cell=kw.get("cell", "springfield-test"),
        now=NOW,
    )


def _completed_gig(store, amount=120.0):
    """Full pipeline to a signed-off gig, ready for settlement.

    Runs at soft_launch stage by writing the gate stage directly into the
    operator config (the keeper's gate, not a test bypass of the law).
    """
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    cfg["gates"]["stage"] = "soft_launch"
    path.write_text(json.dumps(cfg))
    gig = _publish(store)
    worker = _worker(store)
    lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=True, now=NOW)
    lift.accept_offer(store, gig["id"], worker["id"], now=NOW)
    work.check_in(store, gig["id"], worker["id"], now=NOW)
    work.check_out(store, gig["id"], worker["id"], now=NOW)
    work.sign_off(store, gig["id"], "Ann H", 5, final_amount=amount, now=NOW)
    return gig, worker


# -- Job DNA ------------------------------------------------------------
def test_job_dna_stable(tmp_path):
    a = post.job_dna("plumbing", "Fix leaky faucet", "drips", "cell-a", 120)
    b = post.job_dna("Plumbing ", "fix LEAKY faucet", "drips", "cell-a", 120)
    assert a["dna"] == b["dna"]
    assert a["dna_family"] == "plumbing@cell-a/small"


def test_job_dna_sensitive_to_scope(tmp_path):
    a = post.job_dna("plumbing", "Fix leaky faucet", "drips", "cell-a", 120)
    b = post.job_dna("plumbing", "Install water heater", "cold showers", "cell-a", 120)
    assert a["dna"] != b["dna"]
    assert a["dna_family"] == b["dna_family"]  # same family, different job


def test_price_band_edges():
    assert post.price_band(None) == "unknown"
    assert post.price_band(99.99) == "micro"
    assert post.price_band(499.99) == "small"
    assert post.price_band(1999.99) == "medium"
    assert post.price_band(2000) == "large"


def test_estimate_band_honest_when_thin(tmp_path):
    store = _store(tmp_path)
    band = post.estimate_band(store, "plumbing@cell/small")
    assert band["history_thin"] is True
    assert band["based_on"] == 0


def test_estimate_band_data_backed_after_history(tmp_path):
    store = _store(tmp_path)
    for amount in (100.0, 140.0, 160.0):
        gig, _ = _completed_gig(store, amount=amount)
    band = post.estimate_band(store, "plumbing@springfield-test/small")
    assert band["history_thin"] is False
    assert band["low"] == 100.0 and band["high"] == 160.0
    assert band["based_on"] == 3


# -- publish pipeline ----------------------------------------------------
def test_publish_requires_permission(tmp_path):
    store = _store(tmp_path)
    gig = post.draft_gig("t", "plumbing", "d", "r", "c", "cell")
    with pytest.raises(PermissionError):
        post.publish_gig(store, gig, confirm=False)


def test_publish_assigns_id_and_opens(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    assert gig["id"] == "gig-0001"
    assert gig["status"] == "open"
    assert gig["requester_contact"] == "ann@example.com"  # plain, never masked


def test_preview_names_contact_and_dna(tmp_path):
    store = _store(tmp_path)
    gig = post.draft_gig(
        "Fix leaky faucet",
        "plumbing",
        "drips",
        "Ann H",
        "ann@example.com",
        "springfield-test",
        120,
    )
    text = post.preview_gig(store, gig)
    assert "ann@example.com" in text
    assert "thin history" in text
    assert gig["dna"][:16] in text


# -- proof of work ----------------------------------------------------------
def test_sign_off_requires_checkout(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    with pytest.raises(ValueError):
        work.sign_off(store, gig["id"], "Ann H", 5)


def test_rating_bounds(tmp_path):
    store = _store(tmp_path)
    gig, worker = _completed_gig(store)
    gig2 = _publish(store, title="second job")
    lift.offer(store, gig2["id"], worker["id"], operator="k", confirm=True, now=NOW)
    lift.accept_offer(store, gig2["id"], worker["id"], now=NOW)
    work.check_in(store, gig2["id"], worker["id"], now=NOW)
    work.check_out(store, gig2["id"], worker["id"], now=NOW)
    with pytest.raises(ValueError):
        work.sign_off(store, gig2["id"], "Ann H", 6)


def test_credential_claims_never_verified_by_us(tmp_path):
    store = _store(tmp_path)
    worker = work.register_worker(
        store,
        "Bob",
        "bob@x",
        ["plumbing"],
        "cell",
        credentials=[{"type": "EPA 608", "issuer": "EPA"}],
        now=NOW,
    )
    claim = worker["credentials"][0]
    assert claim["verified_by_us"] is False
    assert claim["asserted_by"] == "EPA"
    assert "asserted_at" in claim


# -- fee math ------------------------------------------------------------------
def test_fee_bands_match_corpus(tmp_path):
    store = _store(tmp_path)
    p = _policies(store)
    assert monetize.compute_fee(50, p)["band_rate"] == 0.12
    assert monetize.compute_fee(120, p)["band_rate"] == 0.10
    assert monetize.compute_fee(1000, p)["band_rate"] == 0.08
    assert monetize.compute_fee(5000, p)["band_rate"] == 0.06


def test_floor_clamp_fires_where_band_would_undercut(tmp_path):
    store = _store(tmp_path)
    p = _policies(store)
    fee = monetize.compute_fee(50, p)  # 12% band → 88% keep, under the floor
    assert fee["clamped"] is True
    assert fee["keep_rate"] >= 0.90
    assert fee["applied_rate"] == 0.10  # platform eats the difference


def test_emergency_band_still_cannot_break_floor(tmp_path):
    store = _store(tmp_path)
    p = _policies(store)
    fee = monetize.compute_fee(3000, p, emergency=True)
    assert fee["band_rate"] == 0.15
    assert fee["clamped"] is True
    assert fee["keep_rate"] >= 0.90


def test_pro_worker_reduction(tmp_path):
    store = _store(tmp_path)
    p = _policies(store)
    base = monetize.compute_fee(300, p)
    pro = monetize.compute_fee(300, p, pro_worker=True)
    assert pro["applied_rate"] == pytest.approx(base["applied_rate"] - 0.02)
    assert pro["keep_rate"] >= 0.90


def test_fee_receipt_is_inspectable(tmp_path):
    store = _store(tmp_path)
    p = _policies(store)
    text = monetize.fee_receipt(monetize.compute_fee(120, p), "gig-0001", "worker-0001")
    assert "$108.00" in text and "90.00%" in text


def test_lowering_floor_is_rejected(tmp_path):
    store = _store(tmp_path)
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    cfg["worker_keep_floor"] = 0.80
    path.write_text(json.dumps(cfg))
    with pytest.raises(policies_mod.FloorViolation):
        policies_mod.load_policies(store)


# -- settlement ledger ------------------------------------------------------------
def test_settle_refuses_unfinished_gig(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    with pytest.raises(pay.SettlementRefused):
        pay.settle(
            store, gig["id"], 120, rail="cash", rail_reference="R1", confirm=True
        )


def test_settle_requires_rail_reference(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    with pytest.raises(pay.SettlementRefused):
        pay.settle(store, gig["id"], 120, rail="", rail_reference="", confirm=True)


def test_settle_requires_permission(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    with pytest.raises(PermissionError):
        pay.settle(
            store, gig["id"], 120, rail="cash", rail_reference="R1", confirm=False
        )


def test_settlement_records_not_moves(tmp_path):
    store = _store(tmp_path)
    gig, worker = _completed_gig(store)
    entry = pay.settle(
        store,
        gig["id"],
        120,
        rail="cash",
        rail_reference="CASH-1",
        confirm=True,
        now=NOW,
    )
    assert entry["status"] == "recorded"
    assert entry["rail"] == "cash" and entry["rail_reference"] == "CASH-1"
    assert entry["worker_keep"] == 108.0
    assert pay.verify_settlement(store, entry["id"])["ok"] is True


def test_mark_cleared_moves_gig_to_paid(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    entry = pay.settle(
        store, gig["id"], 120, rail="cash", rail_reference="C-1", confirm=True, now=NOW
    )
    cleared = pay.mark_cleared(store, entry["id"], confirmed_by="keeper", now=NOW)
    assert cleared["status"] == "cleared"
    assert post.latest_gig(store, gig["id"])["status"] == "paid"


def test_dispute_freezes_settlement(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    dispute = work.dispute(store, gig["id"], "Ann H", "faucet still drips", now=NOW)
    assert dispute["status"] == "open"
    with pytest.raises(pay.SettlementRefused):
        pay.settle(
            store, gig["id"], 120, rail="cash", rail_reference="C-1", confirm=True
        )


def test_dispute_release_is_human_and_payable(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    dispute = work.dispute(store, gig["id"], "Ann H", "faucet still drips", now=NOW)
    resolved = work.resolve_dispute(
        store, dispute["id"], "release", decided_by="keeper", now=NOW
    )
    assert resolved["decided_by"] == "keeper"
    entry = pay.settle(
        store, gig["id"], 120, rail="cash", rail_reference="C-1", confirm=True, now=NOW
    )
    assert entry["keep_rate"] >= 0.90


def test_dispute_void_means_no_settlement(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    dispute = work.dispute(store, gig["id"], "Ann H", "never showed", now=NOW)
    work.resolve_dispute(store, dispute["id"], "void", decided_by="keeper", now=NOW)
    with pytest.raises(pay.SettlementRefused):
        pay.settle(
            store, gig["id"], 120, rail="cash", rail_reference="C-1", confirm=True
        )


def test_dispute_bad_outcome_rejected(tmp_path):
    store = _store(tmp_path)
    gig, _ = _completed_gig(store)
    dispute = work.dispute(store, gig["id"], "Ann H", "x", now=NOW)
    with pytest.raises(ValueError):
        work.resolve_dispute(store, dispute["id"], "refund", decided_by="keeper")
