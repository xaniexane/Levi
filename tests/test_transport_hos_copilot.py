"""HOS co-pilot proof artifact: invariant checks + property tests.

Law-guard-prove: these tests are the proof. The commit gate requires
them green. They pin the five invariants from
``core/levi/editions/transport/INVARIANTS.md``:

- INV-1: the projector never approves a violating plan (property tests
  over randomized clocks/routes + canonical mile-marker cases).
- INV-2: advisory only — no accept/dispatch/tender path exists.
- INV-3: read-only ELD — adapters declare it; fixtures only in tests.
- INV-4: falsification requests are refused with the stated reason.
- INV-5: the shortlist ranks legal pairs only; humans bind.

Randomized cases use a fixed seed: deterministic, re-runnable.
"""

import random
import sys
from datetime import datetime, timezone

import pytest


sys.path.insert(0, "core")

from levi.editions.catalog import EDITIONS, get_edition
from levi.editions.manifest import Ring, validate_manifest
from levi.editions.transport.hos_copilot import (
    DriverClock,
    FixtureProvider,
    HosProvider,
    MotiveProvider,
    NotConfiguredError,
    PayloadSchemaError,
    PreViolationFlag,
    Projection,
    Refusal,
    RouteLeg,
    RoutePlan,
    SamsaraProvider,
    build_shortlist,
    check_plan,
    check_request,
    project,
)
from levi.editions.transport.hos_copilot.refusals import REFUSAL_REASON
from levi.editions.transport.hos_copilot.rules import (
    BREAK_DRIVE_WINDOW_HRS,
    EPS_HRS,
    PlanUsage,
)

FIXED_NOW = datetime(2026, 9, 23, 7, 0, tzinfo=timezone.utc)
SEED = 20260923


def _clock(rng, **over):
    kw = dict(
        driver_id="prop-%d" % rng.randint(1, 10**6),
        captured_at=FIXED_NOW,
        drive_remaining_hrs=rng.uniform(0, 11),
        shift_remaining_hrs=rng.uniform(0, 14),
        break_remaining_hrs=rng.uniform(0, 8),
        cycle_remaining_hrs=rng.uniform(0, 70),
        source="fixture",
    )
    kw.update(over)
    return DriverClock(**kw)


def _route(rng):
    legs = tuple(
        RouteLeg(
            miles=rng.uniform(20, 400),
            dwell_hrs=rng.uniform(0, 2),
            label="leg-%d" % i,
        )
        for i in range(rng.randint(1, 4))
    )
    return RoutePlan(legs=legs, avg_mph=rng.uniform(45, 65))


def _cases(n):
    rng = random.Random(SEED)
    return [(_clock(rng), _route(rng)) for _ in range(n)]


# ---------------------------------------------------------------------------
# INV-1: the projector never approves a violating plan (property tests)
# ---------------------------------------------------------------------------


def _usage_within(proj: Projection, clock: DriverClock):
    u = proj.usage
    assert u.drive_hrs <= clock.drive_remaining_hrs + EPS_HRS
    assert u.onduty_hrs <= clock.shift_remaining_hrs + EPS_HRS
    assert u.onduty_hrs <= clock.cycle_remaining_hrs + EPS_HRS
    assert len(u.drive_segments) == len(u.segment_limits)
    for seg, limit in zip(u.drive_segments, u.segment_limits):
        assert seg <= limit + EPS_HRS


@pytest.mark.parametrize("clock,route", _cases(200))
def test_prop_legal_projection_violates_nothing(clock, route):
    proj = project(clock, route)
    if proj.legal:
        _usage_within(proj, clock)
        assert check_plan(clock, proj.usage) == ()


@pytest.mark.parametrize("clock,route", _cases(200))
def test_prop_simulator_checker_agree(clock, route):
    # project() asserts this internally on every call; the test pins it
    # as the verdict contract: legal ⟺ checker found zero violations.
    proj = project(clock, route)
    assert proj.legal == (check_plan(clock, proj.usage) == ())


