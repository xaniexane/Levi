"""Hermetic tests for the usage governor.

No network, no real providers, no user HOME writes. Token counts are
simulated through a fake provider; time is an injected clock.
"""

import json

import pytest

from levi.agent.providers import ChatProvider, ChatResponse
from levi.governor import (
    BudgetEnforcer,
    BurstPass,
    CooldownManager,
    GovernedProvider,
    Meter,
    PassWallet,
    SpikeDetector,
    fingerprint_messages,
    governed_call,
    summarize,
    top_contributors,
)
from levi.governor import __main__ as gov_cli


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def clock():
    now = [10_000.0]

    def _clock():
        return now[0]

    _clock.advance = lambda s: now.__setitem__(0, now[0] + s)
    return _clock


class FakeProvider(ChatProvider):
    name = "fake-test"

    def __init__(self, prompt_tokens=100, completion_tokens=50, fail=False):
        self.pt = prompt_tokens
        self.ct = completion_tokens
        self.fail = fail
        self.calls = 0

    def is_available(self):
        return True

    def chat(self, messages, tools):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return ChatResponse(
            text="ok",
            model="fake-1",
            provider="fake-test",
            prompt_tokens=self.pt,
            completion_tokens=self.ct,
        )


def _msgs():
    return [{"role": "user", "content": "hello"}]


# ---------------------------------------------------------------- meter
def test_record_attribution(home, clock):
    m = Meter(clock=clock)
    m.record(
        provider="openai", model="gpt-x", task_id="t1", agent_id="a1",
        tool_name="web_search", prompt_fingerprint="abc",
        prompt_tokens=10, completion_tokens=20,
    )
    recs = m.query(task_id="t1")
    assert len(recs) == 1
    r = recs[0]
    assert (r.provider, r.model, r.agent_id, r.tool_name) == (
        "openai", "gpt-x", "a1", "web_search")
    assert r.total == 30
    assert m.query(tool_name="nope") == []
    assert m.query(agent_id="a1", tool_name="web_search") != []


def test_negative_tokens_rejected(home, clock):
    m = Meter(clock=clock)
    with pytest.raises(ValueError):
        m.record(prompt_tokens=-1)


def test_fingerprint_stable_and_sensitive():
    a = fingerprint_messages(_msgs())
    b = fingerprint_messages([{"role": "user", "content": "hello"}])
    c = fingerprint_messages([{"role": "user", "content": "goodbye"}])
    assert a == b and len(a) == 16
    assert a != c


def test_ledger_persists_across_instances(home, clock):
    Meter(clock=clock).record(provider="p", prompt_tokens=5, completion_tokens=5)
    recs = Meter(clock=clock).query()
    assert len(recs) == 1 and recs[0].total == 10


def test_corrupt_ledger_line_skipped(home, clock):
    m = Meter(clock=clock)
    m.record(prompt_tokens=1, completion_tokens=1)
    with open(m.ledger_path, "a", encoding="utf-8") as fh:
        fh.write("not json{{{\n")
    assert len(m.query()) == 1


# ---------------------------------------------------------------- spikes
def _seed(det, meter, ts, n, tokens, **kw):
    for _ in range(n):
        meter.record(prompt_tokens=tokens, completion_tokens=0, ts=ts, **kw)
        det.observe(meter.query()[-1])


def test_spike_on_multiplier(home, clock):
    det = SpikeDetector(window_seconds=600, multiplier=4.0, clock=clock)
    m = Meter(clock=clock)
    now = clock()
    _seed(det, m, now - 900, 10, 100, tool_name="web_search")   # baseline 1k
    alerts = []
    for _ in range(10):
        m.record(prompt_tokens=1000, completion_tokens=0,
                 ts=now - 100, tool_name="web_search")
        alerts.extend(det.observe(m.query()[-1]))
    keys = {a.key for a in alerts}
    assert "tool:web_search" in keys
    assert any("× baseline" in a.reason for a in alerts)


def test_no_spike_below_multiplier(home, clock):
    det = SpikeDetector(window_seconds=600, multiplier=4.0, clock=clock)
    m = Meter(clock=clock)
    now = clock()
    _seed(det, m, now - 900, 20, 100, tool_name="t")  # baseline 2k
    alerts = []
    for _ in range(5):
        m.record(prompt_tokens=100, completion_tokens=0, ts=now - 100, tool_name="t")
        alerts.extend(det.observe(m.query()[-1]))
    assert alerts == []


