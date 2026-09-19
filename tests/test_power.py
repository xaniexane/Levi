"""Tests for levi.power — the organism-wide signal layer."""

import pytest

from levi.power import (
    Booster,
    BreakerOpen,
    BreakerState,
    CircuitBreaker,
    Delivery,
    Direction,
    GainStage,
    PowerRail,
    Repeater,
    Signal,
    StepAmplifier,
    TransformChain,
    Transformer,
    attenuate,
    degraded,
    signal_to_noise,
)
from levi.power.lwp import (
    IMMORTAL_REPEATER,
    SCAR_REPEATER,
    PowerProfile,
    finale_surge,
    power_repeats,
    power_step,
    profile,
)


# --- Signal ---


def test_signal_clamps_strength_and_noise():
    s = Signal(value=1.0, strength=9.0, noise=-3.0)
    assert s.strength == 1.0
    assert s.noise == 0.0


def test_attenuate_decays_strength_not_value():
    s = attenuate(Signal(value=10.0, strength=1.0), 0.5)
    assert s.value == 10.0
    assert s.strength == pytest.approx(0.5)
    assert s.noise > 0.0


def test_attenuate_rejects_bad_factor():
    with pytest.raises(ValueError):
        attenuate(Signal(), 0.0)
    with pytest.raises(ValueError):
        attenuate(Signal(), 1.5)


def test_snr_and_degraded():
    assert signal_to_noise(Signal(strength=1.0, noise=0.0)) == float("inf")
    assert signal_to_noise(Signal(strength=1.0, noise=0.5)) == pytest.approx(2.0)
    assert degraded(Signal(strength=0.1))
    assert not degraded(Signal(strength=0.9))


# --- Transformer ---


def test_transformer_converts_and_preserves_payload():
    t = Transformer(convert=lambda v: v * 2, name="doubler")
    out = t.convert(Signal(value=21.0, payload="cargo", tags=["in"]))
    assert out is not None
    assert out.value == 42.0
    assert out.payload == "cargo"
    assert out.tags == ["in", "doubler"]
    assert t.converted == 1


def test_transformer_isolates_noise_below_floor():
    t = Transformer(noise_floor=0.5)
    weak = Signal(value=1.0, strength=0.2)
    assert t.convert(weak) is None
    assert len(t.quarantined) == 1
    strong = Signal(value=1.0, strength=0.9)
    assert t.convert(strong) is not None
    assert len(t.quarantined) == 1


def test_transformer_rejects_bad_floor():
    with pytest.raises(ValueError):
        Transformer(noise_floor=1.5)


def test_transform_chain_runs_left_to_right_and_stops_at_quarantine():
    a = Transformer(convert=lambda v: v + 1, name="a")
    b = Transformer(convert=lambda v: v * 10, noise_floor=0.9, name="b")
    chain = a.chain(b)
    out, ran = chain.convert(Signal(value=1.0, strength=1.0))
    assert out is not None and out.value == 20.0
    assert ran == ["a", "b"]
    out2, ran2 = chain.convert(Signal(value=1.0, strength=0.5))
    assert out2 is None
    assert ran2 == ["a", "b"]  # a ran, then b quarantined
    assert len(chain.quarantined) == 1


def test_transform_chain_needs_a_stage():
    with pytest.raises(ValueError):
        TransformChain([])


# --- Amplifier ---


def test_booster_burns_charges_then_passes_through():
    b = Booster(factor=2.0, charges=2)
    s1 = b.apply(Signal(value=5.0))
    s2 = b.apply(s1)
    assert s1.value == 10.0 and s2.value == 20.0
    assert b.spent
    s3 = b.apply(s2)
    assert s3.value == 20.0  # spent: unchanged
    assert "boosted x2" in s1.tags


def test_booster_rejects_bad_args():
    with pytest.raises(ValueError):
        Booster(factor=0)
    with pytest.raises(ValueError):
        Booster(charges=-1)


def test_gain_stage_climbs_to_band_then_holds():
    g = GainStage(band=(80_000, 100_000), step=70)
    s = Signal(value=79_800)
    assert not g.in_band(s)
    s = g.apply(s)
    assert s.value == 79_870
    assert not g.in_band(s)
    s = g.apply(s)
    assert s.value == 79_940
    assert not g.in_band(s)
    s = g.apply(s)
    assert s.value == 80_010
    assert g.in_band(s)
    held = g.apply(s)
    assert held.value == s.value  # holds, never overshoots


