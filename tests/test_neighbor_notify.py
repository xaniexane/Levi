"""Tests for the NeighborOS notifier (notify.py, laws N1–N6), the admin
push-path drain, and the DemandPulse alert push wiring.

Hermetic: stores on tmp_path, webhook egress injected (no network).
"""

from types import SimpleNamespace

import pytest

from levi.demand import alerts as alertmod
from levi.neighbor import admin, notify, policies as policies_mod
from levi.neighbor.notify import Notifier, summarize
from levi.neighbor.store import Store

NOW = "2026-09-23T09:00:00+00:00"
CANARY = "https://canary-secret-9f3k.example/exec"


def _store(tmp_path):
    return Store(tmp_path / "neighbor")


def _notifier(tmp_path, **cfg):
    base = {"backends": ["app_push", "file", "webhook", "whatsapp"]}
    base.update(cfg)
    http_post = base.pop("http_post", None)
    return Notifier(config=base, state_dir=tmp_path / "nstate", http_post=http_post)


def _nudge(nid, kind="recruit", message="ping"):
    return {
        "id": nid,
        "title": f"t-{nid}",
        "body": message,
        "kind": kind,
        "cell": None,
    }


# ---- laws N5/N6: honest statuses -------------------------------------------
def test_app_push_never_reports_delivered(tmp_path):
    n = _notifier(tmp_path)
    assert n.send(_nudge("a1"))["app_push"] == "queued_for_app_push"
    outbox = list((tmp_path / "nstate").glob("notify_app_push.jsonl"))
    assert outbox and '"queued_for_app_push"' in outbox[0].read_text()
    assert '"delivered"' not in outbox[0].read_text()


def test_whatsapp_stays_gated(tmp_path):
    n = _notifier(tmp_path)
    st = n.status()["whatsapp"]
    assert st["status"] == "needs_whatsapp_chat_setup"
    assert "side chat" in st["setup"]
    assert n.send(_nudge("w1"), backends=["whatsapp"]) == {
        "whatsapp": "needs_whatsapp_chat_setup"
    }


def test_unknown_backend_rejected(tmp_path):
    with pytest.raises(ValueError):
        _notifier(tmp_path, backends=["smoke_signal"])