def test_absolute_cap_fires(home, clock):
    det = SpikeDetector(window_seconds=600, absolute_cap=1000, clock=clock)
    m = Meter(clock=clock)
    m.record(prompt_tokens=2000, completion_tokens=0, ts=clock())
    alerts = det.observe(m.query()[-1])
    assert any("absolute cap" in a.reason for a in alerts)


def test_cold_start_only_cap_can_fire(home, clock):
    det = SpikeDetector(window_seconds=600, absolute_cap=10**9, clock=clock)
    m = Meter(clock=clock)
    m.record(prompt_tokens=5000, completion_tokens=0, ts=clock())
    assert det.observe(m.query()[-1]) == []


# ---------------------------------------------------------------- cooldown
def test_breach_opens_and_refuses_with_reason(home, clock):
    cd = CooldownManager(clock=clock)
    delay = cd.breach("provider:x", "test spike")
    assert delay == 60
    grant = cd.acquire("provider:x")
    assert not grant.allowed and "cooling down" in grant.reason
    assert "test spike" in grant.reason
    assert cd.acquire("provider:y").allowed  # other scopes unaffected


def test_half_open_probe_then_close(home, clock):
    cd = CooldownManager(clock=clock)
    cd.breach("s", "r")
    clock.advance(61)
    grant = cd.acquire("s")
    assert grant.allowed and grant.probe
    # second acquire while probe in flight: refused
    assert not cd.acquire("s").allowed
    cd.probe_success("s")
    assert cd.acquire("s").allowed and not cd.acquire("s").probe


def test_probe_failure_doubles_backoff(home, clock):
    cd = CooldownManager(base_seconds=60, clock=clock)
    cd.breach("s", "r")
    clock.advance(61)
    assert cd.acquire("s").probe
    delay = cd.probe_failure("s", "still spiking")
    assert delay == 120
    grant = cd.acquire("s")
    assert not grant.allowed and "retry in 120s" in grant.reason


def test_cooldown_persists_across_restart(home, clock):
    CooldownManager(clock=clock).breach("provider:x", "r")
    cd2 = CooldownManager(clock=clock)
    assert not cd2.acquire("provider:x").allowed


def test_corrupt_state_denies_closed(home, clock):
    cd = CooldownManager(clock=clock)
    cd._state_file.parent.mkdir(parents=True, exist_ok=True)
    cd._state_file.write_text("garbage{{{", encoding="utf-8")
    cd2 = CooldownManager(clock=clock)
    grant = cd2.acquire("anything")
    assert not grant.allowed and "unreadable" in grant.reason
    cd2.reset("anything")  # operator reset clears it
    assert CooldownManager(clock=clock).acquire("anything").allowed


# ---------------------------------------------------------------- budgets
def test_session_budget_refuses(home, clock):
    m = Meter(clock=clock)
    b = BudgetEnforcer(m, config={"session_tokens": 100})
    b.note_spend(60)
    assert b.authorize(30) == (True, "within budget")
    b.note_spend(50)
    ok, reason = b.authorize()
    assert not ok and "session budget exhausted" in reason


def test_day_budget_refuses(home, clock):
    import time as _time

    m = Meter(clock=clock)
    b = BudgetEnforcer(m, config={"day_tokens": 100})
    m.record(prompt_tokens=90, completion_tokens=20, ts=_time.time())
    ok, reason = b.authorize()
    assert not ok and "daily budget exhausted" in reason


def test_budget_config_persists(home, clock):
    m = Meter(clock=clock)
    BudgetEnforcer(m).set_budget("session_tokens", 12345)
    b2 = BudgetEnforcer(Meter(clock=clock))
    assert b2.remaining()["session_tokens"]["budget"] == 12345
    with pytest.raises(ValueError):
        b2.set_budget("nope", 10)


