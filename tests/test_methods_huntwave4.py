"""Hermetic tests for forgotten-methods hunt wave 4 (batch D).

Modules: indenture, masterpiece, compagnon, mystery, hallmark,
zunftlade, sloyd, kontor.

Hermetic: pure in-memory, no I/O, deterministic. Stdlib only.
"""

import pytest

from levi.methods import (
    compagnon,
    hallmark,
    indenture,
    kontor,
    masterpiece,
    mystery,
    sloyd,
    zunftlade,
)


# -- indenture -----------------------------------------------------------------


class TestIndenture:
    def _contract(self):
        return indenture.TrainingContract(
            master="Meister Hans", apprentice="Fritz", term_years=7
        )

    def test_full_scaffold_closes_contract(self):
        c = self._contract()
        for stage in indenture.STAGES:
            assert c.current_stage == stage
            c.sign_off(stage, "Meister Hans")
            assert c.advance() == stage
        assert c.is_closed
        assert c.current_stage is None

    def test_liability_lands_on_master(self):
        c = self._contract()
        c.log_incident("broke a chisel")
        assert c.master_record()["incidents"] == ["broke a chisel"]
        assert c.master_record()["master"] == "Meister Hans"

    def test_empty_names_rejected(self):
        with pytest.raises(ValueError):
            indenture.TrainingContract(master=" ", apprentice="Fritz")
        with pytest.raises(ValueError):
            indenture.TrainingContract(master="Hans", apprentice="")

    def test_nonpositive_term_rejected(self):
        with pytest.raises(ValueError):
            indenture.TrainingContract(master="H", apprentice="F", term_years=0)

    def test_unknown_stage_rejected(self):
        c = self._contract()
        with pytest.raises(ValueError):
            c.sign_off("alchemy", "Meister Hans")

    def test_signoff_from_non_master_rejected(self):
        c = self._contract()
        with pytest.raises(ValueError):
            c.sign_off("mimicry", "Fritz")

    def test_signoff_out_of_order_rejected(self):
        c = self._contract()
        with pytest.raises(ValueError):
            c.sign_off("subcomponents", "Meister Hans")

    def test_advance_without_signoff_rejected(self):
        c = self._contract()
        with pytest.raises(ValueError):
            c.advance()

    def test_advance_after_close_rejected(self):
        c = self._contract()
        for stage in indenture.STAGES:
            c.sign_off(stage, "Meister Hans")
            c.advance()
        with pytest.raises(ValueError):
            c.advance()
        with pytest.raises(ValueError):
            c.sign_off("mimicry", "Meister Hans")

    def test_incident_after_close_rejected(self):
        c = self._contract()
        for stage in indenture.STAGES:
            c.sign_off(stage, "Meister Hans")
            c.advance()
        with pytest.raises(ValueError):
            c.log_incident("late mischief")

    def test_empty_incident_rejected(self):
        with pytest.raises(ValueError):
            self._contract().log_incident("  ")


# -- masterpiece ---------------------------------------------------------------


