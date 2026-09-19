"""Tests for levi.social.living — the living layer.

Presence honesty, cartoon motion validation, overlay/immersion contracts,
reduced-motion degradation, and sealed bundle round-trips.
"""

import pytest

from levi.social import living
from levi.social.living import (
    Expression,
    ExpressionSlot,
    Frame,
    LivingError,
    LivingLayer,
    Overlay,
    OverlayGrant,
    PresenceAnimation,
    PresenceBeacon,
    Simulation,
)


# ---------------------------------------------------------------------------
# 1. Agent presence
# ---------------------------------------------------------------------------


def test_presence_states_valid():
    for state in ("idle", "working", "thinking", "delivering", "resting"):
        activity = "rescuing the bakery site" if state in (
            "working", "thinking", "delivering") else ""
        b = PresenceBeacon(operator_id="op-1", state=state, activity=activity)
        assert b.state == state


def test_presence_bad_state_refused():
    with pytest.raises(LivingError):
        PresenceBeacon(operator_id="op-1", state="sleeping", activity="")


def test_presence_work_without_activity_refused():
    # Honesty: claiming work without naming it is faked presence.
    for state in ("working", "thinking", "delivering"):
        with pytest.raises(LivingError):
            PresenceBeacon(operator_id="op-1", state=state, activity="")
        with pytest.raises(LivingError):
            PresenceBeacon(operator_id="op-1", state=state, activity="   ")


def test_presence_rest_with_activity_refused():
    # Honesty: rest states must not fake an activity claim.
    for state in ("idle", "resting"):
        with pytest.raises(LivingError):
            PresenceBeacon(operator_id="op-1", state=state,
                           activity="secretly working")


def test_presence_set_state_keeps_honesty():
    b = PresenceBeacon(operator_id="op-1", state="idle")
    b.set_state("working", activity="lifting the bakery site")
    assert b.state == "working"
    with pytest.raises(LivingError):
        b.set_state("delivering")  # no activity named
    with pytest.raises(LivingError):
        b.set_state("resting", activity="still working")  # faked rest


def test_presence_animation_bounds():
    with pytest.raises(LivingError):
        PresenceAnimation(name="x", duration_ms=10)  # too fast
    with pytest.raises(LivingError):
        PresenceAnimation(name="x", duration_ms=60000)  # too slow
    with pytest.raises(LivingError):
        PresenceAnimation(name="bad name!", duration_ms=500)
    ok = PresenceAnimation(name="hands-moving", loop=True, duration_ms=1200)
    assert ok.spec()["duration_ms"] == 1200


def test_presence_default_animations_cover_all_states():
    for state in living.PRESENCE_STATES:
        anim = living.DEFAULT_PRESENCE_ANIMATIONS[state]
        anim.validate()


# ---------------------------------------------------------------------------
# 2. Cartoon / GIF-like motion
# ---------------------------------------------------------------------------


def _frames():
    return [Frame(name="f1", duration_ms=200),
            Frame(name="f2", duration_ms=200),
            Frame(name="f3", duration_ms=400)]


def test_expression_valid():
    e = Expression(name="happy-dance", motion="bounce", frames=_frames())
    assert e.total_ms() == 800
    assert e.starts == "muted"  # muted-by-default


def test_expression_bad_motion_refused():
    with pytest.raises(LivingError):
        Expression(name="x", motion="explode", frames=_frames())


def test_expression_autoplay_refused():
    # No autoplay ambushes: starts must be member-invited or muted.
    with pytest.raises(LivingError):
        Expression(name="x", motion="pop", frames=_frames(), starts="auto")


def test_expression_frame_bounds():
    with pytest.raises(LivingError):
        Expression(name="x", motion="wiggle",
                   frames=[Frame(name="f1", duration_ms=10)])
    with pytest.raises(LivingError):
        Expression(name="x", motion="wiggle",
                   frames=[Frame(name="f1", duration_ms=5000)])


def test_expression_empty_frames_refused():
    with pytest.raises(LivingError):
        Expression(name="x", motion="pop", frames=[])


def test_expression_duplicate_frames_refused():
    with pytest.raises(LivingError):
        Expression(name="x", motion="pop",
                   frames=[Frame(name="f1", duration_ms=200),
                           Frame(name="f1", duration_ms=200)])


def test_expression_loop_cap():
    long_frames = [Frame(name="f%d" % i, duration_ms=2000) for i in range(20)]
    with pytest.raises(LivingError):
        Expression(name="marathon", motion="parade", frames=long_frames)
    # Non-looping long sequences are fine — they end.
    ok = Expression(name="marathon", motion="parade",
                    frames=long_frames, loop=False)
    assert ok.loop is False


def test_expression_slot_targets():
    e = Expression(name="wave", motion="pop", frames=_frames())
    ExpressionSlot(target="profile", ref="keeper", expression=e)
    ExpressionSlot(target="post", ref="post-9", expression=e)
    with pytest.raises(LivingError):
        ExpressionSlot(target="galaxy", ref="keeper", expression=e)


# ---------------------------------------------------------------------------
# 3. Immersive overlays and simulations
# ---------------------------------------------------------------------------


def test_overlay_valid():
    o = Overlay(id="ov-1", anchor="profile-region", region="hero",
                depth=20, title="Welcome tour")
    assert o.dismissible is True
    o2 = Overlay(id="ov-2", anchor="viewport", depth=0)
    assert o2.region == ""


def test_overlay_not_dismissible_refused():
    # Immersion is never imposed.
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="viewport", dismissible=False)


