"""Sourcing-law tests for the Nexus revival: levi-local + levi-si-cloud only.

References are NEVER operational sources — they must come back
ineligible in every mode, with a reason in LEVI's voice. The two lawful
sources route normally, and offline mode stays deny-closed.
"""

import pytest

from levi.revival.omega import nexus as nx


def _all_sources():
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


# ---- sourcing law ----


def test_only_three_sources_exist():
    assert nx.SOURCES == frozenset({"levi-local", "levi-si-cloud", "reference"})
    assert nx.SOURCE_LOCAL == "levi-local"
    assert nx.SOURCE_CLOUD == "levi-si-cloud"
    assert nx.SOURCE_REFERENCE == "reference"


def test_default_source_is_reference():
    p = nx.Provider(name="someone-elses-model", kinds=frozenset({"chat"}))
    assert p.source == "reference"
    assert not p.local


def test_reference_never_eligible_in_any_mode():
    task = nx.Task(kinds=frozenset({"chat", "code", "vision"}), label="do everything")
    for mode in nx.MODES:
        routes = nx.route(task, _all_sources(), mode=mode)
        ref = next(r for r in routes if r.provider == "rival-a")
        assert not ref.eligible, f"reference eligible in mode {mode}"
        assert ref.confidence == 0.0
        # the reason speaks in LEVI's voice
        assert any(
            "reference-only" in reason and "never an operational source" in reason
            for reason in ref.reasons
        ), f"mode {mode}: {ref.reasons}"
        # references sort after every eligible provider
        assert routes.index(ref) >= len([r for r in routes if r.eligible])


def test_reference_never_eligible_even_when_best_on_paper():
    # rival-a is cheaper AND higher quality AND covers all kinds:
    # still never operational.
    task = nx.Task(kinds=frozenset({"chat", "code", "vision"}))
    for mode in ("fast", "balanced", "deep", "offline"):
        routes = nx.route(task, _all_sources(), mode=mode)
        ref = next(r for r in routes if r.provider == "rival-a")
        assert not ref.eligible and ref.confidence == 0.0


def test_reference_alone_routes_nobody():
    task = nx.Task(kinds=frozenset({"chat"}))
    providers = [
        nx.Provider(name="rival-a", kinds=frozenset({"chat"})),
        nx.Provider(name="rival-b", kinds=frozenset({"chat"})),
    ]
    routes = nx.route(task, providers)
    assert routes  # doesn't raise
    assert all(not r.eligible and r.confidence == 0.0 for r in routes)


# ---- the two lawful sources ----


def test_local_property_tracks_source():
    assert nx.Provider(name="a", source="levi-local").local is True
    assert nx.Provider(name="b", source="levi-si-cloud").local is False
    assert nx.Provider(name="c", source="reference").local is False


def test_local_property_is_read_only():
    p = nx.Provider(name="a", source="levi-local")
    with pytest.raises(AttributeError):
        p.local = False  # frozen dataclass + property: no assignment


def test_levi_si_cloud_is_operational_in_online_modes():
    task = nx.Task(kinds=frozenset({"vision"}))
    routes = nx.route(task, _all_sources())
    cloud = next(r for r in routes if r.provider == "levi-si-cloud")
    assert cloud.eligible
    # only the cloud covers vision, so it wins balanced
    assert routes[0].provider == "levi-si-cloud"


def test_levi_local_vs_cloud_both_route():
    task = nx.Task(kinds=frozenset({"chat"}), label="both could serve")
    routes = nx.route(task, _all_sources(), mode="balanced")
    eligible = [r.provider for r in routes if r.eligible]
    assert set(eligible) == {"levi-local", "levi-si-cloud"}


def test_cloud_says_it_is_the_only_remote_source():
    task = nx.Task(kinds=frozenset({"chat"}))
    routes = nx.route(task, _all_sources())
    cloud = next(r for r in routes if r.provider == "levi-si-cloud")
    assert any("LEVI SI Cloud" in reason for reason in cloud.reasons)


# ---- offline: deny-closed ----


def test_offline_excludes_cloud_and_references():
    task = nx.Task(kinds=frozenset({"chat"}), label="private")
    routes = nx.route(task, _all_sources(), mode="offline")
    for r in routes:
        if r.provider == "levi-local":
            assert r.eligible
        else:
            assert not r.eligible and r.confidence == 0.0


def test_offline_with_no_local_says_so():
    task = nx.Task(kinds=frozenset({"chat"}))
    providers = [
        nx.Provider(name="levi-si-cloud", source="levi-si-cloud"),
        nx.Provider(name="rival-a"),
    ]
    routes = nx.route(task, providers, mode="offline")
    assert all(not r.eligible for r in routes)
    local_lines = [r for r in routes if r.provider == "levi-si-cloud"]
    assert any("LEVI-local only" in reason for reason in local_lines[0].reasons)


# ---- validation ----


def test_invalid_source_rejected():
    with pytest.raises(ValueError, match="source must be one of"):
        nx.Provider(name="rogue", source="rogue-cloud")


def test_empty_source_rejected():
    with pytest.raises(ValueError, match="source must be one of"):
        nx.Provider(name="rogue", source="")


def test_name_cost_quality_validation_kept():
    with pytest.raises(ValueError):
        nx.Provider(name="", source="levi-local")
    with pytest.raises(ValueError):
        nx.Provider(name="x", source="levi-local", cost=11)
    with pytest.raises(ValueError):
        nx.Provider(name="x", source="levi-local", quality=1.5)


# ---- explain ----


def test_explain_marks_reference_skip():
    task = nx.Task(kinds=frozenset({"chat"}))
    text = nx.explain(nx.route(task, _all_sources()))
    assert "[SKIP] rival-a" in text
    assert "reference-only" in text
    assert "[OK ]" in text and "levi-local" in text