class TestMasterpiece:
    def _gate(self):
        g = masterpiece.MasterpieceGate(min_jurors=2)
        g.set_rubric({"material": 7.0, "technique": 7.0})
        j1 = g.register_juror("Ada")
        j2 = g.register_juror("Bram")
        return g, j1, j2

    def _fully_scored(self, g, sub, j1, j2, v1=8.0, v2=9.0):
        for j, v in ((j1, v1), (j2, v2)):
            for criterion in ("material", "technique"):
                g.score(j, sub.id, criterion, v)

    def test_admitted_piece_joins_corpus(self):
        g, j1, j2 = self._gate()
        sub = g.submit("Cleo", "Oak Cabinet")
        self._fully_scored(g, sub, j1, j2)
        result = g.verdict(sub.id)
        assert result["verdict"] == "admitted"
        assert g.corpus() == [sub]
        standard = g.reference_standard()
        assert standard["material"] == pytest.approx(8.5)

    def test_failing_piece_rejected_not_in_corpus(self):
        g, j1, j2 = self._gate()
        sub = g.submit("Cleo", "Wobbly Stool")
        self._fully_scored(g, sub, j1, j2, v1=5.0, v2=6.0)
        assert g.verdict(sub.id)["verdict"] == "rejected"
        assert g.corpus() == []

    def test_empty_author_title_rejected(self):
        g, _, _ = self._gate()
        with pytest.raises(ValueError):
            g.submit("", "Cabinet")
        with pytest.raises(ValueError):
            g.submit("Cleo", "  ")

    def test_duplicate_juror_rejected(self):
        g, _, _ = self._gate()
        with pytest.raises(ValueError):
            g.register_juror("ada")  # case-insensitive duplicate

    def test_empty_juror_name_rejected(self):
        g, _, _ = self._gate()
        with pytest.raises(ValueError):
            g.register_juror(" ")

    def test_duplicate_submission_rejected(self):
        g, _, _ = self._gate()
        g.submit("Cleo", "Oak Cabinet")
        with pytest.raises(ValueError):
            g.submit("cleo", "oak cabinet")

    def test_submit_before_rubric_rejected(self):
        g = masterpiece.MasterpieceGate()
        with pytest.raises(ValueError):
            g.submit("Cleo", "Cabinet")

    def test_bad_rubric_rejected(self):
        g = masterpiece.MasterpieceGate()
        with pytest.raises(ValueError):
            g.set_rubric({})
        with pytest.raises(ValueError):
            g.set_rubric({"material": 11.0})
        with pytest.raises(ValueError):
            g.set_rubric({"": 7.0})

    def test_score_out_of_range_rejected(self):
        g, j1, _ = self._gate()
        sub = g.submit("Cleo", "Cabinet")
        with pytest.raises(ValueError):
            g.score(j1, sub.id, "material", 10.5)
        with pytest.raises(ValueError):
            g.score(j1, sub.id, "material", -1.0)

    def test_unknown_ids_rejected(self):
        g, j1, _ = self._gate()
        sub = g.submit("Cleo", "Cabinet")
        with pytest.raises(ValueError):
            g.score("juror-99", sub.id, "material", 8.0)
        with pytest.raises(ValueError):
            g.score(j1, "sub-99", "material", 8.0)
        with pytest.raises(ValueError):
            g.score(j1, sub.id, "gilding", 8.0)
        with pytest.raises(ValueError):
            g.verdict("sub-99")

    def test_double_score_rejected(self):
        g, j1, _ = self._gate()
        sub = g.submit("Cleo", "Cabinet")
        g.score(j1, sub.id, "material", 8.0)
        with pytest.raises(ValueError):
            g.score(j1, sub.id, "material", 9.0)

    def test_verdict_before_full_jury_rejected(self):
        g, j1, j2 = self._gate()
        sub = g.submit("Cleo", "Cabinet")
        g.score(j1, sub.id, "material", 8.0)  # incomplete
        with pytest.raises(ValueError):
            g.verdict(sub.id)

    def test_second_verdict_rejected(self):
        g, j1, j2 = self._gate()
        sub = g.submit("Cleo", "Cabinet")
        self._fully_scored(g, sub, j1, j2)
        g.verdict(sub.id)
        with pytest.raises(ValueError):
            g.verdict(sub.id)

    def test_reference_standard_empty_corpus_rejected(self):
        g, _, _ = self._gate()
        with pytest.raises(ValueError):
            g.reference_standard()


# -- compagnon -----------------------------------------------------------------


