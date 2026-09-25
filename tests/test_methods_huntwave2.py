"""Tests for hunt wave batch B: harvard, eniac, greenwich, bletchley,
actuarial, forecast, claytablet, writegates.

Hermetic: pure in-memory, no file/network I/O anywhere.
"""

import pytest

from levi.methods.harvard import ClassificationPipeline
from levi.methods.eniac import BlueprintAdoption
from levi.methods.greenwich import PostPublicationAudit
from levi.methods.bletchley import StagedAttackPipeline
from levi.methods.actuarial import ExperienceTable
from levi.methods.forecast import CellularComputer
from levi.methods.claytablet import SealedRecord
from levi.methods.writegates import WriteGates


class TestHarvardPipeline:
    def _pipeline(self):
        p = ClassificationPipeline()
        for label in ("O", "B", "A"):
            p.define_label(label)
        return p

    def test_full_flow_with_piece_accounting(self):
        p = self._pipeline()
        p.add_item("plate-1", "spectrum data one")
        p.add_item("plate-2", "spectrum data two")
        p.measure("plate-1", {"mag": 4.2}, "fleming")
        p.measure("plate-2", {"mag": 6.1}, "cannon")
        p.classify("plate-1", "O", "fleming")
        p.classify("plate-2", "B", "cannon")
        p.catalogue("plate-1", "maury")
        p.catalogue("plate-2", "maury")
        tally = p.throughput()
        assert tally["fleming"] == {"pieces": 2, "measured": 1, "classified": 1}
        assert tally["cannon"] == {"pieces": 2, "measured": 1, "classified": 1}
        assert tally["maury"] == {"pieces": 2, "catalogued": 2}

    def test_compress_remaps_items_and_taxonomy(self):
        p = self._pipeline()
        p.add_item("plate-1", "data")
        p.add_item("plate-2", "data")
        p.measure("plate-1", {"m": 1}, "a")
        p.measure("plate-2", {"m": 2}, "a")
        p.classify("plate-1", "O", "a")
        p.classify("plate-2", "B", "a")
        remap = p.compress({"O": "A"})
        assert remap == {"O": "A"}
        assert p._items["plate-1"].label == "A"
        assert p._items["plate-2"].label == "B"
        assert "O" not in p.labels()
        assert p.labels() == ["A", "B"]

    def test_deny_closed(self):
        p = self._pipeline()
        with pytest.raises(ValueError):
            p.add_item("", "data")
        with pytest.raises(ValueError):
            p.add_item("x", "")
        with pytest.raises(ValueError):
            p.add_item("x", "   ")
        p.add_item("x", "data")
        with pytest.raises(ValueError):
            p.add_item("x", "data")  # duplicate
        with pytest.raises(ValueError):
            p.define_label("")
        with pytest.raises(ValueError):
            p.define_label("O")  # duplicate
        with pytest.raises(ValueError):
            p.measure("nope", {"m": 1}, "a")  # unknown item
        with pytest.raises(ValueError):
            p.measure("x", {}, "a")  # no measurements
        with pytest.raises(ValueError):
            p.measure("x", {"m": 1}, "")  # empty analyst
        with pytest.raises(ValueError):
            p.classify("x", "O", "a")  # not measured yet
        with pytest.raises(ValueError):
            p.catalogue("x", "a")  # not classified yet
        p.measure("x", {"m": 1}, "a")
        with pytest.raises(ValueError):
            p.measure("x", {"m": 2}, "a")  # already measured
        with pytest.raises(ValueError):
            p.classify("x", "ZZZ", "a")  # unknown label
        with pytest.raises(ValueError):
            p.classify("x", "", "a")
        with pytest.raises(ValueError):
            p.catalogue("nope", "a")
        with pytest.raises(ValueError):
            p.compress({})  # empty merges
        with pytest.raises(ValueError):
            p.compress({"ZZZ": "A"})  # unknown old
        with pytest.raises(ValueError):
            p.compress({"O": "ZZZ"})  # unknown target
        with pytest.raises(ValueError):
            p.compress({"O": "O"})  # self-merge