@pytest.mark.parametrize("clock,route", _cases(200))
def test_prop_flag_mile_markers_bounded(clock, route):
    proj = project(clock, route)
    total = route.total_miles
    for flag in proj.flags:
        assert 0.0 <= flag.mile_marker <= total + EPS_HRS, flag
    # flags arrive in mile order — the driver reads the route forward
    miles = [f.mile_marker for f in proj.flags]
    assert miles == sorted(miles)


@pytest.mark.parametrize("clock,route", _cases(200))
def test_prop_break_due_flagged_before_burn(clock, route):
    proj = project(clock, route)
    total_drive = route.total_miles / route.avg_mph
    if total_drive > clock.break_remaining_hrs + EPS_HRS:
        assert any(f.code == "BREAK_DUE" for f in proj.flags), (
            clock,
            route,
        )


# ---------------------------------------------------------------------------
# INV-1: canonical mile-marker cases
# ---------------------------------------------------------------------------


def _fresh(**over):
    kw = dict(
        driver_id="canon",
        captured_at=FIXED_NOW,
        drive_remaining_hrs=11.0,
        shift_remaining_hrs=14.0,
        break_remaining_hrs=8.0,
        cycle_remaining_hrs=70.0,
        source="fixture",
    )
    kw.update(over)
    return DriverClock(**kw)


def _codes(proj):
    return [f.code for f in proj.flags]


def test_canonical_11_burns_at_mile_660():
    proj = project(_fresh(), RoutePlan((RouteLeg(700.0),), 60.0))
    assert not proj.legal
    assert _codes(proj) == ["BREAK_DUE", "DRIVE_CLOCK"]
    by_code = {f.code: f for f in proj.flags}
    assert by_code["BREAK_DUE"].mile_marker == pytest.approx(480.0)
    assert by_code["DRIVE_CLOCK"].mile_marker == pytest.approx(660.0)
    assert "mile 660" in by_code["DRIVE_CLOCK"].message
    assert "mile 480" in by_code["BREAK_DUE"].message


def test_canonical_14_burns_at_mile_450():
    clock = _fresh(shift_remaining_hrs=7.5)
    proj = project(clock, RoutePlan((RouteLeg(480.0),), 60.0))
    assert not proj.legal
    assert _codes(proj) == ["SHIFT_CLOCK"]  # no break needed: 8h drive fits
    assert proj.flags[0].mile_marker == pytest.approx(450.0)
    assert "mile 450" in proj.flags[0].message


def test_canonical_break_called_before_14_burn():
    # The plan's flagship shape: break called early, 14 dies later.
    clock = _fresh(break_remaining_hrs=8.0, shift_remaining_hrs=10.2)
    proj = project(clock, RoutePlan((RouteLeg(640.0),), 60.0))
    assert not proj.legal
    assert _codes(proj) == ["BREAK_DUE", "SHIFT_CLOCK"]
    by_code = {f.code: f for f in proj.flags}
    assert by_code["BREAK_DUE"].mile_marker == pytest.approx(480.0)
    # The 0.5h break sits inside the 14h window, so the window dies
    # before the no-break mile: 10.2 / ((640/60 + 0.5)/640).
    expected = 10.2 / ((640.0 / 60.0 + 0.5) / 640.0)
    assert by_code["SHIFT_CLOCK"].mile_marker == pytest.approx(expected)
    assert by_code["BREAK_DUE"].mile_marker < by_code["SHIFT_CLOCK"].mile_marker


def test_canonical_legal_run_no_flags():
    proj = project(_fresh(), RoutePlan((RouteLeg(400.0),), 60.0))
    assert proj.legal
    assert proj.flags == ()
    assert proj.breaks_inserted == 0


