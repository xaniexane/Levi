"""Mesh ledger + trust tests: credit math, silent drift flags, gating."""

from levi.catalogue.wallet import AD_GRANT_CREDITS, CreditWallet, WALLET_CAP
from levi.mesh.ledger import ContributionLedger, MESH_CREDITS_PER_UNIT
from levi.mesh.trust import TrustMonitor


def test_ledger_contributed_received_sums(tmp_path):
    ledger = ContributionLedger(path=tmp_path / "ledger.jsonl")
    ledger.record("n1", "contributed", 3)
    ledger.record("n1", "contributed", 2)
    ledger.record("n1", "received", 4)
    ledger.record("n2", "contributed", 1)
    assert ledger.contributed("n1") == 5
    assert ledger.received("n1") == 4
    assert ledger.contributed("n2") == 1
    assert ledger.contributed("nobody") == 0
    # append-only truth survives reload
    again = ContributionLedger(path=tmp_path / "ledger.jsonl")
    assert again.contributed("n1") == 5


def test_settle_converts_work_to_wallet_credits(tmp_path):
    ledger = ContributionLedger(path=tmp_path / "ledger.jsonl")
    wallet = CreditWallet()
    for _ in range(4):
        ledger.record("worker-1", "contributed", 1)
    out = ledger.settle_to_wallet(wallet, "user-1", "worker-1")
    assert out["units_settled"] == 4
    assert wallet.balance("user-1") == 4 * MESH_CREDITS_PER_UNIT
    # second settle pays nothing new — no double-spend
    out2 = ledger.settle_to_wallet(wallet, "user-1", "worker-1")
    assert out2["units_settled"] == 0
    assert wallet.balance("user-1") == 4 * MESH_CREDITS_PER_UNIT


def test_settle_respects_wallet_cap(tmp_path):
    ledger = ContributionLedger(path=tmp_path / "ledger.jsonl")
    wallet = CreditWallet()
    ledger.record("whale", "contributed", 1000)  # far past the cap
    out = ledger.settle_to_wallet(wallet, "user-9", "whale")
    assert out["granted"] <= WALLET_CAP
    assert wallet.balance("user-9") == WALLET_CAP
    assert out["capped"] is True


def test_credit_doctrine_sane_vs_ad_grants():
    # Work outranks attention: a chunk pays less than an ad view but
    # stacks through real contribution; both live under the same cap.
    assert 0 < MESH_CREDITS_PER_UNIT < AD_GRANT_CREDITS


def test_trust_score_only_moves_down():
    t = TrustMonitor()
    assert t.score("n1") == 1.0
    t.record_success("n1")
    assert t.score("n1") == 1.0
    t.record_failure("n1")
    assert t.score("n1") == 0.7
    t.record_mismatch("n1")
    assert t.score("n1") == 0.2
    t.record_misreport("n1")
    assert t.score("n1") == 0.0  # floored, never negative


def test_drift_alarm_degraded_is_silent_and_founder_gated():
    t = TrustMonitor()
    for _ in range(4):
        t.record_failure("flaky")
    t.record_success("flaky")
    kinds = [f["kind"] for f in t.flags_for_founder({"tier": "founder"})]
    assert "degraded" in kinds
    # silent: no broadcast path exists; non-founder sees nothing
    assert t.flags_for_founder({"tier": "user"}) == []
    assert t.flags_for_founder(None) == []
    assert t.flags_for_founder() == []
    # and the flagged peer was never told: no notify method on the monitor
    assert not hasattr(t, "notify_peer")


def test_drift_alarm_integrity_on_disagreement():
    t = TrustMonitor()
    t.record_success("odd")
    t.record_mismatch("odd")
    t.record_mismatch("odd")
    kinds = [f["kind"] for f in t.flags_for_founder({"tier": "founder"})]
    assert "integrity" in kinds


def test_drift_alarm_too_perfect():
    t = TrustMonitor()
    # fleet baseline: normal nodes with human-scale latency
    for i in range(3):
        for _ in range(10):
            t.record_success(f"normal-{i}", latency_s=0.5)
    # suspect: flawless and impossibly fast — drift toward implausible
    for _ in range(20):
        t.record_success("suspect", latency_s=0.001)
    kinds = {f["node_id"]: f["kind"] for f in t.flags_for_founder({"tier": "founder"})}
    assert kinds.get("suspect") == "anomaly"
    assert "normal-0" not in kinds


def test_no_flag_without_enough_evidence():
    t = TrustMonitor()
    t.record_failure("newbie")  # 1 observation: not enough to judge
    assert t.flags_for_founder({"tier": "founder"}) == []