class TestEniacBlueprint:
    def _adoption(self):
        a = BlueprintAdoption()
        a.register_op("add", "accumulator wiring")
        a.register_op("branch", "function-table wiring")
        a.define_procedure("trajectory", ["load tables", "integrate", "pray"])
        return a

    def test_transfer_and_rewrite_classification(self):
        a = self._adoption()
        a.map_step("trajectory", 0, "add")
        a.map_step("trajectory", 1, "branch")
        a.mark_rewrite("trajectory", 2, "no op for prayer on ENIAC")
        report = a.finalize("trajectory")
        assert report.transferred == {0: "add", 1: "branch"}
        assert report.rewrites == {2: "no op for prayer on ENIAC"}
        assert report.transfer_ratio == pytest.approx(2 / 3)
        summary = report.summary()
        assert summary["transferred"] == 2
        assert summary["rewrites"] == 1
        # report() reads back the frozen port
        assert a.report("trajectory").summary() == summary

    def test_deny_closed(self):
        a = self._adoption()
        with pytest.raises(ValueError):
            a.register_op("", "w")
        with pytest.raises(ValueError):
            a.register_op("add", "w")  # duplicate op
        with pytest.raises(ValueError):
            a.define_procedure("", ["s"])
        with pytest.raises(ValueError):
            a.define_procedure("trajectory", ["s"])  # duplicate
        with pytest.raises(ValueError):
            a.define_procedure("empty", [])
        with pytest.raises(ValueError):
            a.map_step("nope", 0, "add")  # unknown procedure
        with pytest.raises(ValueError):
            a.map_step("trajectory", 99, "add")  # out of range
        with pytest.raises(ValueError):
            a.map_step("trajectory", -1, "add")
        with pytest.raises(ValueError):
            a.map_step("trajectory", "0", "add")  # non-int index
        with pytest.raises(ValueError):
            a.map_step("trajectory", 0, "ZZZ")  # unknown op
        with pytest.raises(ValueError):
            a.map_step("trajectory", 0, "")  # empty op
        a.map_step("trajectory", 0, "add")
        with pytest.raises(ValueError):
            a.map_step("trajectory", 0, "add")  # already accounted
        with pytest.raises(ValueError):
            a.mark_rewrite("trajectory", 0, "r")  # already mapped
        with pytest.raises(ValueError):
            a.mark_rewrite("trajectory", 1, "")  # empty reason
        with pytest.raises(ValueError):
            a.finalize("trajectory")  # steps 1,2 unmapped
        with pytest.raises(ValueError):
            a.report("trajectory")  # not finalized yet
        with pytest.raises(ValueError):
            a.report("nope")  # unknown procedure
        a.map_step("trajectory", 1, "branch")
        a.mark_rewrite("trajectory", 2, "manual")
        a.finalize("trajectory")
        with pytest.raises(ValueError):
            a.finalize("trajectory")  # already finalized
        with pytest.raises(ValueError):
            a.map_step("trajectory", 0, "add")  # frozen


class TestGreenwichAudit:
    def _audit(self):
        audit = PostPublicationAudit()
        derive = lambda a, s: 10.0 + a["bias"] + 0.1 * s  # noqa: E731
        published = audit.publish(
            "halley-1910",
            derive,
            {"bias": 0.5},  # planted discrepancy
            [10.0, 10.2, 9.9],
            tolerance=0.2,
        )
        return audit, published

    def test_rederivation_flags_planted_discrepancy(self):
        audit, published = self._audit()
        assert published == pytest.approx(10.6)
        report = audit.re_derive("halley-1910", {"corrected": {"bias": 0.0}})
        assert report.published_flagged is True
        assert report.published_divergence == pytest.approx(10.6 - 10.033333, abs=1e-4)
        assert len(report.variants) == 1
        variant = report.variants[0]
        assert variant.name == "corrected"
        assert variant.derived == pytest.approx(10.1)
        assert variant.flagged is False  # corrected assumptions match reality

    def test_deny_closed(self):
        audit, _ = self._audit()
        derive = lambda a, s: 1.0  # noqa: E731
        with pytest.raises(ValueError):
            audit.publish("halley-1910", derive, {}, [1.0])  # duplicate id
        with pytest.raises(ValueError):
            audit.publish("", derive, {}, [1.0])
        with pytest.raises(ValueError):
            audit.publish("x", "not-callable", {}, [1.0])
        with pytest.raises(ValueError):
            audit.publish("x", derive, "nope", [1.0])  # assumptions not dict
        with pytest.raises(ValueError):
            audit.publish("x", derive, {}, [])  # empty observations
        with pytest.raises(ValueError):
            audit.publish("x", derive, {}, [1.0, "bad"])
        with pytest.raises(ValueError):
            audit.publish("x", derive, {}, [1.0], tolerance=-0.1)
        with pytest.raises(ValueError):
            audit.re_derive("nope", {"v": {}})  # unknown id
        with pytest.raises(ValueError):
            audit.re_derive("halley-1910", {})  # empty variants
        with pytest.raises(ValueError):
            audit.re_derive("halley-1910", {"": {"bias": 0.0}})  # empty name
        with pytest.raises(ValueError):
            audit.re_derive("halley-1910", {"v": "nope"})  # non-dict
        with pytest.raises(ValueError):
            audit.re_derive("halley-1910", {"v": {"unknown_key": 1}})