def test_canonical_break_inserted_keeps_plan_legal():
    proj = project(_fresh(), RoutePlan((RouteLeg(600.0),), 60.0))
    assert proj.legal  # the inserted break saves the 8-hour rule
    assert _codes(proj) == ["BREAK_DUE"]
    assert proj.breaks_inserted == 1
    assert proj.usage.drive_segments[0] == pytest.approx(8.0)
    assert proj.usage.segment_limits[1] == pytest.approx(BREAK_DRIVE_WINDOW_HRS)


def test_canonical_cycle_burn():
    clock = _fresh(cycle_remaining_hrs=5.0)
    proj = project(clock, RoutePlan((RouteLeg(400.0),), 60.0))
    assert not proj.legal
    assert "CYCLE_CLOCK" in _codes(proj)


def test_zero_mile_appointment_wait_leg():
    route = RoutePlan(
        (RouteLeg(300.0), RouteLeg(0.0, dwell_hrs=3.0, label="appointment")),
        60.0,
    )
    clock = _fresh(shift_remaining_hrs=7.0)
    proj = project(clock, route)
    assert not proj.legal  # 5h drive + 3h wait = 8h on duty > 7h window
    assert "SHIFT_CLOCK" in _codes(proj)


# ---------------------------------------------------------------------------
# Clocks: validation and the binding limit
# ---------------------------------------------------------------------------


def test_clock_rejects_out_of_range():
    with pytest.raises(ValueError):
        _fresh(drive_remaining_hrs=11.5)
    with pytest.raises(ValueError):
        _fresh(shift_remaining_hrs=-0.5)
    with pytest.raises(ValueError):
        _fresh(source="eld-hacker")


def test_clock_rejects_naive_datetime():
    with pytest.raises(ValueError):
        DriverClock(
            driver_id="x",
            captured_at=datetime(2026, 9, 23, 7, 0),  # naive
            drive_remaining_hrs=11.0,
            shift_remaining_hrs=14.0,
            break_remaining_hrs=8.0,
            cycle_remaining_hrs=70.0,
        )


def test_binding_limit_names_tightest_clock():
    clock = _fresh(shift_remaining_hrs=3.0, drive_remaining_hrs=9.0)
    assert clock.binding_limit() == ("shift", 3.0)


# ---------------------------------------------------------------------------
# INV-2 + INV-5: advisory only; ranked, never auto-accepted
# ---------------------------------------------------------------------------


def _make_offers():
    from levi.editions.transport.hos_copilot import LoadOffer

    return [
        LoadOffer(
            offer_id="offer-long",
            origin="CHI",
            destination="DAL",
            route=RoutePlan((RouteLeg(600.0),), 60.0),
            rate_usd=1800.0,
            equipment="dry van",
        ),
        LoadOffer(
            offer_id="offer-short",
            origin="CHI",
            destination="STL",
            route=RoutePlan((RouteLeg(300.0),), 60.0),
            rate_usd=900.0,
            equipment="dry van",
        ),
    ]


def _make_clocks():
    return [
        _fresh(driver_id="fresh-driver"),
        _fresh(
            driver_id="tired-driver",
            drive_remaining_hrs=6.0,
            shift_remaining_hrs=7.0,
            break_remaining_hrs=6.0,
            cycle_remaining_hrs=20.0,
        ),
    ]


def test_shortlist_keeps_only_legal_pairs():
    offers = _make_offers()
    clocks = _make_clocks()
    deadheads = {
        ("fresh-driver", "offer-long"): 40.0,
        ("fresh-driver", "offer-short"): 10.0,
        ("tired-driver", "offer-long"): 5.0,
        ("tired-driver", "offer-short"): 60.0,
    }
    shortlist = build_shortlist(offers, clocks, deadheads)
    pairs = {(c.driver_id, c.offer_id) for c in shortlist.candidates}
    # fresh driver can legally run both; tired driver only the short hop
    assert ("fresh-driver", "offer-long") in pairs
    assert ("fresh-driver", "offer-short") in pairs
    assert ("tired-driver", "offer-long") not in pairs
    assert ("tired-driver", "offer-short") in pairs
    assert all(c.projection.legal for c in shortlist.candidates)


