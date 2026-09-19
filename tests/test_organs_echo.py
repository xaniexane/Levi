"""Hermetic tests for the Echo organ (core/levi/organs/echo.py).

Covers the explore-space wiring: DNAStrip validation, interpenetrate
(cross-strand only, risk-ceiling inheritance, deterministic ordering,
fail-closed on malformed input), explore_space (branches +
interpenetrations together, bounded cap), the interpenetration renderer,
and spot-checks that the original run_echo/format_echo behavior is
unchanged.

No network, no HOME writes, deterministic.
"""

import pytest

from levi.organs.echo import (
    DNAStrip,
    Interpenetration,
    explore_space,
    format_echo,
    format_interpenetrations,
    interpenetrate,
    run_echo,
)


def _strips():
    return [
        DNAStrip(
            id="s-levi",
            strand="levi",
            patterns=["adaptive memory", "persona routing"],
            risk="low",
        ),
        DNAStrip(
            id="s-lwp",
            strand="lwp",
            patterns=["direction/phase/power", "twelve modes"],
            risk="high",
        ),
        DNAStrip(
            id="s-factory",
            strand="factory",
            patterns=["build pipeline"],
            risk="medium",
        ),
    ]


class TestDNAStrip:
    def test_bad_strand_raises(self):
        with pytest.raises(ValueError):
            DNAStrip(id="x", strand="omega", patterns=["p"], risk="low")

    def test_bad_risk_raises(self):
        with pytest.raises(ValueError):
            DNAStrip(id="x", strand="levi", patterns=["p"], risk="extreme")

    def test_bad_patterns_raise(self):
        with pytest.raises(ValueError):
            DNAStrip(id="x", strand="levi", patterns="not-a-list", risk="low")
        with pytest.raises(ValueError):
            DNAStrip(id="x", strand="levi", patterns=["ok", 42], risk="low")
        with pytest.raises(ValueError):
            DNAStrip(id="x", strand="levi", patterns=["ok", "  "], risk="low")

    def test_bad_id_raises(self):
        with pytest.raises(ValueError):
            DNAStrip(id="", strand="levi", patterns=["p"], risk="low")

    def test_empty_patterns_allowed(self):
        s = DNAStrip(id="x", strand="levi", patterns=[], risk="low")
        assert s.patterns == []


class TestRiskCeiling:
    def test_low_times_high_is_high(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="high"),
            ]
        )
        assert recs, "expected at least one record"
        assert all(r.risk == "high" for r in recs)

    def test_medium_times_medium_is_medium(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="medium"),
                DNAStrip(id="b", strand="factory", patterns=["p2"], risk="medium"),
            ]
        )
        assert all(r.risk == "medium" for r in recs)

    def test_low_times_medium_is_medium(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="factory", patterns=["p2"], risk="medium"),
            ]
        )
        assert all(r.risk == "medium" for r in recs)

    def test_low_times_low_stays_low(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="low"),
            ]
        )
        assert all(r.risk == "low" for r in recs)


class TestCrossStrandOnly:
    def test_same_strand_pairs_never_combine(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="levi", patterns=["p2"], risk="low"),
                DNAStrip(id="c", strand="levi", patterns=["p3"], risk="high"),
            ]
        )
        assert recs == []

    def test_different_strands_pair_both_orders(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="low"),
            ]
        )
        pairs = {(r.strip_a, r.strip_b) for r in recs}
        assert pairs == {("a", "b"), ("b", "a")}
        assert recs[0].fused == '"p1" × "p2"'
        assert recs[1].fused == '"p2" × "p1"'


class TestDeterminismAndInput:
    def test_same_input_identical_output(self):
        assert interpenetrate(_strips()) == interpenetrate(_strips())

    def test_input_order_does_not_matter(self):
        fwd = interpenetrate(_strips())
        rev = interpenetrate(list(reversed(_strips())))
        assert fwd == rev

    def test_output_sorted_by_strip_ids_then_patterns(self):
        recs = interpenetrate(_strips())
        keys = [(r.strip_a, r.strip_b, r.fused) for r in recs]
        assert keys == sorted(keys)

    def test_empty_strips_returns_empty(self):
        assert interpenetrate([]) == []

    def test_strip_with_no_patterns_contributes_nothing(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=[], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="low"),
            ]
        )
        assert recs == []

    def test_malformed_input_raises(self):
        with pytest.raises(ValueError):
            interpenetrate("not-a-list")
        with pytest.raises(ValueError):
            interpenetrate([{"id": "a"}])
        with pytest.raises(ValueError):
            interpenetrate([None])