class TestCompagnon:
    def _tour(self):
        t = compagnon.RotationTour("Fritz")
        t.add_station("Lyon", "Maitre A", "joinery", "compass")
        t.add_station("Tours", "Maitre B", "carving", "square")
        return t

    def test_tour_completion_in_order(self):
        t = self._tour()
        assert t.next_station.name == "Lyon"
        t.complete_station("Lyon", "compass")
        assert t.next_station.name == "Tours"
        t.complete_station("Tours", "square")
        assert t.is_complete
        assert t.progress()["completed"] == ["Lyon", "Tours"]

    def test_empty_fields_rejected(self):
        t = compagnon.RotationTour("Fritz")
        with pytest.raises(ValueError):
            t.add_station("", "M", "S", "sym")
        with pytest.raises(ValueError):
            t.add_station("N", "M", "S", " ")
        with pytest.raises(ValueError):
            compagnon.RotationTour(" ")

    def test_duplicate_station_rejected(self):
        t = self._tour()
        with pytest.raises(ValueError):
            t.add_station("lyon", "M", "S", "sym")

    def test_out_of_order_rejected(self):
        t = self._tour()
        with pytest.raises(ValueError):
            t.complete_station("Tours", "square")

    def test_wrong_symbol_rejected(self):
        t = self._tour()
        with pytest.raises(ValueError):
            t.complete_station("Lyon", "triangle")

    def test_unknown_station_rejected(self):
        t = self._tour()
        with pytest.raises(ValueError):
            t.complete_station("Paris", "compass")

    def test_add_station_after_start_rejected(self):
        t = self._tour()
        t.complete_station("Lyon", "compass")
        with pytest.raises(ValueError):
            t.add_station("Paris", "M", "S", "sym")

    def test_complete_after_tour_done_rejected(self):
        t = self._tour()
        t.complete_station("Lyon", "compass")
        t.complete_station("Tours", "square")
        with pytest.raises(ValueError):
            t.complete_station("Tours", "square")


# -- mystery -------------------------------------------------------------------


class TestMystery:
    def _disclosure(self):
        d = mystery.TieredDisclosure()
        basics = d.add_knowledge("Sweeping the shop", 0)
        secret = d.add_knowledge("The master's temper mix", 2)
        member = d.register_member("Fritz")
        return d, basics, secret, member

    def test_tier_gating_and_promotion(self):
        d, basics, secret, member = self._disclosure()
        assert d.access(member, basics.id).title == "Sweeping the shop"
        with pytest.raises(ValueError):
            d.access(member, secret.id)
        d.record_milestone(member, "kept the oath")
        d.record_milestone(member, "seven silent months")
        assert d.promote(member) == 1
        with pytest.raises(ValueError):  # tier 2 secret still above
            d.access(member, secret.id)
        d.record_milestone(member, "returned the lost purse")
        d.record_milestone(member, "taught a junior the basics")
        assert d.promote(member) == 2
        assert d.access(member, secret.id).title == "The master's temper mix"

    def test_empty_names_rejected(self):
        d = mystery.TieredDisclosure()
        with pytest.raises(ValueError):
            d.register_member(" ")
        with pytest.raises(ValueError):
            d.add_knowledge(" ", 0)

    def test_duplicate_member_and_item_rejected(self):
        d = mystery.TieredDisclosure()
        d.register_member("Fritz")
        with pytest.raises(ValueError):
            d.register_member("fritz")
        d.add_knowledge("Basics", 0)
        with pytest.raises(ValueError):
            d.add_knowledge("basics", 1)

    def test_negative_tier_rejected(self):
        d = mystery.TieredDisclosure()
        with pytest.raises(ValueError):
            d.add_knowledge("Secret", -1)

    def test_unknown_ids_rejected(self):
        d, basics, _, member = self._disclosure()
        with pytest.raises(ValueError):
            d.access("member-99", basics.id)
        with pytest.raises(ValueError):
            d.access(member, "know-99")
        with pytest.raises(ValueError):
            d.record_milestone("member-99", "x")
        with pytest.raises(ValueError):
            d.promote("member-99")
        with pytest.raises(ValueError):
            d.member_tier("member-99")

    def test_empty_milestone_rejected(self):
        d, _, _, member = self._disclosure()
        with pytest.raises(ValueError):
            d.record_milestone(member, "  ")

    def test_promotion_without_milestones_rejected(self):
        d, _, _, member = self._disclosure()
        with pytest.raises(ValueError):
            d.promote(member)
        d.record_milestone(member, "one deed")
        with pytest.raises(ValueError):  # only 1 of 2 banked
            d.promote(member)

    def test_promotion_past_max_tier_rejected(self):
        d, _, _, member = self._disclosure()
        for i in range(4):
            d.record_milestone(member, f"deed {i}")
        d.promote(member)
        d.promote(member)
        assert d.member_tier(member) == 2
        with pytest.raises(ValueError):
            d.promote(member)