# ---------------------------------------------------------------- governed wrapper
def test_governed_meters_call_with_attribution(home, clock):
    inner = FakeProvider()
    gov = GovernedProvider(inner, task_id="t9", agent_id="a9",
                           tool_name="search", clock=clock)
    resp = gov.chat(_msgs(), [])
    assert resp.error is None and inner.calls == 1
    recs = Meter(clock=clock).query()
    assert len(recs) == 1
    r = recs[0]
    assert (r.task_id, r.agent_id, r.tool_name, r.provider) == (
        "t9", "a9", "search", "fake-test")
    assert r.total == 150 and len(r.prompt_fingerprint) == 16
    assert gov.name == "fake-test"  # name delegates to inner provider


def test_governed_refuses_during_cooldown_with_reason(home, clock):
    inner = FakeProvider()
    cd = CooldownManager(clock=clock)
    gov = GovernedProvider(inner, clock=clock, cooldowns=cd)
    cd.breach(gov.scope, "simulated spike")
    resp = gov.chat(_msgs(), [])
    assert inner.calls == 0  # never reached the provider
    assert resp.error and "cool-down" in resp.error
    assert "simulated spike" in resp.error


def test_governed_spike_triggers_cooldown(home, clock):
    inner = FakeProvider(prompt_tokens=5000, completion_tokens=0)
    det = SpikeDetector(window_seconds=600, absolute_cap=1000, clock=clock)
    gov = GovernedProvider(inner, clock=clock, detector=det)
    resp = gov.chat(_msgs(), [])
    assert resp.error is None
    assert hasattr(resp, "governor_alerts")  # no silent pass
    resp2 = gov.chat(_msgs(), [])
    assert resp2.error and "cool-down" in resp2.error
    assert inner.calls == 1


def test_governed_budget_refusal_mentions_budget(home, clock):
    inner = FakeProvider()
    meter = Meter(clock=clock)
    b = BudgetEnforcer(meter, config={"session_tokens": 10})
    b.note_spend(11)  # budget already exceeded: the next call must not run
    gov = GovernedProvider(inner, clock=clock, meter=meter, budgets=b)
    resp = gov.chat(_msgs(), [])
    assert inner.calls == 0
    assert resp.error and "budget" in resp.error


def test_governed_provider_exception_metered_not_silent(home, clock):
    inner = FakeProvider(fail=True)
    gov = GovernedProvider(inner, clock=clock)
    resp = gov.chat(_msgs(), [])
    assert resp.error and "RuntimeError" in resp.error
    recs = Meter(clock=clock).query()
    assert len(recs) == 1 and recs[0].error and "boom" in recs[0].error


def test_governed_call_one_shot(home, clock):
    resp = governed_call(FakeProvider(), _msgs(), [], task_id="t1", clock=clock)
    assert resp.error is None
    assert Meter(clock=clock).query(task_id="t1")


# ---------------------------------------------------------------- diagnose
def test_top_contributors_shares(home, clock):
    m = Meter(clock=clock)
    now = clock()
    for _ in range(3):
        m.record(prompt_tokens=300, completion_tokens=0, ts=now - 10, tool_name="big")
    for _ in range(2):
        m.record(prompt_tokens=50, completion_tokens=0, ts=now - 10, tool_name="small")
    rows = top_contributors(m, window_seconds=3600, group_by="tool", clock=clock)
    assert rows[0]["key"] == "big"
    assert rows[0]["share"] == pytest.approx(0.9)
    assert sum(r["share"] for r in rows) == pytest.approx(1.0)


def test_summarize_names_the_cause(home, clock):
    m = Meter(clock=clock)
    now = clock()
    m.record(prompt_tokens=9000, completion_tokens=0, ts=now - 10, tool_name="rogue_tool")
    text = summarize(m, window_seconds=3600, clock=clock)
    assert "rogue_tool" in text and "9,000" in text


# ---------------------------------------------------------------- CLI
def test_cli_status_top_why(home, clock, capsys, monkeypatch):
    monkeypatch.setenv("HOME", str(home))
    m = Meter()
    m.record(provider="p", tool_name="t", prompt_tokens=100,
             completion_tokens=50, ts=__import__("time").time())
    assert gov_cli.main(["--home", str(home), "status"]) == 0
    out = capsys.readouterr().out
    assert "150" in out and "all closed" in out
    assert gov_cli.main(["--home", str(home), "top", "--by", "tool"]) == 0
    assert "t:" in capsys.readouterr().out
    assert gov_cli.main(["--home", str(home), "why"]) == 0
    assert "Top cause" in capsys.readouterr().out
    assert gov_cli.main(["--home", str(home), "cooldowns"]) == 0
    assert "No cool-down" in capsys.readouterr().out
    assert gov_cli.main(["--home", str(home), "budgets"]) == 0
    assert "session_tokens" in capsys.readouterr().out


