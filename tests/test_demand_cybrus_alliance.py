"""Law/guard/proof tests for the DemandPulse <-> Cybrus alliance (DemandPulse side).

Alliance rules under test:
  A1 threats are not demand — a threat match never becomes a signal/card
  A2 minimal PII — one sentence, truncated, never full bodies
  A3 never invents — silence when nothing matches
  A4 never acts — no gateway/enforce/money imports anywhere in the module
  A5 the guard is the swarm's wire — this side only exposes seams

Hermetic: HOME/LEVI_HOME redirected; the Cybrus audit engine is faked via
monkeypatch — no real Cybrus writes, no real home writes.
"""

import pytest

from levi.demand import cybrus_alliance as alliance
from levi.demand import watcher as wmod
from levi.demand.pulse import DemandPulse


@pytest.fixture
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    import levi.demand.pulse as _pulse

    monkeypatch.setattr(_pulse, "DEFAULT", tmp_path / "demand_pulse.json")
    return tmp_path


def _dp(tmp_path):
    return DemandPulse(path=tmp_path / "dp.json")


def _st(tmp_path):
    return wmod.WatcherState.load(path=tmp_path / "wstate.json")


class _FakeAudit:
    def __init__(self):
        self.records = []

    def append(self, event, actor, details=None):
        rec = {"event": event, "actor": actor, "details": dict(details or {})}
        self.records.append(rec)
        return rec


# ------------------------------------------------------- A3/A2: extraction


def test_extract_threats_finds_phishing_sentence():
    out = alliance.extract_threats(
        "Hi team. Your account has been suspended, verify your account "
        "immediately to avoid lockout. Thanks."
    )
    assert len(out) == 1
    sentence, markers = out[0]
    assert "verify your account" in markers
    assert len(sentence) <= alliance.INTEL_TEXT_MAX


def test_extract_threats_silent_on_benign_text():
    marketing = (
        "Your receipt for order 12345 is attached. "
        "Your subscription renews on Friday. Thanks for being a customer!"
    )
    assert alliance.extract_threats(marketing) == []
    assert alliance.extract_threats("") == []


def test_extract_threats_truncates_long_sentence():
    long = "Please verify your account now " + ("x" * 500) + "."
    out = alliance.extract_threats(long)
    assert len(out) == 1
    assert len(out[0][0]) <= alliance.INTEL_TEXT_MAX


# ------------------------------------------------- A1: threats are not demand


def test_threats_never_become_signals(herm, monkeypatch):
    shared = []

    def fake_share(items):
        shared.extend(items)
        return {"items": len(items), "threats_found": 1, "shared": 1,
                "status": "ok"}

    monkeypatch.setattr(alliance, "share_intel", fake_share)
    dp = _dp(herm)
    state = _st(herm)
    receipt = wmod.ingest_items(
        dp,
        state,
        "text",
        [{"id": "m1",
          "text": "URGENT: your account has been suspended, "
                  "verify your account immediately via wire transfer."}],
    )
    assert receipt["signals"] == 0
    assert receipt["candidates"] == 0
    assert len(dp.signals) == 0
    assert len(shared) == 1
    assert receipt["threat_intel"]["shared"] == 1


def test_share_intel_labels_hypothesis():
    fake = _FakeAudit()
    receipt = alliance.share_intel(
        [{"id": "m1", "channel": "email",
          "text": "You have won the lottery winner prize, claim your prize now."}],
        audit=fake,
    )
    assert receipt["status"] == "ok"
    assert receipt["shared"] == 1
    rec = fake.records[0]
    assert rec["event"] == "demandpulse.threat_intel"
    assert rec["actor"] == "demandpulse"
    assert rec["details"]["kind"] == "HYPOTHESIS"
    assert rec["details"]["channel"] == "email"
    assert "claim your prize" in rec["details"]["markers"]


def test_share_intel_minimal_pii():
    fake = _FakeAudit()
    long_body = "Hello. " + "Please send bitcoin to unlock. " + ("y" * 600)
    alliance.share_intel(
        [{"id": "m1", "channel": "text", "text": long_body}], audit=fake
    )
    assert len(fake.records[0]["details"]["text"]) <= alliance.INTEL_TEXT_MAX


def test_share_intel_cybrus_unavailable_is_honest(monkeypatch):
    def boom():
        raise RuntimeError("no cybrus here")

    monkeypatch.setattr(alliance, "_audit_engine", boom)
    receipt = alliance.share_intel(
        [{"id": "m1", "channel": "email", "text": "phishing attempt, verify your account."}]
    )
    assert receipt["status"] == "cybrus_unavailable"
    assert receipt["shared"] == 0