# -- hallmark ------------------------------------------------------------------


class TestHallmark:
    def _struck(self, assay_pass=True):
        p = hallmark.StruckProvenance()
        p.stamp("cup-1", "Goldsmith Ade", 0.925, assay_pass, "Warden Bex", "1300-M")
        return p

    def test_verify_checks_all_three_marks(self):
        p = self._struck()
        checks = p.verify("cup-1")
        assert checks == {
            "maker_mark": True,
            "assay_passed": True,
            "date_struck": True,
            "fraud_flagged": False,
            "verified": True,
        }

    def test_failed_assay_fails_verify(self):
        p = self._struck(assay_pass=False)
        assert p.verify("cup-1")["verified"] is False

    def test_assay_fraud_taints_assayer(self):
        p = self._struck()
        report = p.report_fraud("cup-1", 0.800)
        assert report["assayer_strikes"] == 1
        assert p.verify("cup-1")["verified"] is False
        assert p.verify("cup-1")["fraud_flagged"] is True
        record = p.assayer_record("Warden Bex")
        assert record["fraud_strikes"] == 1
        assert record["artifacts_tested"] == 1

    def test_empty_fields_rejected(self):
        p = hallmark.StruckProvenance()
        with pytest.raises(ValueError):
            p.stamp("", "M", 0.925, True, "A", "D")
        with pytest.raises(ValueError):
            p.stamp("x", " ", 0.925, True, "A", "D")
        with pytest.raises(ValueError):
            p.stamp("x", "M", 0.925, True, "", "D")

    def test_bad_fineness_rejected(self):
        p = hallmark.StruckProvenance()
        with pytest.raises(ValueError):
            p.stamp("x", "M", 0.0, True, "A", "D")
        with pytest.raises(ValueError):
            p.stamp("x", "M", 1.5, True, "A", "D")

    def test_nonboolean_assay_rejected(self):
        p = hallmark.StruckProvenance()
        with pytest.raises(ValueError):
            p.stamp("x", "M", 0.925, "pass", "A", "D")

    def test_duplicate_stamp_rejected(self):
        p = self._struck()
        with pytest.raises(ValueError):
            p.stamp("cup-1", "M", 0.925, True, "A", "D")

    def test_unknown_artifact_rejected(self):
        p = self._struck()
        with pytest.raises(ValueError):
            p.verify("cup-99")
        with pytest.raises(ValueError):
            p.report_fraud("cup-99", 0.5)

    def test_fraud_report_on_failed_assay_rejected(self):
        p = self._struck(assay_pass=False)
        with pytest.raises(ValueError):
            p.report_fraud("cup-1", 0.5)

    def test_bad_actual_fineness_rejected(self):
        p = self._struck()
        with pytest.raises(ValueError):
            p.report_fraud("cup-1", 0.0)

    def test_unknown_assayer_record_rejected(self):
        p = self._struck()
        with pytest.raises(ValueError):
            p.assayer_record("Warden Nobody")
        with pytest.raises(ValueError):
            p.assayer_record(" ")


# -- zunftlade -----------------------------------------------------------------


