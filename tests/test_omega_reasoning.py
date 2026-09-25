"""Reasoned-routing tests: Alpha reasons, Omega platforms and routes.

One call path — ``reason_route`` — deliberates over the task text
(propose -> critique -> verdict) and then routes over providers under
Nexus's unchanged policy. Both laws must hold through the wiring: Alpha's
honesty law (the verdict states its substrate; the brain-voice never
wins) and Nexus's sourcing law (references never eligible, in any mode).
"""

import pytest

from levi.alpha.reason import SUBSTRATE_HYBRID, SUBSTRATE_RULES
from levi.revival.omega import reasoning as rr
from levi.revival.omega import nexus as nx


def _fleet():
    return [
        nx.Provider(
            name="levi-local",
            source=nx.SOURCE_LOCAL,
            kinds=frozenset({"chat", "code"}),
            cost=1,
            quality=0.6,
        ),
        nx.Provider(
            name="levi-si-cloud",
            source=nx.SOURCE_CLOUD,
            kinds=frozenset({"chat", "code", "vision"}),
            cost=4,
            quality=0.9,
        ),
        nx.Provider(
            name="rival-a",
            source=nx.SOURCE_REFERENCE,
            kinds=frozenset({"chat", "code", "vision"}),
            cost=1,
            quality=1.0,
        ),
    ]


# ---- the wire itself ----


def test_reason_route_deliberates_then_routes():
    plan = rr.reason_route(
        "Should I take an umbrella today?",
        _fleet(),
        mode="balanced",
    )
    assert plan.task_text == "Should I take an umbrella today?"
    assert plan.task_type == "yes-no"
    assert plan.kinds == rr.DEFAULT_KINDS
    # the deliberation survived the wiring intact
    v = plan.verdict
    for key in ("chosen", "score", "answer", "survived_weakness", "open_question"):
        assert key in v, key
    assert v["answer"], "the verdict must carry its own answer text"
    # Alpha's honesty law: the substrate is reported, honestly, in this env
    assert plan.substrate in {SUBSTRATE_RULES, SUBSTRATE_HYBRID}
    assert plan.limits  # the limits line always says what reasoned
    # and the routes are Nexus's unchanged policy, best first
    assert plan.routes
    eligible = [r.provider for r in plan.routes if r.eligible]
    assert eligible
    assert plan.top_provider == eligible[0]


def test_task_type_reported_for_information_question():
    plan = rr.reason_route("What is the best way to water herbs?", _fleet())
    assert plan.task_type == "information"
    assert "best" in plan.verdict["answer"] or plan.verdict["answer"]


def test_caller_supplied_kinds_reach_the_router():
    plan = rr.reason_route(
        "describe this image for me",
        _fleet(),
        kinds=frozenset({"vision"}),
    )
    assert plan.kinds == frozenset({"vision"})
    # only the cloud covers vision; the local is missing a kind but still
    # eligible — the kind facts traveled through honestly
    cloud = next(r for r in plan.routes if r.provider == "levi-si-cloud")
    assert cloud.eligible
    # no default-kinds caveat when the caller supplied kinds
    assert not any("defaulted" in c for c in plan.caveats)


def test_default_kinds_are_reported_as_default():
    plan = rr.reason_route("hello", _fleet())
    assert any("defaulted" in c for c in plan.caveats)


def test_needs_local_excludes_cloud():
    plan = rr.reason_route(
        "keep this on the device",
        _fleet(),
        mode="balanced",
        needs_local=True,
    )
    assert plan.needs_local is True
    cloud = next(r for r in plan.routes if r.provider == "levi-si-cloud")
    assert not cloud.eligible


# ---- the sourcing law survives the wiring ----


def test_reference_never_eligible_through_reason_route():
    for mode in nx.MODES:
        plan = rr.reason_route("Should I take an umbrella today?", _fleet(), mode=mode)
        ref = next(r for r in plan.routes if r.provider == "rival-a")
        assert not ref.eligible, f"reference eligible in mode {mode}"
        assert ref.confidence == 0.0