class TestBletchleyPipeline:
    def _pipeline(self):
        p = StagedAttackPipeline()
        p.collect("i1", "encrypted morse traffic")
        return p

    def test_staged_flow_finds_planted_stop(self):
        p = self._pipeline()
        menu = p.hypothesize(
            "i1", {"crib": "WETTER", "settings": "guess", "expected_stop": "STOP-7"}
        )
        assert menu["expected_stop"] == "STOP-7"
        stops = p.machine_run("i1", "night-shift", ["STOP-3", "STOP-7"])
        assert stops == ["STOP-3", "STOP-7"]
        found = p.verify("i1", "STOP-7")
        assert found.found is True
        assert found.expected_stop == "STOP-7"
        log = p.shift_log()
        assert log == [{"intercept_id": "i1", "shift": "night-shift", "stops": 2}]

    def test_produced_but_unexpected_stop_is_not_found(self):
        p = self._pipeline()
        p.hypothesize("i1", {"expected_stop": "STOP-7"})
        p.machine_run("i1", "day-shift", ["STOP-3"])
        result = p.verify("i1", "STOP-3")
        assert result.found is False

    def test_deny_closed(self):
        p = StagedAttackPipeline()
        with pytest.raises(ValueError):
            p.collect("", "payload")
        with pytest.raises(ValueError):
            p.collect("i1", "")
        p.collect("i1", "payload")
        with pytest.raises(ValueError):
            p.collect("i1", "payload")  # duplicate intercept
        with pytest.raises(ValueError):
            p.hypothesize("nope", {"expected_stop": "S"})
        with pytest.raises(ValueError):
            p.machine_run("i1", "shift", ["S"])  # out of order: no menu yet
        with pytest.raises(ValueError):
            p.verify("i1", "S")  # out of order: no machine run
        with pytest.raises(ValueError):
            p.hypothesize("i1", {})  # empty menu
        with pytest.raises(ValueError):
            p.hypothesize("i1", {"crib": "x"})  # no expected stop
        with pytest.raises(ValueError):
            p.hypothesize("i1", {"expected_stop": ""})
        p.hypothesize("i1", {"expected_stop": "STOP-7"})
        with pytest.raises(ValueError):
            p.hypothesize("i1", {"expected_stop": "STOP-7"})  # stage re-run
        with pytest.raises(ValueError):
            p.machine_run("i1", "", ["S"])  # empty shift
        with pytest.raises(ValueError):
            p.machine_run("i1", "shift", [])  # empty stops
        with pytest.raises(ValueError):
            p.machine_run("i1", "shift", ["S", "S"])  # duplicate stops
        with pytest.raises(ValueError):
            p.machine_run("i1", "shift", ["S", ""])  # empty stop
        p.machine_run("i1", "shift", ["STOP-7"])
        with pytest.raises(ValueError):
            p.machine_run("i1", "shift", ["STOP-7"])  # stage re-run
        with pytest.raises(ValueError):
            p.verify("i1", "NEVER-PRODUCED")  # machines never found it
        with pytest.raises(ValueError):
            p.verify("nope", "STOP-7")  # unknown intercept
        with pytest.raises(ValueError):
            p.verify("i1", "")


