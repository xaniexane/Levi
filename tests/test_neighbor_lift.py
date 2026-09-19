"""The Site Lift's un-hedged invariants — `tests/test_neighbor_lift.py`.

The four guarantees the gig platforms hedge, asserted against live
behavior:
1. the worker owns their reputation (portable passport, round-trips);
2. dispatch is explainable (open rules only, every offer logged);
3. relationships are direct (no contact-hiding anywhere);
4. workers keep 90%+ (every settlement, every amount, every band).

Hermetic: tmp_path stores, no network, no randomness.
"""

import json

import pytest

from levi.neighbor import lift, pay, policies as policies_mod, post, work
from levi.neighbor.store import Store

NOW = "2026-09-17T16:00:00+00:00"


def _store(tmp_path):
    return Store(tmp_path / "neighbor")


def _set_stage(store, stage):
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    cfg["gates"]["stage"] = stage
    path.write_text(json.dumps(cfg))


def _publish(store, **kw):
    gig = post.draft_gig(
        title=kw.get("title", "Fix leaky faucet"),
        category=kw.get("category", "plumbing"),
        description=kw.get("description", "drips all night"),
        requester="Ann H",
        requester_contact="ann@example.com",
        neighborhood_cell="springfield-test",
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
        credentials=kw.get("credentials"),
        now=NOW,
    )


def _run_to_done(store, gig, worker, amount, rating=5):
    lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=True, now=NOW)
    lift.accept_offer(store, gig["id"], worker["id"], now=NOW)
    work.check_in(store, gig["id"], worker["id"], now=NOW)
    work.check_out(store, gig["id"], worker["id"], now=NOW)
    work.sign_off(store, gig["id"], "Ann H", rating, final_amount=amount, now=NOW)


# -- 4. workers keep 90%+, every settlement ---------------------------------
@pytest.mark.parametrize(
    "amount",
    [5, 20, 50, 99.99, 100, 250, 499.99, 500, 1500, 1999.99, 2000, 7500, 25000],
)
def test_keep_floor_on_every_amount(tmp_path, amount):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    _run_to_done(store, gig, worker, amount)
    entry = pay.settle(
        store, gig["id"], amount, rail="cash", rail_reference="R", confirm=True, now=NOW
    )
    assert entry["keep_rate"] >= 0.90, f"floor broken at ${amount}"


@pytest.mark.parametrize("emergency,pro", [(True, False), (False, True), (True, True)])
def test_keep_floor_under_bands_and_tiers(tmp_path, emergency, pro):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    _run_to_done(store, gig, worker, 3000.0)
    entry = pay.settle(
        store,
        gig["id"],
        3000.0,
        rail="cash",
        rail_reference="R",
        confirm=True,
        emergency=emergency,
        pro_worker=pro,
        now=NOW,
    )
    assert entry["keep_rate"] >= 0.90