def test_overlay_anchor_rules():
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="profile-region")  # region unnamed
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="viewport", region="hero")  # region misplaced
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="everywhere")
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="viewport", depth=100)  # depth out of range
    with pytest.raises(LivingError):
        Overlay(id="ov-1", anchor="viewport", depth=-1)


def test_overlay_grant_required_by_layer():
    layer = LivingLayer(
        owner_id="keeper",
        overlays=[Overlay(id="ov-1", anchor="viewport")],
        grants=[OverlayGrant(overlay_id="ov-1", member_id="keeper")],
    )
    assert len(layer.grants) == 1
    with pytest.raises(LivingError):
        LivingLayer(
            owner_id="keeper",
            overlays=[Overlay(id="ov-1", anchor="viewport")],
            grants=[OverlayGrant(overlay_id="ov-9", member_id="keeper")],
        )


def test_simulation_invite_exit_contract():
    s = Simulation(id="sim-1", scene="the bakery at dawn",
                   actors=("baker-op",))
    assert s.state == "invited"
    s.enter()
    assert s.state == "active"
    s.exit()
    assert s.state == "exited"
    with pytest.raises(LivingError):
        s.enter()  # exited sessions never reopen
    with pytest.raises(LivingError):
        s.exit()  # already exited


def test_simulation_must_be_invited():
    with pytest.raises(LivingError):
        Simulation(id="sim-1", scene="dark room", invited=False)


def test_simulation_exit_from_invited():
    # The clean exit is always available — even before entering.
    s = Simulation(id="sim-1", scene="the bakery at dawn")
    s.exit()
    assert s.state == "exited"


def test_simulation_bad_actors_refused():
    with pytest.raises(LivingError):
        Simulation(id="sim-1", scene="x",
                   actors=("op-1", "op-1"))  # duplicate actors


# ---------------------------------------------------------------------------
# Reduced-motion degradation across all three systems
# ---------------------------------------------------------------------------


def _full_layer() -> LivingLayer:
    return LivingLayer(
        owner_id="keeper",
        beacons=[PresenceBeacon(operator_id="op-1", state="working",
                                activity="lifting the bakery site")],
        expressions=[ExpressionSlot(
            target="profile", ref="keeper",
            expression=Expression(name="wave", motion="pop",
                                  frames=_frames()))],
        overlays=[Overlay(id="ov-1", anchor="viewport", depth=5)],
        grants=[OverlayGrant(overlay_id="ov-1", member_id="keeper")],
        simulations=[Simulation(id="sim-1", scene="the bakery at dawn")],
    )


def test_reduced_motion_degrades_everything():
    layer = _full_layer()
    out = layer.render(reduced_motion=True)
    assert out["reduced_motion"] is True
    assert out["beacons"][0]["animation"] == {
        "name": out["beacons"][0]["animation"]["name"],
        "motion": "static",
    }
    assert out["expressions"][0]["motion"] == "static"
    assert out["expressions"][0]["frame"] == "f1"  # frozen on first frame
    assert out["overlays"][0]["motion"] == "static"
    assert out["overlays"][0]["dismissible"] is True  # still dismissible
    assert out["simulations"][0]["motion"] == "static"
    # Identities survive degradation.
    assert out["beacons"][0]["state"] == "working"
    assert out["beacons"][0]["activity"] == "lifting the bakery site"


def test_full_motion_render():
    out = _full_layer().render(reduced_motion=False)
    assert out["beacons"][0]["animation"]["duration_ms"] == 2400  # default anim
    assert out["expressions"][0]["motion"] == "pop"
    assert len(out["expressions"][0]["frames"]) == 3


# ---------------------------------------------------------------------------
# Sealed bundle round-trip
# ---------------------------------------------------------------------------


def test_bundle_round_trip():
    layer = _full_layer()
    clone = LivingLayer.from_dict(layer.to_dict())
    assert clone.owner_id == "keeper"
    assert clone.beacons[0].state == "working"
    assert clone.beacons[0].activity == "lifting the bakery site"
    assert clone.expressions[0].expression.motion == "pop"
    assert clone.overlays[0].anchor == "viewport"
    assert clone.grants[0].member_id == "keeper"
    assert clone.simulations[0].scene == "the bakery at dawn"


def test_bundle_tamper_refused():
    data = _full_layer().to_dict()
    data["beacons"][0]["state"] = "resting"  # tamper after sealing
    with pytest.raises(LivingError):
        LivingLayer.from_dict(data)


def test_bundle_bad_format_or_version_refused():
    data = _full_layer().to_dict()
    data["format"] = "something-else"
    with pytest.raises(LivingError):
        LivingLayer.from_dict(data)
    data = _full_layer().to_dict()
    data["version"] = 99
    with pytest.raises(LivingError):
        LivingLayer.from_dict(data)


def test_layer_duplicate_ids_refused():
    with pytest.raises(LivingError):
        LivingLayer(
            owner_id="keeper",
            beacons=[
                PresenceBeacon(operator_id="op-1", state="idle"),
                PresenceBeacon(operator_id="op-1", state="idle"),
            ],
        )
    with pytest.raises(LivingError):
        LivingLayer(
            owner_id="keeper",
            overlays=[Overlay(id="ov-1", anchor="viewport"),
                      Overlay(id="ov-1", anchor="viewport")],
        )
    with pytest.raises(LivingError):
        LivingLayer(
            owner_id="keeper",
            simulations=[Simulation(id="s", scene="a"),
                         Simulation(id="s", scene="b")],
        )