# ---------------------------------------------------------------- priority lane
def _wallet_and_cooldowns(home, clock):
    wallet = PassWallet(clock=clock)
    cd = CooldownManager(clock=clock, wallet=wallet)
    return wallet, cd


def test_pass_issue_redeem_expiry_scopes(home, clock):
    wallet = PassWallet(clock=clock)
    bp = wallet.issue(scope="provider:x", uses=2, ttl_seconds=100, note="test")
    assert bp.pass_id.startswith("bp_")
    assert wallet.redeemable(bp.pass_id, "provider:x") == (True, "ok")
    assert wallet.redeem(bp.pass_id, "provider:x") == (True, "ok")
    # wrong scope: not honored, not consumed
    ok, why = wallet.redeem(bp.pass_id, "provider:y")
    assert not ok and "does not cover" in why
    assert wallet.get(bp.pass_id).uses_remaining == 1
    # expiry
    clock.advance(101)
    ok, why = wallet.redeem(bp.pass_id, "provider:x")
    assert not ok and "expired" in why
    # refund
    wallet.refund(bp.pass_id)
    assert wallet.get(bp.pass_id).uses_remaining == 2
    # unknown pass
    assert wallet.redeemable("bp_nope", "provider:x")[0] is False


def test_pass_cannot_manufacture_contention(home, clock):
    """The honesty core: a pass against a closed circuit changes nothing."""
    wallet, cd = _wallet_and_cooldowns(home, clock)
    bp = wallet.issue(uses=3)
    grant = cd.acquire("provider:x", pass_id=bp.pass_id)
    assert grant.allowed and not grant.reserved and grant.pass_id == ""
    assert wallet.get(bp.pass_id).uses_remaining == 3  # untouched
    assert cd.status() == {}  # no circuit opened, no reservation
    # ...and again via the full provider wrapper
    inner = FakeProvider()
    gov = GovernedProvider(inner, clock=clock, wallet=wallet,
                           cooldowns=cd, pass_id=bp.pass_id)
    resp = gov.chat(_msgs(), [])
    assert resp.error is None and inner.calls == 1
    assert wallet.get(bp.pass_id).uses_remaining == 3
    assert Meter(clock=clock).query()[-1].priority_pass_id == ""


def test_reserve_only_during_genuine_contention(home, clock):
    wallet, cd = _wallet_and_cooldowns(home, clock)
    bp = wallet.issue(uses=2)
    cd.breach("provider:x", "real spike")
    grant = cd.acquire("provider:x", pass_id=bp.pass_id)
    assert not grant.allowed and grant.reserved
    assert grant.pass_id == bp.pass_id
    assert "genuine contention" in grant.reason
    assert "priority pass" in grant.reason.lower() and bp.pass_id in grant.reason
    assert "real spike" in grant.reason  # the true cause is named
    assert wallet.get(bp.pass_id).uses_remaining == 1  # one use consumed
    st = cd.status()["provider:x"]
    assert st["probe_reserved_by"] == bp.pass_id


def test_reserved_probe_wins(home, clock):
    wallet, cd = _wallet_and_cooldowns(home, clock)
    bp = wallet.issue()
    cd.breach("provider:x", "r")
    assert cd.acquire("provider:x", pass_id=bp.pass_id).reserved
    clock.advance(61)
    # Non-holder asks first: refused, told why.
    g2 = cd.acquire("provider:x")
    assert not g2.allowed and "reserved by a priority pass holder" in g2.reason
    # Holder: wins the single probe slot.
    g3 = cd.acquire("provider:x", pass_id=bp.pass_id)
    assert g3.allowed and g3.probe and g3.pass_id == bp.pass_id
    cd.probe_success("provider:x")
    assert cd.acquire("provider:x").allowed  # circuit closed again