def test_fee_only_on_completed_and_paid(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    # in_progress, not signed off → refused
    lift.offer(store, gig["id"], worker["id"], operator="k", confirm=True, now=NOW)
    lift.accept_offer(store, gig["id"], worker["id"], now=NOW)
    work.check_in(store, gig["id"], worker["id"], now=NOW)
    with pytest.raises(pay.SettlementRefused):
        pay.settle(store, gig["id"], 120, rail="cash", rail_reference="R", confirm=True)


# -- 1. the worker owns their reputation ------------------------------------
def test_passport_round_trips(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    worker = _worker(store, credentials=[{"type": "EPA 608", "issuer": "EPA"}])
    gig = _publish(store)
    _run_to_done(store, gig, worker, 120.0)
    result = lift.export_passport(store, worker["id"], dest=tmp_path / "passport.json")
    imported = lift.import_passport(result["path"])
    assert imported["content_hash"] == result["passport"]["content_hash"]
    assert imported["worker"]["contact"] == "bob@example.com"  # their data, portable
    assert imported["credentials"][0]["type"] == "EPA 608"
    assert imported["proof_of_work"]["jobs_completed"] == 1
    assert imported["proof_of_work"]["average_rating"] == 5.0
    assert imported["proof_of_work"]["customer_sign_offs"] == 1


def test_tampered_passport_fails(tmp_path):
    store = _store(tmp_path)
    worker = _worker(store)
    result = lift.export_passport(store, worker["id"], dest=tmp_path / "passport.json")
    data = json.loads((tmp_path / "passport.json").read_text())
    data["proof_of_work"]["jobs_completed"] = 999
    (tmp_path / "passport.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        lift.import_passport(tmp_path / "passport.json")
    assert result["passport"]["proof_of_work"]["jobs_completed"] == 0


def test_passport_without_history_still_exports(tmp_path):
    store = _store(tmp_path)
    worker = _worker(store)
    result = lift.export_passport(store, worker["id"], dest=tmp_path / "p.json")
    assert result["passport"]["proof_of_work"]["jobs_completed"] == 0
    assert result["passport"]["proof_of_work"]["average_rating"] is None


# -- 2. dispatch is explainable --------------------------------------------
def test_every_candidate_carries_explanations(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    _worker(store, name="Bob", categories=["plumbing"])
    _worker(
        store,
        name="Cara",
        contact="cara@x",
        categories=["electrical"],
        cell="other-cell",
    )
    policies = policies_mod.load_policies(store)
    rule_ids = [r["id"] for r in policies["dispatch_rules"]]
    candidates = lift.explain_dispatch(store, gig["id"], limit=5)
    assert len(candidates) == 2
    assert candidates[0]["worker_name"] == "Bob"  # category + proximity win
    for cand in candidates:
        assert [b["rule"] for b in cand["breakdown"]] == rule_ids
        assert all(b["explanation"] for b in cand["breakdown"])
        assert cand["score"] <= cand["max_score"]


def test_hidden_rules_are_refused(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    path = store.base / "policies.json"
    cfg = json.loads(path.read_text())
    cfg["dispatch_rules"].append({"id": "secret_throttle", "weight": 999})
    path.write_text(json.dumps(cfg))
    gig = _publish(store)
    _worker(store)
    with pytest.raises(ValueError, match="not implemented"):
        lift.explain_dispatch(store, gig["id"])


def test_offer_logs_an_explainable_decision(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    receipt = lift.offer(
        store, gig["id"], worker["id"], operator="keeper", confirm=True, now=NOW
    )
    assert receipt["verified"] is True
    decisions = [d for d in store.read_all("decisions") if d.get("kind") == "offer"]
    assert len(decisions) == 1
    logged = decisions[0]
    assert logged["operator"] == "keeper"
    assert logged["breakdown"] and all("explanation" in b for b in logged["breakdown"])


def test_offer_without_permission_is_refused(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    with pytest.raises(PermissionError):
        lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=False)


# -- 3. relationships are direct -------------------------------------------
def test_no_contact_hiding_on_records(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    worker = _worker(store)
    lift.assert_no_contact_hiding(gig)  # requester contact plain
    lift.assert_no_contact_hiding(worker)  # worker contact plain
    assert gig["requester_contact"] == "ann@example.com"
    assert worker["contact"] == "bob@example.com"


def test_masked_contact_is_detected(tmp_path):
    with pytest.raises(ValueError, match="contact-hiding"):
        lift.assert_no_contact_hiding({"contact": "•••-•••-1234"})
    with pytest.raises(ValueError, match="contact-hiding"):
        lift.assert_no_contact_hiding({"masked_phone": "555-0100"})
    with pytest.raises(ValueError, match="contact-hiding"):
        lift.assert_no_contact_hiding({"worker": {"hidden_email": "x@y"}})


def test_both_sides_see_each_other(tmp_path):
    store = _store(tmp_path)
    gig = _publish(store)
    worker = _worker(store)
    candidates = lift.explain_dispatch(store, gig["id"])
    assert candidates[0]["worker_contact"] == "bob@example.com"  # requester sees worker
    assert (
        post.latest_gig(store, gig["id"])["requester_contact"] == "ann@example.com"
    )  # worker sees requester


# -- ledger: nothing deleted --------------------------------------------------
def test_streams_are_append_only_across_full_pipeline(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    before = {
        s: len(store.read_all(s))
        for s in ("gigs", "workers", "ledger", "settlements", "decisions")
    }
    _run_to_done(store, gig, worker, 120.0)
    pay.settle(
        store, gig["id"], 120, rail="cash", rail_reference="R", confirm=True, now=NOW
    )
    after = {s: len(store.read_all(s)) for s in before}
    # nothing is ever deleted: every stream only grows…
    assert all(after[s] >= before[s] for s in before)
    # …and the pipeline's streams all grew.
    assert all(
        after[s] > before[s] for s in ("gigs", "ledger", "settlements", "decisions")
    )
    report = store.verify_integrity()
    assert report["ok"] is True
    for stream, info in report["streams"].items():
        assert info["append_only_ok"] is True


# -- gates ----------------------------------------------------------------------
def test_dispatch_refused_before_active_dispatch(tmp_path):
    store = _store(tmp_path)  # default stage: waitlist_only
    gig, worker = _publish(store), _worker(store)
    with pytest.raises(PermissionError, match="gate refused"):
        lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=True)


def test_gate_override_is_logged_and_named(tmp_path):
    store = _store(tmp_path)
    gig, worker = _publish(store), _worker(store)
    receipt = lift.offer(
        store,
        gig["id"],
        worker["id"],
        operator="keeper",
        confirm=True,
        override_gate=True,
        now=NOW,
    )
    assert receipt["gate"]["override"] is True
    overrides = [
        d for d in store.read_all("decisions") if d.get("kind") == "gate_override"
    ]
    assert len(overrides) == 1
    assert overrides[0]["operator"] == "keeper"


def test_soft_launch_cap_enforced(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "soft_launch")
    path = store.base / "policies.json"
    cfg = json.loads(path.read_text())
    cfg["gates"]["soft_launch"]["job_cap"] = 1
    path.write_text(json.dumps(cfg))
    _publish(store)
    gig2, worker = _publish(store, title="second"), _worker(store)
    # first offer consumes the single soft-launch slot…
    gigs = [g for g in store.read_all("gigs")]
    lift.offer(store, gigs[0]["id"], worker["id"], operator="k", confirm=True, now=NOW)
    with pytest.raises(PermissionError, match="gate refused"):
        lift.offer(store, gig2["id"], worker["id"], operator="k", confirm=True)


# -- platform integrity ------------------------------------------------------------
def test_integrity_report_green_on_healthy_state(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "active_dispatch")
    gig, worker = _publish(store), _worker(store)
    _run_to_done(store, gig, worker, 120.0)
    pay.settle(
        store, gig["id"], 120, rail="cash", rail_reference="R", confirm=True, now=NOW
    )
    report = lift.platform_integrity_report(store)
    assert report["ok"] is True
    assert set(report["checks"]) == {
        "keep_floor",
        "no_contact_hiding",
        "dispatch_explainable",
        "ledger_append_only",
    }


def test_integrity_report_catches_floor_violation(tmp_path):
    store = _store(tmp_path)
    # hand-write a hostile settlement straight into the stream — the
    # detector must catch what the API would never produce.
    store.append(
        "settlements",
        {
            "id": "settlement-0001",
            "gig_id": "gig-0001",
            "worker_id": "worker-0001",
            "gross": 100.0,
            "fee": 40.0,
            "worker_keep": 60.0,
            "keep_rate": 0.60,
            "floor": 0.90,
            "rail": "cash",
            "rail_reference": "X",
            "status": "recorded",
        },
        now=NOW,
    )
    report = lift.platform_integrity_report(store)
    assert report["ok"] is False
    assert report["checks"]["keep_floor"]["violations"] == ["settlement-0001"]