# ---- law N2: dedupe ----------------------------------------------------------
def test_never_double_sends(tmp_path):
    n = _notifier(tmp_path)
    first = n.send(_nudge("d1"), backends=["app_push", "file"])
    assert first == {"app_push": "queued_for_app_push", "file": "delivered"}
    second = n.send(_nudge("d1"), backends=["app_push", "file"])
    assert second == {"app_push": "already_sent", "file": "already_sent"}
    dedupe = tmp_path / "nstate" / "notify_sent.jsonl"
    lines = [ln for ln in dedupe.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2  # one record per (backend, id)


# ---- law N4: bounded webhook egress ------------------------------------------
def test_webhook_no_targets_configured(tmp_path):
    n = _notifier(tmp_path, webhook_urls=[])
    assert n.send(_nudge("h1"), backends=["webhook"]) == {
        "webhook": "no_targets_configured"
    }
    assert n.status()["webhook"]["status"] == "no_targets_configured"


def test_webhook_retries_then_succeeds(tmp_path):
    calls = []

    def fake_post(url, payload, timeout):
        calls.append(url)
        return (False, None, "boom") if len(calls) < 3 else (True, 200, None)

    n = _notifier(
        tmp_path, webhook_urls=[CANARY], max_retries=2, http_post=fake_post
    )
    assert n.send(_nudge("h2"), backends=["webhook"]) == {"webhook": "delivered"}
    assert len(calls) == 3  # 1 + max_retries


def test_webhook_all_fail_bounded_and_honest(tmp_path):
    calls = []

    def fake_post(url, payload, timeout):
        calls.append(url)
        return (False, 500, "server exploded")

    n = _notifier(
        tmp_path, webhook_urls=[CANARY], max_retries=2, http_post=fake_post
    )
    statuses = n.send(_nudge("h3"), backends=["webhook"])
    assert statuses["webhook"].startswith("failed")
    assert len(calls) == 3  # bounded: 1 + max_retries, not infinite
    assert CANARY not in statuses["webhook"]  # N3: URL never in status


def test_no_secrets_in_state_files(tmp_path):
    def fake_post(url, payload, timeout):
        return (False, None, f"refused by {url} loudly")

    n = _notifier(tmp_path, webhook_urls=[CANARY], http_post=fake_post)
    n.send(_nudge("s1"))  # all backends incl. failing webhook
    state = tmp_path / "nstate"
    for name in ("notify_sent.jsonl", "notify_app_push.jsonl", "notify_file_outbox.jsonl"):
        p = state / name
        if p.exists():
            assert CANARY not in p.read_text(), name  # N3


def test_summarize_prefers_best_honest(tmp_path):
    assert summarize({"a": "failed", "b": "queued_for_app_push"}) == "queued_for_app_push"
    assert summarize({"a": "failed"}) == "failed"
    assert summarize({"a": "failed: x", "b": "failed: y"}) == "failed"


# ---- admin drain (L3: push additive, pull intact) -----------------------------
def test_drain_marks_sent_and_pull_still_works(tmp_path):
    store = _store(tmp_path)
    n1 = admin.queue_nudge(store, "recruit", "two workers short", now=NOW)
    n2 = admin.queue_nudge(store, "recruit", "cell is hot", now=NOW)
    n = _notifier(tmp_path / "nstate2", backends=["app_push", "file"])
    receipt = admin.drain_nudges(store, n, now=NOW)
    assert receipt["drained"] == 2
    assert sorted(receipt["sent"]) == sorted([n1["id"], n2["id"]])
    assert receipt["retried"] == []
    # marked sent on the stream with honest per-backend statuses
    latest = {r["id"]: r for r in store.read_all("nudges")}
    assert latest[n1["id"]]["status"] == "sent"
    assert latest[n1["id"]]["via"]["app_push"] == "queued_for_app_push"
    # second drain finds nothing; pull of sent items returns nothing queued
    assert admin.drain_nudges(store, n)["drained"] == 0
    assert admin.pull_nudges(store) == []


def test_drain_retries_transient_failure(tmp_path):
    store = _store(tmp_path)
    n1 = admin.queue_nudge(store, "recruit", "retry me", now=NOW)
    state = {"fail": True}

    def fake_post(url, payload, timeout):
        return (False, None, "down") if state["fail"] else (True, 200, None)

    n = Notifier(
        config={"backends": ["webhook"], "webhook_urls": [CANARY], "max_retries": 0},
        state_dir=tmp_path / "ns3",
        http_post=fake_post,
    )
    r1 = admin.drain_nudges(store, n, now=NOW)
    assert r1["sent"] == [] and r1["retried"] == [n1["id"]]
    latest = {r["id"]: r for r in store.read_all("nudges")}
    assert latest[n1["id"]]["status"] == "queued"  # stays queued
    state["fail"] = False
    r2 = admin.drain_nudges(store, n, now=NOW)
    assert r2["sent"] == [n1["id"]]  # retried, never double-sent
    assert r2["statuses"]["webhook"] == ["delivered"]


# ---- DemandPulse push wiring --------------------------------------------------
def _event(alert_id="al-x"):
    return alertmod.AlertEvent(
        alert_id=alert_id,
        alert_name="probe",
        kind="threshold",
        title="crossed",
        lines=["worth 0.9"],
        dedup_key="k1",
    )


def test_push_without_notifier_stays_not_configured(tmp_path):
    eng = alertmod.AlertEngine(path=tmp_path / "alerts.json")
    status = eng.deliver(
        _event(), channels=("push", "email"), outbox=tmp_path / "o.jsonl"
    )
    assert status == {"push": "not_configured", "email": "not_configured"}


def test_push_with_notifier_reaches_app_push(tmp_path):
    eng = alertmod.AlertEngine(path=tmp_path / "alerts.json")
    n = _notifier(tmp_path, backends=["app_push", "file"])
    status = eng.deliver(
        _event(), channels=("push", "email"), outbox=tmp_path / "o.jsonl",
        notifier=n,
    )
    assert status["push"] == "queued_for_app_push"
    assert status["email"] == "not_configured"  # email untouched: no provider


def test_run_threads_notifier(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    eng = alertmod.AlertEngine(path=tmp_path / "alerts.json")
    alert = eng.create("threshold", "hot opp", channels=("push", "file"))
    card = SimpleNamespace(
        alert=True, composite=90.0, opportunity_id="o1", title="Big gig", tier="A"
    )
    dp = SimpleNamespace(score_cards=[card], opportunities=[], signals=[])
    n = _notifier(tmp_path, backends=["app_push"])
    noon = datetime(2026, 9, 23, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    receipt = eng.run(dp, now=noon, outbox=tmp_path / "o.jsonl", notifier=n)
    assert receipt["fired"] == 1
    assert receipt["channel_status"]["push"] == ["queued_for_app_push"]
    # dedupe: second run fires nothing
    assert eng.run(dp, now=noon, outbox=tmp_path / "o.jsonl", notifier=n)["fired"] == 0


# ---- check_laws -----------------------------------------------------------------
def test_check_laws_green(tmp_path):
    store = _store(tmp_path)
    policies_mod.load_policies(store)  # seeds package defaults incl. notify
    n = _notifier(store.base, backends=["app_push", "file", "whatsapp"])
    n.send(_nudge("c1"))
    n.send(_nudge("c2"), backends=["whatsapp"])
    res = notify.check_laws(store)
    assert res["ok"], res["checks"]