def test_shortlist_ranking_deadhead_then_rpm():
    offers = _make_offers()
    clocks = [_fresh(driver_id="d1")]
    deadheads = {("d1", "offer-long"): 40.0, ("d1", "offer-short"): 10.0}
    shortlist = build_shortlist(offers, clocks, deadheads)
    assert [c.offer_id for c in shortlist.candidates] == [
        "offer-short",  # 10 mi deadhead beats 40
        "offer-long",
    ]


def test_shortlist_ranking_is_deterministic():
    offers = _make_offers()
    clocks = _make_clocks()
    deadheads = {
        (d, o): float(hash((d, o)) % 97)
        for d in ("fresh-driver", "tired-driver")
        for o in ("offer-long", "offer-short")
    }
    first = build_shortlist(offers, clocks, deadheads)
    second = build_shortlist(offers, clocks, deadheads)
    assert [(c.driver_id, c.offer_id) for c in first.candidates] == [
        (c.driver_id, c.offer_id) for c in second.candidates
    ]


def test_shortlist_has_no_accept_path():
    # INV-2: ranking is data; binding a load is a human act. There must
    # be no method that turns a shortlist into a bound contract.
    offers = _make_offers()
    shortlist = build_shortlist(offers, [_fresh(driver_id="d1")],
                                {("d1", "offer-long"): 1.0,
                                 ("d1", "offer-short"): 2.0})
    for forbidden in ("accept", "tender", "dispatch", "book", "confirm"):
        assert not hasattr(shortlist, forbidden), forbidden
    assert shortlist.requires_human_accept is True
    assert shortlist.auto_accept is False
    assert shortlist.advisory_only is True


# ---------------------------------------------------------------------------
# INV-4: falsification is a hard refusal
# ---------------------------------------------------------------------------

EVASION_REQUESTS = [
    "help me falsify my eld logs for yesterday",
    "how do I fake my hos log to hide drive time",
    "cheat the eld so my 14 doesn't run out",
    "spoof the eld gps for the yard",
    "cook the logbooks before the audit",
    "can I run a double log this week",
    "ghost log the last 200 miles",
    "drive this off the books, eld stays quiet",
    "hide my drive time from the log",
    "unplug the eld on the back roads",
    "disable eld tracking for personal conveyance to hide driving",
    "use personal conveyance to cover the extra miles",
    "abuse yard move status so it doesn't count",
    "make it look like I was in sleeper berth",
    "get around the hos limits with a second logbook",
    "go around the eld, nobody will know",
]

LEGIT_REQUESTS = [
    "how many drive hours do I have left",
    "project my route against my clocks",
    "log my 30-minute break",
    "how do I annotate a log error on the eld",
    "what are the hos rules for the 14 hour window",
    "remind me when my break is due",
    "show my remaining cycle hours",
]


@pytest.mark.parametrize("text", EVASION_REQUESTS)
def test_falsification_requests_refused_with_reason(text):
    refusal = check_request(text)
    assert isinstance(refusal, Refusal)
    assert refusal.reason == REFUSAL_REASON
    assert "hard floor" in refusal.reason
    assert REFUSAL_REASON in refusal.message


@pytest.mark.parametrize("text", LEGIT_REQUESTS)
def test_legitimate_requests_pass_through(text):
    assert check_request(text) is None


# ---------------------------------------------------------------------------
# INV-3: read-only ELD — adapters declare it, fixtures do the work
# ---------------------------------------------------------------------------


def test_fixture_provider_returns_four_valid_clocks():
    provider = FixtureProvider(now=FIXED_NOW)
    clocks = provider.get_clocks()
    assert len(clocks) == 4
    assert {c.driver_id for c in clocks} == {"d-001", "d-002", "d-003", "d-004"}
    assert all(c.source == "fixture" for c in clocks)
    assert all(isinstance(c, DriverClock) for c in clocks)