def test_offline_deny_closed_through_reason_route():
    plan = rr.reason_route("keep this private", _fleet(), mode="offline")
    for r in plan.routes:
        if r.provider == "levi-local":
            assert r.eligible
        else:
            assert not r.eligible and r.confidence == 0.0
    assert plan.top_provider == "levi-local"


def test_nobody_eligible_gives_no_top_provider():
    plan = rr.reason_route(
        "route this nowhere",
        [nx.Provider(name="rival-a")],
        mode="balanced",
    )
    assert plan.top_provider is None
    assert all(not r.eligible for r in plan.routes)


# ---- refusal paths ----


def test_empty_task_refused():
    with pytest.raises(ValueError, match="empty task"):
        rr.reason_route("   ", _fleet())


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="unknown mode"):
        rr.reason_route("hello", _fleet(), mode="turbo")


def test_empty_providers_raise():
    with pytest.raises(ValueError, match="providers must be non-empty"):
        rr.reason_route("hello", [])


# ---- explain ----


def test_explain_plan_covers_verdict_and_routes():
    plan = rr.reason_route("Should I take an umbrella today?", _fleet())
    text = rr.explain_plan(plan)
    assert "verdict:" in text
    assert "top provider: levi-local" in text
    assert "[SKIP] rival-a" in text
    assert "reference-only" in text
    assert "substrate:" in text
    assert "caveats" in text


# ---- brain-voice continuity in routing output ----

_FAKE_CONTINUATION = "umbrella rain clouds wet garbled brain echo"


def _patch_brain_voice(monkeypatch):
    """Give the Reasoner a running brain with a fixed, labeled output.

    Monkeypatched, not torch-gated: deterministic on every host — this
    exercises the THREADING of the evidence trail, not the weights.
    """
    from levi.alpha import reason as alpha_reason

    def fake(self, task):
        return {
            "stance": alpha_reason.BRAIN_STANCE,
            "text": _FAKE_CONTINUATION,
            "confidence": alpha_reason.BRAIN_CONFIDENCE,
            "label": "raw brain continuation — not reasoning",
        }

    monkeypatch.setattr(alpha_reason.Reasoner, "_brain_voice", fake)


def test_brain_voice_threaded_into_plan_when_brain_runs(monkeypatch):
    _patch_brain_voice(monkeypatch)
    plan = rr.reason_route("Should I take an umbrella today?", _fleet())
    # verbatim, as it ran — the evidence trail, not reasoning
    assert plan.brain_voice == _FAKE_CONTINUATION
    # the verdict still came from a rules stance, never the brain-voice
    assert plan.verdict["chosen"] != "brain-voice"
    text = rr.explain_plan(plan)
    assert "brain-voice (heard, never obeyed)" in text
    assert _FAKE_CONTINUATION in text


def test_brain_voice_absent_when_brain_does_not_run(monkeypatch):
    from levi.alpha import reason as alpha_reason

    monkeypatch.setattr(
        alpha_reason.Reasoner,
        "_load_brain_inference",
        lambda self: (None, "test: brain disabled"),
    )
    plan = rr.reason_route("Should I take an umbrella today?", _fleet())
    assert plan.brain_voice is None
    # no trail is reported as absent, never invented
    assert "brain-voice" not in rr.explain_plan(plan)


# ---- offline + needs_local interplay ----


def test_offline_plus_needs_local_agree():
    """mode="offline" AND needs_local=True deny remotes the same way.

    Two independent flags, one consistent outcome: the cloud route is
    ineligible under both (deny-closed offline policy, needs_local
    scoring), the local provider stays eligible and tops the plan.
    """
    plan = rr.reason_route(
        "keep this private and on the device",
        _fleet(),
        mode="offline",
        needs_local=True,
    )
    assert plan.needs_local is True
    local = next(r for r in plan.routes if r.provider == "levi-local")
    cloud = next(r for r in plan.routes if r.provider == "levi-si-cloud")
    assert local.eligible
    assert not cloud.eligible and cloud.confidence == 0.0
    assert any("offline mode allows LEVI-local only" in r for r in cloud.reasons)
    assert plan.top_provider == "levi-local"