class TestActuarialTable:
    def _table(self):
        t = ExperienceTable(reserve_factor=2.0)
        t.add_record("under40", 1000, 12)
        t.add_record("under40", 500, 6)
        t.add_record("over40", 2000, 40)
        return t

    def test_cohort_accumulation_with_rates_and_reserves(self):
        build = self._table().build()
        assert [r.cohort for r in build.rows] == ["over40", "under40"]
        over40, under40 = build.rows
        assert (over40.exposure, over40.claims) == (2000, 40)
        assert over40.rate == pytest.approx(0.02)
        assert (over40.cumulative_exposure, over40.cumulative_claims) == (2000, 40)
        assert over40.reserve == pytest.approx(80.0)
        assert (under40.exposure, under40.claims) == (1500, 18)
        assert under40.rate == pytest.approx(0.012)
        assert (under40.cumulative_exposure, under40.cumulative_claims) == (3500, 58)
        assert under40.reserve == pytest.approx(36.0)
        assert build.total_exposure == pytest.approx(3500)
        assert build.total_claims == pytest.approx(58)
        assert build.overall_rate == pytest.approx(58 / 3500)
        assert build.total_reserve == pytest.approx(116.0)

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            ExperienceTable(reserve_factor=0)
        with pytest.raises(ValueError):
            ExperienceTable(reserve_factor=-1)
        with pytest.raises(ValueError):
            ExperienceTable().build()  # empty table
        t = ExperienceTable()
        with pytest.raises(ValueError):
            t.add_record("", 100, 1)
        with pytest.raises(ValueError):
            t.add_record("c", 0, 1)  # zero exposure
        with pytest.raises(ValueError):
            t.add_record("c", -5, 1)
        with pytest.raises(ValueError):
            t.add_record("c", 100, -1)  # negative claims
        with pytest.raises(ValueError):
            t.add_record("c", "lots", 1)
        with pytest.raises(ValueError):
            t.add_record("c", 100, True)  # bool is not a number


class TestForecastFactory:
    def test_diffusion_converges_with_conserved_total(self):
        c = CellularComputer(5, 5)
        c.seed(2, 2, 100.0)
        assert c.value(2, 2) == 100.0
        report = c.run(400)
        assert report.steps == 400
        assert report.final_variance < report.initial_variance
        assert report.total == pytest.approx(100.0)  # total conserved
        assert report.converged is True
        # Every cell has relaxed toward the mean of 4.0.
        for r in range(5):
            for col in range(5):
                assert c.value(r, col) == pytest.approx(4.0, abs=0.01)

    def test_broadcast_reaches_every_cell_in_one_epoch(self):
        c = CellularComputer(3, 4)
        reached = c.broadcast("tempo: blue beam")
        assert reached == 12
        assert c.inbox(0, 0) == ["epoch-0: tempo: blue beam"]
        assert c.inbox(2, 3) == ["epoch-0: tempo: blue beam"]
        c.step()
        assert c.epoch() == 1

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            CellularComputer(0, 5)
        with pytest.raises(ValueError):
            CellularComputer(5, -2)
        with pytest.raises(ValueError):
            CellularComputer("5", 5)
        c = CellularComputer(3, 3)
        with pytest.raises(ValueError):
            c.seed(3, 0, 1.0)  # out of range
        with pytest.raises(ValueError):
            c.seed(0, -1, 1.0)
        with pytest.raises(ValueError):
            c.seed(0, 0, "hot")  # non-numeric
        with pytest.raises(ValueError):
            c.value(9, 9)
        with pytest.raises(ValueError):
            c.run(0)
        with pytest.raises(ValueError):
            c.run(-3)
        with pytest.raises(ValueError):
            c.run("10")
        with pytest.raises(ValueError):
            c.broadcast("")
        with pytest.raises(ValueError):
            c.inbox(0, 5)


