"""Tests for levi.methods entries 15-28 (deliberation, organization, pedagogy).

Hermetic: no network, no daemons, no user HOME writes (file-backed modules
get tmp_path stores). Deterministic: dates are injected, never read from
the wall clock inside assertions.

Run:  python3 -m pytest tests/test_methods_delib2.py -q
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.methods import (  # noqa: E402
    ach,
    deming,
    franklin,
    ivylee,
    monitorial,
    morphological,
    opsroom,
    ratio,
    repertory,
    tickler,
    triz,
    trivium,
    vsm,
    waterlogic,
)


# ---------------------------------------------------------------------------
# 15. tickler
# ---------------------------------------------------------------------------


class TestTickler:
    def test_file_routes_within_month_to_day_folder(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        item = t.file("Grant proposal", date(2026, 9, 20), reason="officer back")
        assert item.folder == "day:20"

    def test_file_routes_far_future_to_month_folder(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        item = t.file("Renew cert", date(2026, 12, 1))
        assert item.folder == "month:12"

    def test_open_today_surfaces_due_with_context(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        t.file("A", date(2026, 9, 15), body="full material", reason="why")
        t.file("B", date(2026, 9, 20))
        due = t.open_today(date(2026, 9, 15))
        assert [i.title for i in due] == ["A"]
        assert due[0].body == "full material" and due[0].reason == "why"

    def test_overdue_surfaced_failsafe(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        item = t.file("Late", date(2026, 10, 5))  # month folder
        assert item.folder == "month:10"
        due = t.open_today(date(2026, 11, 1))  # never distributed — still surfaced
        assert [i.title for i in due] == ["Late"]
        assert due[0].overdue is True

    def test_distribute_month_moves_into_day_folders(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        t.file("Oct thing", date(2026, 10, 5))
        moved = t.distribute_month(date(2026, 10, 1))
        assert moved == 1
        due = t.open_today(date(2026, 10, 5))
        assert [i.title for i in due] == ["Oct thing"]

    def test_tickle_again_and_dismiss(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        item = t.file("X", date(2026, 9, 16))
        t.tickle_again(item.id, date(2026, 12, 25))
        assert t.get(item.id).folder == "month:12"
        t.dismiss(item.id)
        assert t.pending() == []

    def test_deny_closed(self):
        t = tickler.TicklerFile(today=date(2026, 9, 15))
        with pytest.raises(ValueError):
            t.file("   ", date(2026, 9, 16))
        with pytest.raises(ValueError):
            t.file("Past", date(2026, 9, 14))
        with pytest.raises(ValueError):
            t.file("Bad", "next Friday")
        with pytest.raises(ValueError):
            t.get("nope")
        with pytest.raises(ValueError):
            t.tickle_again("nope", date(2026, 9, 16))

    def test_persistence_round_trip(self, tmp_path):
        p = tmp_path / "tickler.json"
        t = tickler.TicklerFile(path=p, today=date(2026, 9, 15))
        t.file("Persist me", date(2026, 9, 18), reason="r")
        t.save()
        t2 = tickler.TicklerFile(path=p, today=date(2026, 9, 15))
        assert [i.title for i in t2.pending()] == ["Persist me"]
        assert json.loads(p.read_text())  # valid JSON on disk


# ---------------------------------------------------------------------------
# 16. ivylee
# ---------------------------------------------------------------------------


class TestIvyLee:
    def _day(self):
        d = ivylee.IvyLeeDay(date(2026, 9, 15))
        ids = [d.add_task(f"Task {i}").id for i in range(1, 4)]
        d.set_order([ids[2], ids[0], ids[1]])
        return d, ids

    def test_current_reveals_only_number_one(self):
        d, ids = self._day()
        assert d.current().id == ids[2]
        assert [t.id for t in d.queue()] == [ids[2], ids[0], ids[1]]

    def test_strict_order_enforced(self):
        d, ids = self._day()
        with pytest.raises(ValueError):
            d.complete(ids[0])  # not current
        d.complete(ids[2])
        assert d.current().id == ids[0]

    def test_roll_forward_carries_unfinished(self):
        d, ids = self._day()
        d.complete(ids[2])
        nxt = d.roll_forward(date(2026, 9, 16))
        assert [t.title for t in nxt.queue()] == ["Task 1", "Task 2"]
        assert all(t.rolled == 1 for t in nxt.queue())
        assert nxt.current().title == "Task 1"

    def test_chronic_rollers(self):
        d, _ = self._day()
        for i in range(3):
            d = d.roll_forward(date(2026, 9, 16 + i))
        assert len(d.chronic_rollers(threshold=3)) == 3
        assert d.chronic_rollers(threshold=4) == []

    def test_deny_closed(self):
        d = ivylee.IvyLeeDay("2026-09-15")
        for i in range(6):
            d.add_task(f"T{i}")
        with pytest.raises(ValueError):
            d.add_task("T6")  # cap
        with pytest.raises(ValueError):
            d.add_task("t0")  # duplicate (case-insensitive)
        with pytest.raises(ValueError):
            d.add_task("  ")
        with pytest.raises(ValueError):
            d.set_order(["bogus"])
        with pytest.raises(ValueError):
            d.roll_forward(date(2026, 9, 14))  # not later
        with pytest.raises(ValueError):
            ivylee.IvyLeeDay("tomorrow")


# ---------------------------------------------------------------------------
# 17. franklin
# ---------------------------------------------------------------------------


class TestFranklin:
    def test_thirteen_virtues_default(self):
        ledger = franklin.FranklinLedger(start=date(2026, 9, 15))
        assert len(ledger.virtues) == 13
        assert ledger.virtues[0][0] == "Temperance"

    def test_mark_and_report(self):
        ledger = franklin.FranklinLedger(start=date(2026, 9, 14))  # a Monday
        ledger.mark("Order", date(2026, 9, 14))
        ledger.mark("Order", date(2026, 9, 15))
        ledger.mark("Silence", date(2026, 9, 15))
        rep = ledger.report()
        assert rep["spots_per_virtue"]["Order"] == 2
        assert rep["total_spots"] == 3
        assert rep["worst_virtue"] == "Order"

    def test_weekly_focus_rotates(self):
        ledger = franklin.FranklinLedger(start=date(2026, 9, 14))
        assert ledger.focus_virtue(date(2026, 9, 14)) == "Temperance"
        assert ledger.focus_virtue(date(2026, 9, 21)) == "Silence"
        assert ledger.focus_virtue(date(2026, 10, 5)) == "Resolution"  # week 3

    def test_grid_shape(self):
        ledger = franklin.FranklinLedger(start=date(2026, 9, 14))
        ledger.mark("Industry", date(2026, 9, 15))
        g = ledger.grid(start=date(2026, 9, 14), days=2)
        assert g["Industry"] == [False, True]
        assert all(len(v) == 2 for v in g.values())

    def test_deny_closed(self):
        ledger = franklin.FranklinLedger(start=date(2026, 9, 14))
        with pytest.raises(ValueError):
            ledger.mark("Procrastination", date(2026, 9, 14))
        with pytest.raises(ValueError):
            ledger.mark("Order", "yesterday")
        ledger.mark("Order", date(2026, 9, 14))
        with pytest.raises(ValueError):
            ledger.mark("Order", date(2026, 9, 14))  # duplicate mark
        with pytest.raises(ValueError):
            franklin.FranklinLedger(virtues=[])
        with pytest.raises(ValueError):
            franklin.FranklinLedger(virtues=[("A", "p")] * 14)

    def test_custom_virtues_and_persistence(self, tmp_path):
        p = tmp_path / "franklin.json"
        ledger = franklin.FranklinLedger(
            virtues=[("Draft daily", "write"), ("No phone", "mornings")],
            path=p,
            start=date(2026, 9, 14),
        )
        ledger.mark("Draft daily", date(2026, 9, 14))
        ledger.save()
        ledger2 = franklin.FranklinLedger(
            virtues=[("Draft daily", "write"), ("No phone", "mornings")],
            path=p,
            start=date(2026, 9, 14),
        )
        assert ledger2.report()["spots_per_virtue"]["Draft daily"] == 1


# ---------------------------------------------------------------------------
# 18. ach
# ---------------------------------------------------------------------------


class TestACH:
    def _matrix(self):
        m = ach.ACH("Should I take the job?")
        for h in ("Take it", "Stay", "Go freelance"):
            m.add_hypothesis(h)
        m.add_evidence("E1 pay rise", "30% raise")
        m.add_evidence("E2 commute", "2h daily")
        m.add_evidence("E3 growth", "stagnant team")
        m.add_evidence("E4 irrelevant", "office has plants")
        # E1 supports Take it, argues against Stay/freelance
        m.mark("E1 pay rise", "Take it", ach.CONSISTENT)
        m.mark("E1 pay rise", "Stay", ach.INCONSISTENT)
        m.mark("E1 pay rise", "Go freelance", ach.INCONSISTENT)
        # E2 argues against Take it only
        m.mark("E2 commute", "Take it", ach.INCONSISTENT)
        m.mark("E2 commute", "Stay", ach.CONSISTENT)
        m.mark("E2 commute", "Go freelance", ach.CONSISTENT)
        # E3 argues against Take it and Stay
        m.mark("E3 growth", "Take it", ach.INCONSISTENT)
        m.mark("E3 growth", "Stay", ach.INCONSISTENT)
        m.mark("E3 growth", "Go freelance", ach.CONSISTENT)
        for h in ("Take it", "Stay", "Go freelance"):
            m.mark("E4 irrelevant", h, ach.IRRELEVANT)
        return m

    def test_ranked_by_disconfirmation(self):
        m = self._matrix()
        order = [r.hypothesis for r in m.rank()]
        # against counts: Take it=2, Stay=2, freelance=1 -> freelance least refuted
        assert order[0] == "Go freelance"
        assert m.leader().against == 1

    def test_flags_catch_nondiagnostic(self):
        m = self._matrix()
        flags = m.flags()
        nd = [f for f in flags if f["type"] == "non_diagnostic"]
        assert any(f["evidence"] == "E4 irrelevant" for f in nd)

    def test_flags_catch_unexplained(self):
        m = ach.ACH("q")
        m.add_hypothesis("H1")
        m.add_hypothesis("H2")
        m.add_evidence("E1")
        m.mark("E1", "H1", ach.INCONSISTENT)
        m.mark("E1", "H2", ach.INCONSISTENT)
        assert any(f["type"] == "unexplained" for f in m.flags())

    def test_sensitivity_finds_load_bearing_fact(self):
        m = self._matrix()
        sens = m.sensitivity()
        e3 = next(s for s in sens if s["evidence"] == "E3 growth")
        assert e3["flips_leader"] is True  # without E3, "Take it" ties/leads
        e4 = next(s for s in sens if s["evidence"] == "E4 irrelevant")
        assert e4["flips_leader"] is False

    def test_diagnosticity(self):
        m = self._matrix()
        assert m.diagnosticity("E4 irrelevant") == 0.0
        assert 0.9 < m.diagnosticity("E1 pay rise") <= 1.0

    def test_argue_against(self):
        m = self._matrix()
        case = m.argue_against()
        assert case["hypothesis"] == "Go freelance"
        assert "E1 pay rise" in case["inconsistent_evidence"]

    def test_deny_closed(self):
        m = ach.ACH("q")
        m.add_hypothesis("H1")
        with pytest.raises(ValueError):
            m.add_hypothesis("H1")
        with pytest.raises(ValueError):
            m.add_evidence("  ")
        with pytest.raises(ValueError):
            m.mark("nope", "H1", ach.CONSISTENT)
        with pytest.raises(ValueError):
            m.mark("E1", "H1", "maybe")
        m2 = ach.ACH("q")  # no hypotheses at all
        with pytest.raises(ValueError):
            m2.rank()


# ---------------------------------------------------------------------------
# 19. repertory
# ---------------------------------------------------------------------------


class TestRepertory:
    def _grid(self):
        g = repertory.RepertoryGrid(topic="career")
        for el in ("Job A", "Job B", "Job C"):
            g.add_element(el)
        c1 = g.elicit_construct(
            "autonomous",
            "directed",
            triad=("Job A", "Job B", "Job C"),
            alike_pair=("Job A", "Job B"),
        )
        c2 = g.elicit_construct("novel", "routine")
        g.rate("Job A", c1.id, 2)
        g.rate("Job B", c1.id, 3)
        g.rate("Job C", c1.id, 7)
        g.rate("Job A", c2.id, 6)
        g.rate("Job B", c2.id, 6)
        g.rate("Job C", c2.id, 2)
        return g, c1, c2

    def test_triad_provenance_recorded(self):
        g, c1, _ = self._grid()
        assert c1.triad == ("Job A", "Job B", "Job C")
        assert c1.alike_pair == ("Job A", "Job B")

    def test_analysis_finds_discriminating_construct(self):
        g, c1, c2 = self._grid()
        a = g.analyze()
        assert a["most_discriminating"][0] == c1.id  # spread 5 vs 4
        assert a["completeness"] == 1.0

    def test_aligned_constructs_detected(self):
        g = repertory.RepertoryGrid()
        for el in ("a", "b", "c", "d"):
            g.add_element(el)
        c1 = g.elicit_construct("x", "y")
        c2 = g.elicit_construct("p", "q")
        for el, s1, s2 in (("a", 1, 1), ("b", 2, 2), ("c", 6, 7), ("d", 7, 6)):
            g.rate(el, c1.id, s1)
            g.rate(el, c2.id, s2)
        aligned = g.analyze()["aligned_pairs"]
        assert len(aligned) == 1 and abs(aligned[0]["correlation"]) >= 0.7

    def test_score_new_option(self):
        g, c1, c2 = self._grid()
        pos = g.score_option({c1.id: 1, c2.id: 7})
        assert pos == {c1.id: 1.0, c2.id: 7.0}

    def test_deny_closed(self):
        g = repertory.RepertoryGrid()
        g.add_element("a")
        with pytest.raises(ValueError):
            g.add_element("a")
        c = g.elicit_construct("p", "q")
        with pytest.raises(ValueError):
            g.elicit_construct("p", "p")
        with pytest.raises(ValueError):
            g.rate("ghost", c.id, 3)
        with pytest.raises(ValueError):
            g.rate("a", "C99", 3)
        with pytest.raises(ValueError):
            g.rate("a", c.id, 8)
        with pytest.raises(ValueError):
            g.elicit_construct("p2", "q2", triad=("a", "a", "b"))
        with pytest.raises(ValueError):
            g.elicit_construct("p2", "q2", triad=("a", "b", "ghost"))


# ---------------------------------------------------------------------------
# 20. morphological
# ---------------------------------------------------------------------------


class TestMorphological:
    def _box(self):
        b = morphological.MorphologicalBox("sabbatical")
        b.add_parameter("where", ["home", "abroad"])
        b.add_parameter("pace", ["slow", "fast"])
        b.add_parameter("work", ["none", "half"])
        return b

    def test_count_and_enumerate(self):
        b = self._box()
        assert b.count() == 8
        assert len(list(b.enumerate())) == 8

    def test_pruning(self):
        b = self._box()
        b.forbid("where", "abroad", "work", "half", reason="visa limits")
        b.forbid("pace", "fast", "work", "none", reason="wasteful")
        kept = b.survivors()
        assert len(kept) == 4  # 8 - 2(struck by rule1) - 2(struck by rule2)
        for combo in kept:
            assert not (combo["where"] == "abroad" and combo["work"] == "half")
        rep = b.prune_report()
        assert rep["total_combinations"] == 8 and rep["survivors"] == 4
        assert rep["struck"] == 4

    def test_cap_fails_closed(self):
        b = morphological.MorphologicalBox("big")
        for i in range(6):
            b.add_parameter(f"p{i}", [f"v{j}" for j in range(10)])  # 10^6
        with pytest.raises(ValueError):
            list(b.enumerate())
        assert b.count() == 10**6
        # explicit opt-in still works lazily (take one without materializing)
        it = b.enumerate(allow_large=True)
        assert len(next(it)) == 6

    def test_deny_closed(self):
        b = self._box()
        with pytest.raises(ValueError):
            b.add_parameter("where", ["x", "y"])  # duplicate
        with pytest.raises(ValueError):
            b.add_parameter("thin", ["only-one"])
        with pytest.raises(ValueError):
            b.forbid("where", "home", "where", "abroad")  # same param
        with pytest.raises(ValueError):
            b.forbid("where", "moon", "pace", "slow")
        b.forbid("where", "abroad", "pace", "fast")
        with pytest.raises(ValueError):
            b.forbid("pace", "fast", "where", "abroad")  # duplicate (order-free)


# ---------------------------------------------------------------------------
# 21. triz
# ---------------------------------------------------------------------------


class TestTRIZ:
    def test_full_parameter_and_principle_encoding(self):
        assert len(triz.PARAMETERS) == 39
        assert len(triz.PRINCIPLES) == 40
        assert triz.PARAMETERS[1] == "Weight of moving object"
        assert triz.PRINCIPLES[1][0] == "Segmentation"

    def test_classic_weight_strength_lookup(self):
        found = triz.lookup(1, 14)
        assert [p["id"] for p in found] == [1, 8, 15, 34]
        assert found[0]["name"] == "Segmentation"
        assert "try_this" in found[0]

    def test_resolve_by_name(self):
        assert triz.resolve_parameter("weight of moving") == 1
        assert triz.resolve_parameter("39") == 39
        assert triz.lookup("productivity", "loss of time")

    def test_unknown_pair_is_honest_empty(self):
        assert triz.lookup(2, 3) == []
        rep = triz.contradiction_report(2, 3)
        assert rep["in_matrix"] is False
        assert "curated subset" in rep["guidance"] or "full" in rep["guidance"]

    def test_coverage_reports_exactly(self):
        cov = triz.coverage()
        assert cov["matrix_cells_possible"] == 1521
        assert cov["matrix_cells_encoded"] == len(triz.MATRIX)
        assert all("improving" in p for p in cov["encoded_pairs"])

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            triz.resolve_parameter(99)
        with pytest.raises(ValueError):
            triz.resolve_parameter("flibbertigibbet")
        with pytest.raises(ValueError):
            triz.describe_principle(41)
        with pytest.raises(ValueError):
            triz.lookup(5, 5)


# ---------------------------------------------------------------------------
# 22. waterlogic
# ---------------------------------------------------------------------------


class TestWaterlogic:
    def _scape(self):
        f = waterlogic.Flowscape(topic="pricing")
        a = f.add_statement("We cut prices 20%")
        b = f.add_statement("Volume rises")
        c = f.add_statement("Margins compress")
        d = f.add_statement("Competitors match")
        e = f.add_statement("Brand feels cheap")
        g = f.add_statement("We learn nothing")
        f.flow(a, b, "lower price -> more buyers")
        f.flow(a, c, "same costs, less revenue")
        f.flow(b, d, "they notice the volume")
        f.flow(c, d, "pressure to respond")
        f.flow(d, e, "race to the bottom")
        return f, (a, b, c, d, e, g)

    def test_trace_paths(self):
        f, (a, *_rest) = self._scape()
        paths = f.trace(a)
        assert len(paths) == 2  # a->b->d->e and a->c->d->e
        assert all(p[0] == a for p in paths)

    def test_ruts_and_neglected(self):
        f, ids = self._scape()
        a, b, c, d, e, g = ids
        assert f.ruts(1)[0]["id"] == d  # everything drains into "Competitors match"
        assert [n["id"] for n in f.neglected()] == [a, g]
        assert [n["id"] for n in f.dead_ends()] == [e, g]

    def test_report_reading(self):
        f, (a, *_rest) = self._scape()
        rep = f.report(a)
        assert rep["path_count"] == 2
        assert "rut" in rep["reading"]

    def test_deny_closed(self):
        f = waterlogic.Flowscape()
        a = f.add_statement("x")
        with pytest.raises(ValueError):
            f.add_statement("X")  # duplicate
        with pytest.raises(ValueError):
            f.add_statement("  ")
        with pytest.raises(ValueError):
            f.flow(a, "S99")
        with pytest.raises(ValueError):
            f.flow(a, a)  # self-loop
        b = f.add_statement("y")
        f.flow(a, b)
        with pytest.raises(ValueError):
            f.flow(a, b)  # duplicate flow


# ---------------------------------------------------------------------------
# 23. vsm
# ---------------------------------------------------------------------------


class TestVSM:
    def _vsm(self):
        v = vsm.VSM("freelance practice")
        v.add_unit("client work", "1")
        v.add_unit("scheduling", "2")
        v.add_unit("invoicing", "3")
        v.add_unit("identity", "5")
        return v

    def test_missing_s4_flagged_high(self):
        rep = self._vsm().viability_report()
        s4 = [f for f in rep["findings"] if f["system"] == "4"]
        assert s4 and s4[0]["severity"] == "high"
        assert rep["verdict"].startswith("NOT VIABLE")

    def test_missing_audit_channel_flagged(self):
        rep = self._vsm().viability_report()
        assert any(f["system"] == "3*" for f in rep["findings"])

    def test_complete_system_viable(self):
        v = vsm.VSM("ok")
        v.add_unit("ops", "1")
        v.add_unit("rota", "2")
        v.add_unit("budget", "3")
        v.add_unit("spot checks", "3*")
        v.add_unit("market scan", "4")
        v.add_unit("mission", "5")
        rep = v.viability_report()
        assert rep["by_severity"]["high"] == 0
        assert rep["verdict"] == "VIABLE"

    def test_recursion(self):
        v = self._vsm()
        sub = v.decompose("client work")
        sub.add_unit("deep work", "1")
        rep = v.viability_report()
        assert any(
            "recursion via S1 unit 'client work'" in f["message"]
            for f in rep["findings"]
        )
        # the sub-unit 'deep work' is itself not decomposed -> info finding, recursion-tagged
        assert any(
            "'deep work'" in f["message"] and "not decomposed" in f["message"]
            for f in rep["findings"]
        )

    def test_colonized_s3_flagged(self):
        v = vsm.VSM("top-heavy")
        v.add_unit("ops", "1")
        v.add_unit("ctrl-a", "3")
        v.add_unit("ctrl-b", "3")
        rep = v.viability_report()
        assert any("colonized" in f["message"] for f in rep["findings"])

    def test_deny_closed(self):
        v = vsm.VSM("x")
        with pytest.raises(ValueError):
            v.add_unit("ops", "6")
        v.add_unit("ops", "1")
        with pytest.raises(ValueError):
            v.add_unit("OPS", "1")
        with pytest.raises(ValueError):
            v.decompose("missing")
        with pytest.raises(ValueError):
            vsm.VSM("  ")


# ---------------------------------------------------------------------------
# 24. opsroom
# ---------------------------------------------------------------------------


class TestOpsroom:
    def _room(self):
        r = opsroom.OpsRoom("sunday review")
        r.seat(
            "operator",
            "deep work hours",
            12.0,
            threshold=15.0,
            direction="below",
            unit="h",
        )
        r.seat("scout", "inbound leads", 9.0, threshold=5.0, direction="above")
        r.seat(
            "auditor", "hours logged vs planned", 0.92, threshold=0.8, direction="below"
        )
        return r

    def test_algedonic_alerts(self):
        r = self._room()
        alerts = r.algedonic()
        chairs = {a["chair"] for a in alerts}
        assert chairs == {"operator", "scout"}  # 12 < 15 below; 9 > 5 above
        assert all("cry" in a for a in alerts)

    def test_prepare_shows_seven_chairs(self):
        r = self._room()
        prep = r.prepare()
        assert len(prep["chairs"]) == 7
        assert set(prep["empty_chairs"]) == {
            "coordinator",
            "controller",
            "steward",
            "chair",
        }

    def test_decide_requires_rationale(self):
        r = self._room()
        with pytest.raises(ValueError):
            r.decide("chair", "Ship it", "  ")
        d = r.decide(
            "chair", "Pause new client work", "operator signal below threshold"
        )
        assert r.decisions() == [d]

    def test_adjunction(self):
        r = self._room()
        first = r.adjourn()
        assert first["alerts_raised"] == 2
        assert first["decisions"] == 0
        assert "did not do its job" in first["note"]
        r.decide("chair", "Protect deep-work blocks", "operator algedonic")
        second = r.adjourn()
        assert second["adjourned"] is True

    def test_deny_closed(self):
        r = opsroom.OpsRoom()
        with pytest.raises(ValueError):
            r.seat("janitor", "mops", 3.0)
        with pytest.raises(ValueError):
            r.seat("scout", "x", "lots")
        with pytest.raises(ValueError):
            r.seat("scout", "x", 1.0, direction="sideways")
        with pytest.raises(ValueError):
            r.decide("janitor", "x", "y")


# ---------------------------------------------------------------------------
# 25. deming
# ---------------------------------------------------------------------------


class TestDeming:
    def _stable(self):
        d = deming.ProfoundKnowledge()
        for v in (10, 11, 9, 10, 12, 10, 11, 9, 10):
            d.observe("output", v)
        return d

    def test_insufficient_data_refuses_judgment(self):
        d = deming.ProfoundKnowledge()
        for v in (1, 2, 3):
            d.observe("m", v)
        diag = d.diagnose("m")
        assert diag["variation"]["verdict"] == "insufficient_data"

    def test_common_cause_says_dont_tamper(self):
        d = self._stable()
        d.observe("output", 10.5)
        v = d.diagnose("output")["variation"]
        assert v["verdict"] == "common_cause"
        assert "Do not tamper" in v["detail"]

    def test_special_cause_detected(self):
        d = self._stable()
        d.observe("output", 30)
        v = d.diagnose("output")["variation"]
        assert v["verdict"] == "possible_special_cause"

    def test_knowledge_lens_demands_theory(self):
        d = self._stable()
        diag = d.diagnose("output")
        assert diag["knowledge"]["verdict"] == "no_theory"
        d.record_theory(
            "output", "travel weeks cut deep-work blocks", "output dips on travel weeks"
        )
        diag2 = d.diagnose("output")
        assert diag2["knowledge"]["verdict"] == "theory_recorded"

    def test_system_and_psychology_lenses(self):
        d = self._stable()
        d.link("output", "travel_days", "travel displaces deep-work blocks")
        d.watch_for("output", "streak_punishment")
        diag = d.diagnose("output")
        assert diag["system"]["linked_metrics"] == [
            ("travel_days", "travel displaces deep-work blocks")
        ]
        assert "streak_punishment" in diag["psychology"]["watched_risks"]
        assert "Psychology says" in diag["interaction"]

    def test_deny_closed(self):
        d = deming.ProfoundKnowledge()
        with pytest.raises(ValueError):
            d.observe("m", "lots")
        with pytest.raises(ValueError):
            d.diagnose("never-observed")
        with pytest.raises(ValueError):
            d.record_theory("m", "", "pred")
        with pytest.raises(ValueError):
            d.link("m", "m", "self")
        with pytest.raises(ValueError):
            d.watch_for("m", "vibes")


# ---------------------------------------------------------------------------
# 26. trivium
# ---------------------------------------------------------------------------


class TestTrivium:
    def test_gates_block_advance(self):
        t = trivium.TriviumStudy("statistics")
        with pytest.raises(ValueError):
            t.advance()  # no grammar yet
        t.grammar(["p-value", "distribution"])
        assert t.advance() == "logic"
        with pytest.raises(ValueError):
            t.advance()  # no logic yet
        t.logic(["a small p-value does not imply a large effect"])
        assert t.advance() == "rhetoric"
        t.rhetoric("p-values measure surprise under the null...")
        with pytest.raises(ValueError):
            t.advance()  # no cross-examination yet
        t.cross_examine(
            "What does p=0.04 actually claim?",
            "That data this extreme would be rare if the null held.",
        )
        assert t.advance() == "quadrivium"
        t.quadrivium("arithmetic", "computed power for n=200")
        with pytest.raises(ValueError):
            t.advance()  # already final

    def test_status(self):
        t = trivium.TriviumStudy("logic")
        t.grammar(["syllogism"])
        s = t.status()
        assert s["stage"] == "grammar" and s["facts"] == 1
        assert s["gates"]["grammar"]["met"] is True

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            trivium.TriviumStudy("  ")
        t = trivium.TriviumStudy("x")
        with pytest.raises(ValueError):
            t.grammar([])
        with pytest.raises(ValueError):
            t.quadrivium("astrology", "stars")
        t.cross_examine("q?", "a.")
        with pytest.raises(ValueError):
            t.cross_examine("Q?", "a2.")  # duplicate question


# ---------------------------------------------------------------------------
# 27. ratio
# ---------------------------------------------------------------------------


class TestRatio:
    def _study(self):
        s = ratio.RatioStudy(
            "statistics", "the paper on identification", start=date(2026, 9, 1)
        )
        s.praelectio(["the argument in one paragraph", "the identification strategy"])
        return s

    def test_repetitio_schedule(self):
        s = self._study()
        sched = s.repetitio_schedule()
        assert [r["lag_days"] for r in sched] == [1, 3, 7, 14, 30]
        assert sched[0]["date"] == "2026-09-02"
        assert all(r["done"] is False for r in sched)

    def test_mark_repetition_and_report(self):
        s = self._study()
        s.mark_repetition(1, 4, on_date=date(2026, 9, 2))
        s.mark_repetition(3, 2, on_date=date(2026, 9, 4))
        rep = s.repetition_report()
        assert rep["completed"] == 2 and rep["weak_lags"] == [3]

    def test_disputatio_gates_completion(self):
        s = self._study()
        for lag in ratio.REPETITION_LAGS:
            s.mark_repetition(lag, 4)
        assert s.complete() is False  # no disputatio yet
        s.disputatio(["defend the identification strategy"])
        assert s.undefended() == [0]
        assert s.complete() is False
        s.defend(0, "instruments are plausibly exogenous because...")
        assert s.complete() is True

    def test_protocol_versioning(self):
        s = self._study()
        assert s.protocol_version == 1
        assert (
            s.revise_protocol("add a second disputatio round for methods papers") == 2
        )
        assert len(s.protocol_changelog) == 2

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            ratio.RatioStudy("", "material")
        s = self._study()
        with pytest.raises(ValueError):
            s.mark_repetition(2, 4)
        with pytest.raises(ValueError):
            s.mark_repetition(1, 6)
        with pytest.raises(ValueError):
            s.defend(0, "x")  # no objections raised
        with pytest.raises(ValueError):
            s.revise_protocol("  ")


# ---------------------------------------------------------------------------
# 28. monitorial
# ---------------------------------------------------------------------------


class TestMonitorial:
    def test_mastery_requires_all_three_pupils(self):
        t = monitorial.TeachBack("p-values")
        t.explain("naive", "plain words...")
        t.assess("naive", 5, 5, 4)
        assert t.mastery()["mastered"] is False
        t.explain("sharp", "precise words...")
        t.assess("sharp", 4, 4, 4)
        t.explain("hostile", "defended words...")
        t.assess("hostile", 4, 4, 5)
        m = t.mastery()
        assert m["mastered"] is True
        assert "hostile" in m["verdict"]

    def test_low_score_blocks_mastery(self):
        t = monitorial.TeachBack("x")
        for level in monitorial.PUPIL_LEVELS:
            t.explain(level, "words")
            t.assess(level, 2, 2, 2)
        assert t.mastery()["mastered"] is False

    def test_cascade_and_drift(self):
        c = monitorial.Cascade("onboarding")
        c.train_monitor("Ava")
        c.train_monitor("Ben")
        c.assign("Ava", "cohort-1")
        c.assign("Ben", "cohort-2")
        c.spot_check("Ava", 5, "faithful")
        c.spot_check("Ben", 2, "skipping the hard part")
        c.spot_check("Ben", 2, "still skipping")
        rep = c.drift_report()
        assert rep["drifting"] == ["Ben"]
        assert rep["groups_covered"] == 2

    def test_deny_closed(self):
        t = monitorial.TeachBack("x")
        with pytest.raises(ValueError):
            t.explain("professor", "words")
        with pytest.raises(ValueError):
            t.assess("naive", 5, 5, 5)  # no explanation yet
        t.explain("naive", "words")
        with pytest.raises(ValueError):
            t.assess("naive", 6, 5, 5)
        c = monitorial.Cascade("x")
        with pytest.raises(ValueError):
            c.assign("Nobody", "g1")
        c.train_monitor("Ava")
        with pytest.raises(ValueError):
            c.train_monitor("Ava")
        with pytest.raises(ValueError):
            c.spot_check("Ghost", 3)


# ---------------------------------------------------------------------------
# package-level: every module imports cleanly
# ---------------------------------------------------------------------------


def test_all_modules_import():
    import importlib

    for name in (
        "tickler",
        "ivylee",
        "franklin",
        "ach",
        "repertory",
        "morphological",
        "triz",
        "waterlogic",
        "vsm",
        "opsroom",
        "deming",
        "trivium",
        "ratio",
        "monitorial",
    ):
        mod = importlib.import_module(f"levi.methods.{name}")
        assert mod.__name__ == f"levi.methods.{name}"