def test_gain_stage_never_overshoots_hi():
    g = GainStage(band=(100.0, 110.0), step=50.0)
    s = g.apply(Signal(value=90.0))
    assert s.value == 110.0  # clamped at band top, not 140


def test_gain_stage_rejects_bad_band_and_step():
    with pytest.raises(ValueError):
        GainStage(band=(10.0, 5.0), step=1.0)
    with pytest.raises(ValueError):
        GainStage(band=(1.0, 2.0), step=0.0)


def test_step_amplifier_named_steps():
    amp = StepAmplifier({"gain": 70, "booster": 30})
    assert amp.apply(300, "gain") == 370
    assert amp.apply(300, "booster") == 330
    assert amp.apply(300, "unknown") == 300  # unknown kinds pass through


# --- Repeater ---


def test_repeater_restores_strength_on_schedule():
    r = Repeater(essence="scar", interval=2, decay=0.5, restore=1.0)
    out, log = r.propagate(Signal(value=1.0, strength=1.0), hops=4)
    assert log.reinjections == 2
    assert log.injections == [2, 4]
    assert log.essences == ["scar", "scar"]
    assert out.strength == 1.0  # restored at hop 4
    assert "repeated" in out.tags


def test_repeater_decay_without_reinjection_rots():
    r = Repeater(essence="scar", interval=100, decay=0.5)
    out, log = r.propagate(Signal(value=1.0, strength=1.0), hops=3)
    assert log.reinjections == 0
    assert out.strength == pytest.approx(0.125)


def test_repeater_should_reinject():
    r = Repeater(interval=3)
    assert not r.should_reinject(0)
    assert r.should_reinject(3)
    assert not r.should_reinject(4)
    assert r.should_reinject(6)


def test_repeater_multi_cycles_essences():
    r = Repeater.multi(["a", "b"], interval=1, decay=1.0)
    assert r.multi_sequence
    _, log = r.propagate(Signal(value=1.0), hops=3)
    assert log.essences == ["a", "b", "a"]


def test_repeater_rejects_bad_args():
    with pytest.raises(ValueError):
        Repeater(interval=0)
    with pytest.raises(ValueError):
        Repeater(decay=0.0)
    with pytest.raises(ValueError):
        Repeater.multi([])
    with pytest.raises(ValueError):
        Repeater().propagate(Signal(), hops=-1)


# --- CircuitBreaker ---


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, s):
        self.now += s


def _boom():
    raise RuntimeError("fault")


def test_breaker_closed_passes_calls():
    b = CircuitBreaker(failure_threshold=2)
    assert b.call(lambda: 42) == 42
    assert b.state is BreakerState.CLOSED


def test_breaker_opens_at_threshold_and_refuses_fast():
    b = CircuitBreaker(name="t", failure_threshold=2)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state is BreakerState.CLOSED  # one failure is not enough
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state is BreakerState.OPEN
    assert b.trips == 1
    with pytest.raises(BreakerOpen):
        b.call(lambda: 1)  # refused without running fn


def test_breaker_success_resets_failure_count():
    b = CircuitBreaker(failure_threshold=3)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    b.call(lambda: 1)
    assert b.failures == 0
    assert b.state is BreakerState.CLOSED