def test_reservation_refunded_on_reset(home, clock):
    wallet, cd = _wallet_and_cooldowns(home, clock)
    bp = wallet.issue()
    cd.breach("provider:x", "r")
    cd.acquire("provider:x", pass_id=bp.pass_id)
    assert wallet.get(bp.pass_id).uses_remaining == 0
    cd.reset("provider:x")
    assert wallet.get(bp.pass_id).uses_remaining == 1
    assert "provider:x" not in cd.status()


def test_expired_pass_gets_no_priority(home, clock):
    wallet, cd = _wallet_and_cooldowns(home, clock)
    bp = wallet.issue(ttl_seconds=10)
    clock.advance(11)
    cd.breach("provider:x", "r")
    grant = cd.acquire("provider:x", pass_id=bp.pass_id)
    assert not grant.allowed and not grant.reserved
    assert "not honored" in grant.reason and "expired" in grant.reason
    assert "provider:x" not in str(cd.status().get("provider:x", {}))


def test_wallet_corrupt_never_crashes(home, clock):
    wallet = PassWallet(clock=clock)
    wallet._file.parent.mkdir(parents=True, exist_ok=True)
    wallet._file.write_text("garbage{{{", encoding="utf-8")
    w2 = PassWallet(clock=clock)
    assert w2.list_active() == []
    assert w2.redeemable("bp_x", "s") == (False, "unknown pass 'bp_x'")


def test_no_fake_scarcity_language():
    """Deception guard: user-facing strings must never fake overload."""
    import pathlib

    banned = [
        "overloaded",
        "high demand",
        "heavy load",
        "servers are busy",
        "server is busy",
        "too many users",
        "demand surge",
    ]
    src = pathlib.Path(__file__).resolve().parents[1] / "core" / "levi" / "governor"
    for name in ("priority.py", "cooldown.py", "governed.py", "__main__.py",
                 "meter.py", "diagnose.py", "budgets.py", "spikes.py"):
        text = (src / name).read_text(encoding="utf-8").lower()
        for phrase in banned:
            assert phrase not in text, f"{name} contains overload theater: {phrase!r}"


def test_governed_pass_flow_end_to_end(home, clock):
    wallet = PassWallet(clock=clock)
    cd = CooldownManager(clock=clock, wallet=wallet)
    det = SpikeDetector(window_seconds=600, absolute_cap=1000, clock=clock)
    inner = FakeProvider(prompt_tokens=100, completion_tokens=50)
    gov = GovernedProvider(inner, clock=clock, wallet=wallet,
                           cooldowns=cd, detector=det)
    bp = wallet.issue()
    # 1. A genuine spike trips the breaker.
    inner_big = FakeProvider(prompt_tokens=5000, completion_tokens=0)
    gov_big = GovernedProvider(inner_big, clock=clock, wallet=wallet,
                               cooldowns=cd, detector=det)
    assert gov_big.chat(_msgs(), []).error is None
    # 2. Contention: pass holder reserves the probe slot.
    r1 = gov.chat_with_pass(_msgs(), [], bp.pass_id)
    assert r1.error and "priority pass" in r1.error.lower() and "genuine contention" in r1.error
    assert inner.calls == 0
    # 3. Backoff elapses: the pass holder's probe runs, metered as priority.
    clock.advance(61)
    r2 = gov.chat_with_pass(_msgs(), [], bp.pass_id)
    assert r2.error is None and inner.calls == 1
    rec = Meter(clock=clock).query()[-1]
    assert rec.priority_pass_id == bp.pass_id
    # 4. Diagnosis labels it honestly.
    text = summarize(Meter(clock=clock), window_seconds=3600,
                     cooldowns=cd, wallet=wallet, clock=clock)
    assert "Priority lane" in text and "genuine contention" in text


def test_cli_passes(home, capsys):
    assert gov_cli.main(["--home", str(home), "passes"]) == 0
    assert "No active burst passes" in capsys.readouterr().out
    assert gov_cli.main(["--home", str(home), "pass-issue",
                         "--scope", "provider:x", "--uses", "5",
                         "--note", "test-sale"]) == 0
    out = capsys.readouterr().out
    assert "Issued burst pass bp_" in out and "genuine cool-downs only" in out
    assert gov_cli.main(["--home", str(home), "passes"]) == 0
    out = capsys.readouterr().out
    assert "provider:x" in out and "5/5" in out