class TestClayTablet:
    def _sealed(self):
        r = SealedRecord("ration-42")
        r.add_token("sheep", 10)
        r.add_token("jars", 4)
        r.seal()
        return r

    def test_seal_break_impress_happy_path(self):
        r = SealedRecord("ration-42")
        r.add_token("sheep", 10)
        r.add_token("sheep", 2)
        r.add_token("jars", 4)
        mark = r.seal()
        assert isinstance(mark, str) and len(mark) == 64  # sha256 hex
        tokens = r.break_seal()
        assert tokens == {"sheep": 12, "jars": 4}
        entry = r.impress()
        assert entry.record_id == "ration-42"
        assert entry.lines == (("jars", 4), ("sheep", 12))
        assert entry.total == 16

    def test_tampered_seal_fails_verification(self):
        r = self._sealed()
        r.tamper("sheep", 5)  # inside no longer matches the outside marks
        with pytest.raises(ValueError, match="tampering detected"):
            r.break_seal()

    def test_deny_closed(self):
        with pytest.raises(ValueError):
            SealedRecord("")
        r = SealedRecord("r1")
        with pytest.raises(ValueError):
            r.add_token("", 1)
        with pytest.raises(ValueError):
            r.add_token("sheep", 0)
        with pytest.raises(ValueError):
            r.add_token("sheep", -2)
        with pytest.raises(ValueError):
            r.add_token("sheep", 1.5)
        with pytest.raises(ValueError):
            r.seal()  # empty token set
        with pytest.raises(ValueError):
            r.break_seal()  # not sealed
        with pytest.raises(ValueError):
            r.impress()  # not verified
        with pytest.raises(ValueError):
            r.tamper("sheep", 1)  # not sealed
        r.add_token("sheep", 3)
        r.seal()
        with pytest.raises(ValueError):
            r.add_token("sheep", 1)  # sealed record is closed
        with pytest.raises(ValueError):
            r.seal()  # double seal
        with pytest.raises(ValueError):
            r.tamper("sheep", 0)  # zero delta
        with pytest.raises(ValueError):
            r.impress()  # verify first
        r.break_seal()
        with pytest.raises(ValueError):
            r.break_seal()  # already broken
        with pytest.raises(ValueError):
            r.tamper("sheep", 1)  # tamper window closed
        r.impress()
        with pytest.raises(ValueError):
            r.impress()  # already impressed


class TestWriteGates:
    def _gates(self):
        g = WriteGates()
        g.register_gate("user-capture", "explicit user: remember this")
        g.register_gate("review-lesson", "evening review distilled a lesson")
        return g

    def test_gated_write_lands_with_audit_entry(self):
        g = self._gates()
        e1 = g.write("user-capture", "user said remember", "Chauncey's rule")
        e2 = g.write("review-lesson", "evening review", "check the meter daily")
        assert e1.gate == "user-capture"
        assert e1.trigger == "user said remember"
        audit = g.audit()
        assert len(audit) == 2
        assert [a.seq for a in audit] == [1, 2]
        assert [a.gate for a in audit] == ["user-capture", "review-lesson"]
        assert audit[0].entry_id == e1.id
        assert audit[1].entry_id == e2.id
        assert len(g.entries()) == 2

    def test_auto_write_is_always_refused(self):
        g = self._gates()
        with pytest.raises(ValueError, match="REFUSED"):
            g.auto_write("background extraction found something")
        with pytest.raises(ValueError, match="REFUSED"):
            g.auto_write()
        # Small talk produces zero growth by construction.
        assert g.audit() == []
        assert g.entries() == []

    def test_deny_closed(self):
        g = self._gates()
        with pytest.raises(ValueError):
            g.register_gate("", "desc")
        with pytest.raises(ValueError):
            g.register_gate("g", "")
        with pytest.raises(ValueError):
            g.register_gate("user-capture", "again")  # duplicate
        with pytest.raises(ValueError):
            g.write("no-such-gate", "trigger", "content")  # unregistered
        with pytest.raises(ValueError):
            g.write("", "trigger", "content")
        with pytest.raises(ValueError):
            g.write("user-capture", "", "content")  # empty trigger
        with pytest.raises(ValueError):
            g.write("user-capture", "trigger", "")
        with pytest.raises(ValueError):
            g.write("user-capture", "trigger", "   ")
        with pytest.raises(ValueError):
            g.close_gate("no-such-gate")
        g.close_gate("review-lesson")
        with pytest.raises(ValueError):
            g.close_gate("review-lesson")  # already closed
        with pytest.raises(ValueError):
            g.write("review-lesson", "trigger", "content")  # closed gate