class TestExploreSpace:
    def test_returns_branches_and_interpenetrations(self):
        out = explore_space("a seed", _strips(), cycles=3)
        assert out["organ"] == "echo"
        assert out["seed"] == "a seed"
        assert len(out["branches"]) == 3
        assert isinstance(out["insight"], str) and out["insight"]
        assert isinstance(out["interpenetrations"], list)
        assert out["interpenetrations"], "expected cross-strand records"
        # record dicts carry the full shape
        for r in out["interpenetrations"]:
            assert set(r) == {"strip_a", "strip_b", "fused", "risk"}

    def test_branches_match_run_echo(self):
        out = explore_space("a seed", _strips(), cycles=3)
        base = run_echo("a seed", cycles=3)
        assert out["branches"] == base["branches"]
        assert out["insight"] == base["insight"]

    def test_cap_respected_with_many_patterns(self):
        strips = [
            DNAStrip(
                id="a",
                strand="levi",
                patterns=[f"pa{i}" for i in range(10)],
                risk="low",
            ),
            DNAStrip(
                id="b",
                strand="lwp",
                patterns=[f"pb{i}" for i in range(10)],
                risk="low",
            ),
        ]
        cycles = 2
        out = explore_space("seed", strips, cycles=cycles)
        assert len(out["interpenetrations"]) == cycles * 4
        # interpenetrate itself is unbounded — the cap lives in explore_space
        assert len(interpenetrate(strips)) > cycles * 4

    def test_zero_cycles_caps_to_zero(self):
        out = explore_space("seed", _strips(), cycles=0)
        assert out["interpenetrations"] == []
        assert len(out["branches"]) == 3  # run_echo semantics unchanged

    def test_empty_strips_ok(self):
        out = explore_space("seed", [], cycles=3)
        assert out["interpenetrations"] == []
        assert out["organ"] == "echo"

    def test_bad_cycles_raises(self):
        with pytest.raises(ValueError):
            explore_space("seed", _strips(), cycles=-1)
        with pytest.raises(ValueError):
            explore_space("seed", _strips(), cycles="3")


class TestFormatInterpenetrations:
    def test_renders_records(self):
        recs = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="high"),
            ]
        )
        text = format_interpenetrations(recs)
        assert "a × b" in text
        assert "risk=high" in text
        assert '"p1" × "p2"' in text

    def test_accepts_dict_forms(self):
        text = format_interpenetrations(
            [
                {
                    "strip_a": "a",
                    "strip_b": "b",
                    "fused": '"p1" × "p2"',
                    "risk": "low",
                }
            ]
        )
        assert '"p1" × "p2"' in text

    def test_empty_renders_explicit(self):
        text = format_interpenetrations([])
        assert "No interpenetrations" in text

    def test_malformed_raises(self):
        with pytest.raises(ValueError):
            format_interpenetrations("not-a-list")
        with pytest.raises(ValueError):
            format_interpenetrations([{"strip_a": "a"}])
        with pytest.raises(ValueError):
            format_interpenetrations([42])


class TestRunEchoUnchanged:
    """Spot-checks that the original branch exploration is untouched."""

    def test_branch_kinds_and_risks(self):
        out = run_echo("keep me honest", cycles=3)
        assert [b["kind"] for b in out["branches"]] == [
            "taken",
            "not_taken",
            "wild",
        ]
        assert [b["risk"] for b in out["branches"]] == [
            "medium",
            "low",
            "high",
        ]
        assert out["organ"] == "echo"

    def test_deterministic_and_fail_closed(self):
        assert run_echo("s") == run_echo("s")
        with pytest.raises(ValueError):
            run_echo("s", cycles=-1)
        with pytest.raises(ValueError):
            run_echo(123)

    def test_format_echo_still_renders(self):
        text = format_echo(run_echo("hello"))
        assert "=== Echo" in text
        assert "Insight:" in text

    def test_interpenetration_is_dataclass_record(self):
        r = interpenetrate(
            [
                DNAStrip(id="a", strand="levi", patterns=["p1"], risk="low"),
                DNAStrip(id="b", strand="lwp", patterns=["p2"], risk="low"),
            ]
        )[0]
        assert isinstance(r, Interpenetration)