# ------------------------------------------------- A4: never acts


def test_alliance_never_imports_enforcement():
    src = open(alliance.__file__).read()
    for mod in ("levi.cybrus.gateway", "levi.cybrus.enforce", "levi.cybrus.money",
                "levi.cybrus.approval", "levi.cybrus.policy", "levi.cybrus.router"):
        assert mod not in src, f"alliance must not touch {mod}"
    names = " ".join(dir(alliance)).lower()
    assert "gateway" not in names
    assert "enforce" not in names


def test_watcher_law_l8_present():
    assert any(law.startswith("L8") for law in wmod.LAWS)
    assert "cybrus" in " ".join(wmod.LAWS).lower()


def test_watcher_still_never_touches_alerts():
    src = open(wmod.__file__).read()
    assert "levi.demand.alerts" not in src
    assert "import alerts" not in src


# ------------------------------------------------- audit of mutations


def test_audit_mutation_false_when_cybrus_down(monkeypatch):
    def boom():
        raise RuntimeError("down")

    monkeypatch.setattr(alliance, "_audit_engine", boom)
    assert alliance.audit_mutation("demandpulse.opportunity_scored", {}) is False


def test_audit_mutation_true_when_cybrus_up(monkeypatch):
    fake = _FakeAudit()
    monkeypatch.setattr(alliance, "_audit_engine", lambda: fake)
    assert alliance.audit_mutation("demandpulse.opportunity_scored",
                                   {"title": "t"}) is True
    assert fake.records[0]["event"] == "demandpulse.opportunity_scored"
    assert fake.records[0]["actor"] == "demandpulse"


def test_score_opportunity_audits(herm, monkeypatch):
    calls = []
    monkeypatch.setattr(
        alliance, "audit_mutation",
        lambda event, details=None: calls.append((event, details)) or True,
    )
    dp = _dp(herm)
    sig = dp.scan_seed("I need shift help", source="text")
    dp.score_opportunity(sig.id, "Shift planner")
    assert calls and calls[0][0] == "demandpulse.opportunity_scored"
    assert calls[0][1]["opportunity_id"]


def test_score_five_factor_audits(herm, monkeypatch):
    calls = []
    monkeypatch.setattr(
        alliance, "audit_mutation",
        lambda event, details=None: calls.append((event, details)) or True,
    )
    dp = _dp(herm)
    sig = dp.scan_seed("I need shift help", source="text")
    factors = {
        "demand": (80, "three separate asks this week"),
        "market_size": (60, "local teams"),
        "competition_gap": (70, "no local tool"),
        "trend_velocity": (50, "steady"),
        "entry_feasibility": (90, "weekend build"),
    }
    dp.score_five_factor(sig.id, "Shift planner", factors)
    assert calls and calls[0][0] == "demandpulse.card_scored"


# ------------------------------------------------- A5: seams, not guards


def test_guard_seams_lists_store_watcher_intel_alerts(herm):
    seams = alliance.guard_seams()
    names = {s["name"] for s in seams}
    assert {"signal_store", "watcher_state", "intel_feed", "alert_path"} <= names
    for s in seams:
        assert s["path"] and s["kind"]


def test_integrity_missing_files_reported_not_raised(herm):
    rep = alliance.integrity()
    assert rep["signal_store"]["ok"] is False
    assert rep["signal_store"]["detail"] == "missing"
    assert rep["watcher_state"]["ok"] is False


def test_integrity_ok_on_real_files(herm):
    import json

    import levi.demand.pulse as _pulse

    # Write valid files exactly where the seams resolve in hermetic env.
    store = _pulse.DEFAULT  # monkeypatched to tmp_path/demand_pulse.json
    store.write_text(
        json.dumps({"signals": [], "opportunities": [], "score_cards": []}),
        encoding="utf-8",
    )
    wpath = wmod.state_path()  # LEVI_HOME/demand_watcher.json in hermetic env
    wpath.parent.mkdir(parents=True, exist_ok=True)
    wpath.write_text(
        json.dumps({"channels": {"email": {"last_poll": None, "seen_ids": []}}}),
        encoding="utf-8",
    )
    rep = alliance.integrity()
    assert rep["signal_store"] == {"ok": True, "detail": "ok"}
    assert rep["watcher_state"] == {"ok": True, "detail": "ok"}


def test_integrity_flags_corrupt_store(herm):
    import levi.demand.pulse as _pulse

    _pulse.DEFAULT.write_text("{not json", encoding="utf-8")
    rep = alliance.integrity()
    assert rep["signal_store"]["ok"] is False
    assert "unreadable" in rep["signal_store"]["detail"]
