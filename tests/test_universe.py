"""Tests for levi.universe — the theme-park architecture scaffold.

Everything in one, offline-first: entrance routes through the real Omega
organs (rules-engine substrate here — no torch in this env), the star and
the groupings registry are stdlib-only. Registry tests use tmp dirs;
nothing touches the real $LEVI_HOME.
"""

import json

import pytest

from levi.universe import PARK_MAP, entrance, groupings, star


# -- the park map --------------------------------------------------------


def test_park_map_has_all_canon_nodes():
    for node in ("park", "entrance", "builder", "star", "groupings"):
        assert node in PARK_MAP, f"canon node {node!r} missing from the park map"


def test_map_modules_importable():
    import importlib

    for node in ("entrance", "star", "groupings"):
        mod = PARK_MAP[node]
        importlib.import_module(mod)


def test_build_crew_names_builder_organs():
    crew = entrance.build_crew()
    assert "levi.alpha.reason" in crew["understood_by"]
    assert "generators" in crew["built_by"]
    assert "levi.universe.entrance.enter" in crew["admitted_by"]


# -- the entrance ----------------------------------------------------------


def _fleet():
    from levi.revival.omega.nexus import SOURCE_LOCAL, Provider

    return [
        Provider(
            name="levi-local",
            source=SOURCE_LOCAL,
            kinds=frozenset({"chat"}),
            cost=1,
            quality=0.6,
        )
    ]


def test_enter_admits_task_through_real_organs():
    session = entrance.enter("Should I take an umbrella today?", providers=_fleet())
    assert session.entrance == "omega"
    assert session.built_by == "alpha"
    assert session.answer, "the verdict must carry a real answer"
    assert session.task_type in (
        "yes-no",
        "information",
        "instruction",
        "fragment",
        "open",
        "unknown",
    )
    assert session.top_provider == "levi-local"
    assert session.substrate, "substrate must be stated honestly"
    assert session.limits, "honest limits must travel with the session"


def test_enter_explicit_kinds_reach_router():
    from levi.revival.omega.nexus import SOURCE_LOCAL, Provider

    fleet = [
        Provider(
            name="levi-local",
            source=SOURCE_LOCAL,
            kinds=frozenset({"code"}),
            cost=1,
            quality=0.6,
        )
    ]
    session = entrance.enter("hello", providers=fleet, kinds=frozenset({"code"}))
    assert session.top_provider == "levi-local"
    assert not any("generic conversation" in c for c in session.caveats)


def test_enter_default_kinds_caveat_reported():
    session = entrance.enter("hello", providers=_fleet())
    assert any("chat" in c for c in session.caveats)


def test_enter_no_providers_uses_reported_fallback():
    session = entrance.enter("hello")
    assert session.top_provider == "levi-local"
    assert any("fallback fleet" in c for c in session.caveats)


def test_enter_refuses_empty_task():
    with pytest.raises(entrance.EntranceError):
        entrance.enter("   ")


def test_session_summary_is_json_safe():
    session = entrance.enter("Should I take an umbrella today?", providers=_fleet())
    json.dumps(session.summary())


# -- the star ---------------------------------------------------------------


def test_star_is_a_role_not_a_name():
    s = star.current_star()
    assert s.role == "the star"
    assert "a role, not a name" in s.essence


def test_star_declared_filling_is_canon():
    s = star.current_star()
    f = s.filled_by
    assert f.persona == "Rex"
    assert f.declared_by == "Chauncey"
    assert "LEXICON" in f.canon_ref


def test_star_proposal_never_installs():
    s = star.current_star()
    before = (s.filled_by.product, s.filled_by.persona)
    rec = s.propose_filling("some-product", "SomePersona", proposed_by="tester")
    assert rec["status"].startswith("proposed")
    assert (s.filled_by.product, s.filled_by.persona) == before
    assert len(s.proposals) == 1


def test_star_seal_gate_only_chauncey():
    s = star.current_star()
    new = star.Filling(
        product="x", persona="y", declared_by="Zed", declared_on="2026-09-21"
    )
    with pytest.raises(star.StarError):
        s.seal_filling(new, sealed_by="Zed")
    sealed = s.seal_filling(new, sealed_by="Chauncey")
    assert sealed.persona == "y"


def test_star_filling_rejects_blanks():
    with pytest.raises(star.StarError):
        star.Filling(
            product="", persona="Rex", declared_by="Chauncey", declared_on="2026-09-21"
        )


# -- the groupings registry --------------------------------------------------


def test_grouping_forms_are_the_five():
    assert groupings.GROUPING_FORMS == ("hive", "school", "pack", "herd", "flock")


def test_hive_is_the_builders_grouping():
    essence = groupings.FORM_ESSENCES["hive"]["essence"]
    assert "builders" in essence
    assert "Inside the Legion, not the whole" in essence


def test_silent_forms_are_honest_not_invented():
    for form in ("school", "pack", "herd", "flock"):
        assert "awaiting Chauncey's word" in groupings.FORM_ESSENCES[form]["essence"]