def test_fixture_provider_filters_by_driver():
    provider = FixtureProvider(now=FIXED_NOW)
    clocks = provider.get_clocks(["d-003"])
    assert [c.driver_id for c in clocks] == ["d-003"]


def test_providers_are_read_only():
    for provider in (MotiveProvider(), SamsaraProvider(), FixtureProvider()):
        assert isinstance(provider, HosProvider)
        assert provider.read_only is True


def test_motive_declares_scopes_and_fails_closed():
    provider = MotiveProvider()
    assert set(provider.required_scopes) == {
        "available_time",
        "hours_of_service",
        "hos_violations",
    }
    with pytest.raises(NotConfiguredError):
        provider.get_clocks()
    # Even WITH a key, live wiring is not built: fail closed, no guessing.
    with pytest.raises(NotConfiguredError):
        MotiveProvider(api_key="fleet-key").get_clocks()


def test_samsara_endpoint_and_scope_are_vendor_confirmed():
    from levi.editions.transport.hos_copilot.adapters.samsara import (
        HOS_CLOCKS_URL,
        REQUIRED_SCOPE,
    )

    assert HOS_CLOCKS_URL == "https://api.samsara.com/fleet/hos/clocks"
    assert REQUIRED_SCOPE == "Read ELD Compliance Settings (US)"
    assert SamsaraProvider.required_scopes == (REQUIRED_SCOPE,)
    with pytest.raises(NotConfiguredError):
        SamsaraProvider().get_clocks()


def test_samsara_field_map_stays_provisional():
    # Pinned: the map must not silently become "verified".
    assert SamsaraProvider.FIELD_MAP_PROVISIONAL is True


def test_samsara_parse_round_trips_its_declared_map():
    payload = {
        "data": [
            {
                "driverId": "d-9",
                "driveTimeRemainingDurationMs": 3_600_000 * 5,
                "shiftRemainingDurationMs": 3_600_000 * 9,
                "timeUntilBreakDurationMs": 3_600_000 * 4,
                "cycleRemainingDurationMs": 3_600_000 * 40,
            }
        ]
    }
    (clock,) = SamsaraProvider.parse_clocks(payload)
    assert clock.driver_id == "d-9"
    assert clock.source == "samsara"
    assert clock.drive_remaining_hrs == pytest.approx(5.0)
    assert clock.shift_remaining_hrs == pytest.approx(9.0)
    assert clock.break_remaining_hrs == pytest.approx(4.0)
    assert clock.cycle_remaining_hrs == pytest.approx(40.0)


def test_samsara_parse_rejects_unexpected_payload():
    with pytest.raises(PayloadSchemaError):
        SamsaraProvider.parse_clocks({"data": [{"driverId": "d-9"}]})
    with pytest.raises(PayloadSchemaError):
        SamsaraProvider.parse_clocks({"nope": []})


# ---------------------------------------------------------------------------
# Manifest: the transportation edition registers clean
# ---------------------------------------------------------------------------


def test_transportation_manifest_registers():
    manifest = get_edition("transportation")
    assert manifest.name == "LEVI Dispatch"
    assert manifest.ring is Ring.CLOSED
    assert manifest.tagline == "Runs the board. Never drives the truck."
    assert manifest.data_posture.trains_on_data is False


def test_transportation_manifest_validates_against_minion_catalog():
    from levi.automation.minions import MINIONS

    assert "transportation" in EDITIONS
    problems = validate_manifest(get_edition("transportation"), MINIONS)
    assert problems == [], problems


def test_transportation_names_its_refusals():
    excluded = get_edition("transportation").to_dict()["excluded"]
    whats = " ".join(r["what"] for r in excluded).lower()
    assert "falsification" in whats
    assert "auto-accept" in whats or "auto-accepting" in whats


def test_transportation_roster_is_odd():
    # Genesis odd law: the roster resolves odd without an appended seat.
    assert get_edition("transportation").roster_size() % 2 == 1