class TestZunftlade:
    def _chest(self):
        c = zunftlade.MultiKeyChest(quorum=2)
        o1 = c.add_officer("Alderman A")
        o2 = c.add_officer("Alderman B")
        c.add_officer("Alderman C")
        c.file_record("charter", "the original charter")
        return c, o1, o2

    def test_amendment_requires_quorum(self):
        c, o1, o2 = self._chest()
        assert c.propose_amendment("charter", "amended charter", o1) == 1
        with pytest.raises(ValueError):  # single signature: chest stays shut
            c.ratify("charter")
        assert c.propose_amendment("charter", "amended charter", o2) == 2
        record = c.ratify("charter")
        assert record.content == "amended charter"
        assert record.amendments == 1

    def test_lineage_walks_the_chain(self):
        c, _, _ = self._chest()
        c.register_training("Fritz", "Meister Hans")
        c.register_training("Meister Hans", "Old Groot")
        assert c.lineage("Fritz") == ["Fritz", "Meister Hans", "Old Groot"]
        assert c.lineage("Old Groot") == ["Old Groot"]

    def test_bad_quorum_rejected(self):
        with pytest.raises(ValueError):
            zunftlade.MultiKeyChest(quorum=1)

    def test_empty_officer_rejected(self):
        c = zunftlade.MultiKeyChest(quorum=2)
        with pytest.raises(ValueError):
            c.add_officer(" ")

    def test_duplicate_officer_rejected(self):
        c = zunftlade.MultiKeyChest(quorum=2)
        c.add_officer("Alderman A")
        with pytest.raises(ValueError):
            c.add_officer("alderman a")

    def test_duplicate_record_rejected(self):
        c, _, _ = self._chest()
        with pytest.raises(ValueError):
            c.file_record("charter", "another")

    def test_empty_record_fields_rejected(self):
        c = zunftlade.MultiKeyChest(quorum=2)
        with pytest.raises(ValueError):
            c.file_record(" ", "content")
        with pytest.raises(ValueError):
            c.file_record("r1", "  ")

    def test_unknown_ids_rejected(self):
        c, o1, _ = self._chest()
        with pytest.raises(ValueError):
            c.propose_amendment("missing", "x", o1)
        with pytest.raises(ValueError):
            c.propose_amendment("charter", "x", "officer-99")
        with pytest.raises(ValueError):
            c.ratify("missing")

    def test_double_signing_rejected(self):
        c, o1, _ = self._chest()
        c.propose_amendment("charter", "amended", o1)
        with pytest.raises(ValueError):
            c.propose_amendment("charter", "amended", o1)

    def test_conflicting_pending_amendment_rejected(self):
        c, o1, o2 = self._chest()
        c.propose_amendment("charter", "version one", o1)
        with pytest.raises(ValueError):
            c.propose_amendment("charter", "version two", o2)

    def test_ratify_without_pending_rejected(self):
        c, _, _ = self._chest()
        with pytest.raises(ValueError):
            c.ratify("charter")

    def test_lineage_unknown_person_rejected(self):
        c, _, _ = self._chest()
        with pytest.raises(ValueError):
            c.lineage("Nobody")
        with pytest.raises(ValueError):
            c.lineage("  ")

    def test_self_training_rejected(self):
        c, _, _ = self._chest()
        with pytest.raises(ValueError):
            c.register_training("Fritz", "Fritz")


# -- sloyd ---------------------------------------------------------------------