def test_breaker_half_open_probe_closes_on_success():
    clock = _Clock()
    b = CircuitBreaker(failure_threshold=1, cooldown=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state is BreakerState.OPEN
    clock.advance(11.0)
    assert b.state is BreakerState.HALF_OPEN
    assert b.call(lambda: "probe-ok") == "probe-ok"
    assert b.state is BreakerState.CLOSED


def test_breaker_failed_probe_reopens_with_fresh_cooldown():
    clock = _Clock()
    b = CircuitBreaker(failure_threshold=1, cooldown=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(11.0)
    with pytest.raises(RuntimeError):
        b.call(_boom)  # failed probe
    assert b.state is BreakerState.OPEN
    assert b.trips == 2
    clock.advance(5.0)
    assert b.state is BreakerState.OPEN  # fresh cooldown, not half-open yet


def test_breaker_manual_isolate_holds_until_reset():
    clock = _Clock()
    b = CircuitBreaker(cooldown=1.0, clock=clock)
    b.isolate()
    clock.advance(100.0)
    assert b.state is BreakerState.OPEN  # manual hold ignores cooldown
    with pytest.raises(BreakerOpen):
        b.call(lambda: 1)
    b.reset()
    assert b.state is BreakerState.CLOSED


def test_breaker_rejects_bad_config():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(cooldown=-1.0)


def test_breaker_guard_wraps_function():
    b = CircuitBreaker(failure_threshold=1)
    guarded = b.guard(_boom)
    with pytest.raises(RuntimeError):
        guarded()
    assert b.state is BreakerState.OPEN


# --- PowerRail ---


def _recorder(seen):
    def handle(delivery: Delivery):
        seen.append((delivery.consumer, delivery.allocation))

    return handle


def test_rail_distributes_by_weight():
    rail = PowerRail("w")
    seen = []
    rail.consumer("a", _recorder(seen), weight=1.0)
    rail.consumer("b", _recorder(seen), weight=3.0)
    rep = rail.distribute(100.0)
    assert rep.allocations == {"a": 25.0, "b": 75.0}
    assert rep.served == pytest.approx(100.0)
    assert rep.unserved == pytest.approx(0.0)
    assert rep.faults == {}


def test_rail_respects_need_caps_and_redistributes_leftover():
    rail = PowerRail("caps")
    rail.consumer("capped", lambda d: None, weight=1.0, need=10.0)
    rail.consumer("hungry", lambda d: None, weight=1.0)
    rep = rail.distribute(100.0)
    assert rep.allocations["capped"] == 10.0
    assert rep.allocations["hungry"] == pytest.approx(90.0)
    assert rep.served == pytest.approx(100.0)


def test_rail_isolates_faulted_consumer_without_killing_rail():
    rail = PowerRail("iso")
    good_seen = []

    def bad(delivery: Delivery):
        raise RuntimeError("consumer fault")

    rail.consumer("bad", bad, failure_threshold=1)
    rail.consumer("good", _recorder(good_seen))
    rep = rail.distribute(100.0)
    assert "bad" in rep.faults
    assert "bad" in rep.isolated
    assert "bad" not in rep.allocations
    # healthy consumer still served, in a later round too
    rep2 = rail.distribute(100.0)
    assert rep2.allocations == {"good": pytest.approx(100.0)}
    assert good_seen  # handler ran


def test_rail_surge_multiplies_budget_then_ends():
    rail = PowerRail("surge")
    rail.consumer("a", lambda d: None)
    rail.surge(factor=2.0, rounds=2)
    r1 = rail.distribute(50.0)
    assert r1.surged and r1.effective_budget == 100.0
    r2 = rail.distribute(50.0)
    assert r2.surged and r2.effective_budget == 100.0
    r3 = rail.distribute(50.0)
    assert not r3.surged and r3.effective_budget == 50.0


def test_rail_surge_keeps_breakers_armed():
    rail = PowerRail("surge-armed")

    def bad(delivery: Delivery):
        raise RuntimeError("still faulty under surge")

    rail.consumer("bad", bad, failure_threshold=1)
    rail.consumer("good", lambda d: None)
    rail.surge(factor=3.0, rounds=1)
    rep = rail.distribute(10.0)
    assert rep.surged
    assert "bad" in rep.isolated  # surge never excuses a fault


def test_rail_surge_rejects_bad_args():
    rail = PowerRail("s")
    with pytest.raises(ValueError):
        rail.surge(factor=0.5)
    with pytest.raises(ValueError):
        rail.surge(factor=2.0, rounds=0)


def test_rail_rejects_duplicate_consumer_and_negative_budget():
    rail = PowerRail("dup")
    rail.consumer("a", lambda d: None)
    with pytest.raises(ValueError):
        rail.consumer("a", lambda d: None)
    with pytest.raises(ValueError):
        rail.distribute(-1.0)


def test_rail_route_directions():
    order = []

    def handle(delivery: Delivery):
        order.append(delivery.consumer)

    rail = PowerRail("route")
    rail.consumer("one", handle)
    rail.consumer("two", handle)
    sig = Signal(value=7.0)

    rep = rail.route(sig, Direction.FORWARD)
    assert rep.deliveries == ["one", "two"]

    order.clear()
    rep = rail.route(sig, Direction.REVERSE)
    assert rep.deliveries == ["two", "one"]

    order.clear()
    rep = rail.route(sig, Direction.FREE)
    assert rep.deliveries == ["one"]  # first healthy consumer only


def test_rail_route_inverse_negates_value():
    seen = {}

    def handle(delivery: Delivery):
        seen[delivery.consumer] = delivery.signal.value

    rail = PowerRail("inv")
    rail.consumer("one", handle)
    rail.route(Signal(value=7.0), Direction.INVERSE)
    assert seen["one"] == -7.0


def test_rail_route_skips_isolated_consumers():
    rail = PowerRail("skip")

    def bad(delivery: Delivery):
        raise RuntimeError("down")

    rail.consumer("bad", bad, failure_threshold=1)
    rail.consumer("good", lambda d: None)
    rail.distribute(10.0)  # trips bad's breaker
    assert rail.isolated == ["bad"]
    rep = rail.route(Signal(value=1.0), Direction.FORWARD)
    assert rep.deliveries == ["good"]
    assert rep.isolated == ["bad"]


def test_rail_status_mentions_breakers():
    rail = PowerRail("st")
    rail.consumer("a", lambda d: None)
    out = rail.status()
    assert "PowerRail st" in out and "breaker=closed" in out


# --- L.W.P. bridge ---


def test_lwp_power_steps_match_legacy_values():
    assert power_step("gain") == 70
    assert power_step("booster") == 30
    assert power_step("immortal") == 120
    assert power_step("repeater") == 0
    assert power_step("transformer") == 0
    assert power_step("nope") == 0


def test_lwp_power_repeats_only_repeater():
    assert power_repeats("repeater")
    assert not power_repeats("gain")
    assert not power_repeats("booster")
    assert not power_repeats("nope")


def test_lwp_profiles_carry_primitive_composition():
    assert profile("immortal").multi_sequence
    assert profile("immortal").amp_step == 120
    assert profile("transformer").converts
    assert profile("repeater").repeats
    unknown = profile("nope")
    assert isinstance(unknown, PowerProfile) and unknown.amp_step == 0


def test_lwp_scar_repeater_reinjects_every_hop():
    _, log = SCAR_REPEATER.propagate(Signal(value=1.0, strength=0.1), hops=3)
    assert log.reinjections == 3  # interval=1: every hop


def test_lwp_immortal_repeater_cycles_sequences():
    assert IMMORTAL_REPEATER.multi_sequence
    _, log = IMMORTAL_REPEATER.propagate(Signal(value=1.0), hops=21)
    assert log.reinjections == 3
    assert log.essences == [
        "sequence/alpha",
        "sequence/omega",
        "sequence/echo",
    ]


def test_lwp_finale_surge_arms_rail():
    rail = PowerRail("finale")
    rail.consumer("a", lambda d: None)
    finale_surge(rail, factor=2.0, rounds=1)
    rep = rail.distribute(10.0)
    assert rep.surged and rep.effective_budget == 20.0


# --- model_engine delegation stays intact ---


def test_model_engine_target_words_delegates_to_power_layer(tmp_path):
    from levi.lwp.model_engine import LWPModelEngine

    eng = LWPModelEngine(path=tmp_path / "m.json")
    eng.configure(phase="distance", power="repeater")  # base 260, no step
    assert eng.target_words() == 260
    eng.configure(power="transformer")
    assert eng.target_words() == 260
    eng.configure(power="booster")
    assert eng.target_words() == 290
    eng.configure(power="gain")
    assert eng.target_words() == 330
    eng.configure(power="immortal")
    assert eng.target_words() == 380
    eng.configure(phase="finale", power="gain")  # base 240 + 70
    assert eng.target_words() == 310


def test_model_engine_assemble_repeater_sentence_via_power_layer(tmp_path):
    from levi.lwp.model_engine import LWPModelEngine

    eng = LWPModelEngine(path=tmp_path / "m.json")
    eng.configure(power="repeater")
    built = eng.assemble(key="pw-test-repeater", target=120)
    assert "Scar liturgy re-entered so the distance would not rot." in built["text"]
    eng.configure(power="booster")
    built = eng.assemble(key="pw-test-booster", target=120)
    assert "Scar liturgy re-entered so the distance would not rot." not in built["text"]