def test_propose_records_never_declares():
    reg = groupings.GroupingRegistry()
    g = reg.propose(
        name="night-watch",
        form="pack",
        essence="the ones who keep the line after dark",
        proposed_by="tester",
    )
    assert g.status == "proposed"
    assert "not canon" in g.standing_note
    assert reg.declared == []


def test_declare_gate_only_chauncey():
    reg = groupings.GroupingRegistry()
    g = reg.propose(name="night-watch", form="pack", proposed_by="tester")
    with pytest.raises(groupings.GroupingError):
        reg.declare(g, declared_by="tester")
    d = reg.declare(g, declared_by="Chauncey")
    assert d.status == "declared"
    assert len(reg.declared) == 1


def test_sealed_claims_refused():
    reg = groupings.GroupingRegistry()
    with pytest.raises(groupings.GroupingError):
        reg.propose(name="the eleven", form="hive", proposed_by="tester")
    with pytest.raises(groupings.GroupingError):
        reg.propose(
            name="dawn-choir",
            form="flock",
            essence="a sealed original of the first order",
            proposed_by="tester",
        )


def test_unknown_form_refused():
    reg = groupings.GroupingRegistry()
    with pytest.raises(groupings.GroupingError):
        reg.propose(name="x", form="swarm", proposed_by="tester")


def test_propose_requires_provenance():
    reg = groupings.GroupingRegistry()
    with pytest.raises(groupings.GroupingError):
        reg.propose(name="night-watch", form="pack", proposed_by="")


def test_registry_round_trips_through_jsonl(tmp_path):
    path = tmp_path / "groupings.jsonl"
    reg = groupings.GroupingRegistry(path)
    reg.propose(name="night-watch", form="pack", proposed_by="tester")
    declared = reg.propose(name="day-forge", form="hive", proposed_by="tester")
    reg.declare(declared, declared_by="Chauncey")
    reg.save()

    reg2 = groupings.GroupingRegistry(path)
    assert [g.name for g in reg2.proposed] == ["night-watch"]
    assert [g.name for g in reg2.declared] == ["day-forge"]
    assert reg2.declared[0].status == "declared"


def test_registry_describe_carries_sealed_law():
    reg = groupings.GroupingRegistry()
    d = reg.describe()
    assert "eleven" in d["sealed_law"]
    assert len(d["forms"]) == 5
    json.dumps(d)


# ---- brain-voice continuity through the entrance -------------------------


_FAKE_CONTINUATION = "umbrella rain clouds wet garbled brain echo"


def _patch_brain_voice(monkeypatch):
    """Give the Reasoner a running brain with a fixed, labeled output.

    Monkeypatched, not torch-gated: deterministic on every host — this
    exercises the THREADING of the evidence trail through the entrance,
    not the weights. Mirrors the omega-reasoning battery's patch.
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


def _patch_no_brain(monkeypatch):
    from levi.alpha import reason as alpha_reason

    monkeypatch.setattr(
        alpha_reason.Reasoner,
        "_load_brain_inference",
        lambda self: (None, "test: brain disabled"),
    )


def test_enter_threads_brain_voice_when_brain_runs(monkeypatch):
    _patch_brain_voice(monkeypatch)
    session = entrance.enter("Should I take an umbrella today?", providers=_fleet())
    # verbatim, as it ran — the evidence trail, not reasoning
    assert session.brain_voice == _FAKE_CONTINUATION
    assert session.summary()["brain_voice"] == _FAKE_CONTINUATION
    # the verdict still came from a rules stance, never the brain-voice
    assert session.verdict.get("chosen") != "brain-voice"


def test_enter_brain_voice_absent_when_brain_does_not_run(monkeypatch):
    _patch_no_brain(monkeypatch)
    session = entrance.enter("Should I take an umbrella today?", providers=_fleet())
    # no trail is reported as absent, never invented
    assert session.brain_voice is None
    assert session.summary()["brain_voice"] is None


def test_enter_cli_reports_brain_voice_labeled(monkeypatch, capsys):
    from argparse import Namespace

    from levi.universe import cli as universe_cli

    _patch_brain_voice(monkeypatch)
    args = Namespace(
        universe_cmd="enter",
        task="Should I take an umbrella today?",
        mode="balanced",
        kinds="",
        needs_local=False,
    )
    assert universe_cli.cmd_universe(args) == 0
    out = capsys.readouterr().out
    assert "brain-voice (heard, never obeyed):" in out
    assert "raw continuation, not reasoning:" in out
    assert _FAKE_CONTINUATION in out


def test_enter_cli_silent_about_brain_voice_when_none(monkeypatch, capsys):
    from argparse import Namespace

    from levi.universe import cli as universe_cli

    _patch_no_brain(monkeypatch)
    args = Namespace(
        universe_cmd="enter",
        task="Should I take an umbrella today?",
        mode="balanced",
        kinds="",
        needs_local=False,
    )
    assert universe_cli.cmd_universe(args) == 0
    out = capsys.readouterr().out
    # absent is never invented — the console stays silent about the trail
    assert "brain-voice" not in out