class TestSloyd:
    def _curriculum(self):
        cur = sloyd.GradedCurriculum("Woodwork I")
        cur.add_exercise("e1", "The wedge", ("sawing",))
        cur.add_exercise("e2", "The pin", ("boring",))
        cur.add_exercise("e3", "The box", ("dovetailing",))
        return cur

    def test_prerequisite_chain_enforced(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        learner.attempt("e1")
        learner.complete("e1")
        learner.attempt("e2")
        learner.complete("e2")
        learner.attempt("e3")
        learner.complete("e3")
        progress = learner.progress()
        assert progress["completed"] == ["e1", "e2", "e3"]
        assert progress["remaining"] == []

    def test_attempt_without_prerequisites_rejected(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        with pytest.raises(ValueError):
            learner.attempt("e2")
        with pytest.raises(ValueError):
            learner.attempt("e3")

    def test_multiple_new_variables_rejected(self):
        cur = sloyd.GradedCurriculum("Bad")
        with pytest.raises(ValueError):
            cur.add_exercise("e1", "The wedge", ("sawing", "boring"))
        with pytest.raises(ValueError):
            cur.add_exercise("e1", "The wedge", ())

    def test_empty_names_rejected(self):
        cur = sloyd.GradedCurriculum("Woodwork")
        with pytest.raises(ValueError):
            cur.add_exercise("", "The wedge", ("sawing",))
        with pytest.raises(ValueError):
            cur.add_exercise("e1", " ", ("sawing",))
        with pytest.raises(ValueError):
            cur.add_exercise("e1", "The wedge", (" ",))
        with pytest.raises(ValueError):
            cur.learner("  ")
        with pytest.raises(ValueError):
            sloyd.GradedCurriculum(" ")

    def test_duplicate_exercise_rejected(self):
        cur = self._curriculum()
        with pytest.raises(ValueError):
            cur.add_exercise("e1", "Other", ("planing",))

    def test_unknown_exercise_rejected(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        with pytest.raises(ValueError):
            learner.attempt("e9")
        with pytest.raises(ValueError):
            learner.complete("e9")

    def test_double_attempt_rejected(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        learner.attempt("e1")
        with pytest.raises(ValueError):
            learner.attempt("e1")

    def test_complete_before_attempt_rejected(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        with pytest.raises(ValueError):
            learner.complete("e1")

    def test_double_complete_rejected(self):
        cur = self._curriculum()
        learner = cur.learner("Fritz")
        learner.attempt("e1")
        learner.complete("e1")
        with pytest.raises(ValueError):
            learner.complete("e1")
        with pytest.raises(ValueError):
            learner.attempt("e1")

    def test_pacing_is_per_learner(self):
        cur = self._curriculum()
        fast = cur.learner("Fast")
        slow = cur.learner("Slow")
        fast.attempt("e1")
        fast.complete("e1")
        assert slow.progress()["completed"] == []
        assert fast.progress()["completed"] == ["e1"]


# -- kontor --------------------------------------------------------------------


class TestKontor:
    def _posting(self):
        return kontor.ImmersionPosting(
            host_domain="Bruges Kontor",
            practices=["laws", "accounting", "correspondence"],
            duration_days=3,
        )

    def test_completion_requires_everything(self):
        p = self._posting()
        p.submit_evidence("laws", "copied the Lubeck statutes")
        with pytest.raises(ValueError):  # practices + days still missing
            p.complete()
        p.submit_evidence("accounting", "balanced the ledger")
        p.submit_evidence("correspondence", "drafted three letters")
        with pytest.raises(ValueError):  # days still missing
            p.complete()
        for _ in range(3):
            p.serve_day()
        result = p.complete()
        assert result["completed"] is True
        assert result["days_served"] == 3
        assert p.status()["completed"] is True

    def test_empty_domain_rejected(self):
        with pytest.raises(ValueError):
            kontor.ImmersionPosting("", ["laws"], 3)

    def test_bad_practices_rejected(self):
        with pytest.raises(ValueError):
            kontor.ImmersionPosting("Bruges", [], 3)
        with pytest.raises(ValueError):
            kontor.ImmersionPosting("Bruges", ["laws", "laws"], 3)
        with pytest.raises(ValueError):
            kontor.ImmersionPosting("Bruges", [" "], 3)

    def test_nonpositive_duration_rejected(self):
        with pytest.raises(ValueError):
            kontor.ImmersionPosting("Bruges", ["laws"], 0)

    def test_unknown_practice_rejected(self):
        p = self._posting()
        with pytest.raises(ValueError):
            p.submit_evidence("fencing", "a duel")

    def test_empty_evidence_rejected(self):
        p = self._posting()
        with pytest.raises(ValueError):
            p.submit_evidence("laws", "  ")

    def test_serve_day_after_complete_rejected(self):
        p = self._posting()
        for practice in ["laws", "accounting", "correspondence"]:
            p.submit_evidence(practice, "evidence")
        for _ in range(3):
            p.serve_day()
        p.complete()
        with pytest.raises(ValueError):
            p.serve_day()
        with pytest.raises(ValueError):
            p.submit_evidence("laws", "more")
        with pytest.raises(ValueError):
            p.complete()

    def test_missing_reports_gaps(self):
        p = self._posting()
        p.serve_day()
        gaps = p.missing()
        assert gaps["practices_without_evidence"] == [
            "laws",
            "accounting",
            "correspondence",
        ]
        assert gaps["days_remaining"] == 2
