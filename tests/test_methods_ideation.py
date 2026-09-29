"""Tests for the LEVI ideation wave (2026-09-29): the divergence kit.

Covers: synectics (Gordon's excursion), brainwriting (Method 6-3-5),
gordon (the blind-session technique), value (Miles's value analysis).
One test class per module: the core mechanism AND every deny-closed
rejection (pytest.raises(ValueError)).
"""

import pytest

from levi.methods import brainwriting, gordon, synectics, value


# ---------------------------------------------------------------------------
# synectics — the excursion: gather strange material, force-fit it back
# ---------------------------------------------------------------------------


class TestSynectics:
    def _excursion(self):
        ex = synectics.Excursion("design a quieter lawnmower")
        ex.begin()
        ex.add_analogy("direct", "a cat stalking — silent paws")
        ex.add_analogy("personal", "I am the blade, screaming through air")
        ex.add_analogy("symbolic", "loud silence")
        ex.add_analogy("fantasy", "grass that cuts itself in a dream")
        return ex

    def test_full_excursion_restates_the_problem(self):
        ex = self._excursion()
        ex.force_fit("loud silence", "enclose the blade like a silencer")
        restated = ex.restate_problem("a lawnmower that contains its own noise")
        assert ex.state == synectics.ST_CLOSED
        assert restated == "a lawnmower that contains its own noise"
        assert ex.restatement() == restated

    def test_all_four_analogy_kinds_accepted(self):
        ex = synectics.Excursion("p").begin()
        for kind in synectics.ANALOGY_KINDS:
            ex.add_analogy(kind, "some %s material" % kind)
        assert len(ex.analogies()) == 4

    def test_rejects_blank_problem(self):
        with pytest.raises(ValueError):
            synectics.Excursion("   ")

    def test_rejects_unknown_analogy_kind(self):
        ex = synectics.Excursion("p").begin()
        with pytest.raises(ValueError):
            ex.add_analogy("quantum", "spooky action")

    def test_rejects_force_fit_before_gather(self):
        ex = synectics.Excursion("p").begin()
        with pytest.raises(ValueError):
            ex.force_fit("nothing gathered", "an insight")

    def test_rejects_force_fit_citing_ungathered_analogy(self):
        ex = synectics.Excursion("p").begin()
        ex.add_analogy("direct", "a cat stalking")
        with pytest.raises(ValueError):
            ex.force_fit("a dog barking", "an insight")

    def test_rejects_restatement_before_force_fit(self):
        ex = self._excursion()
        with pytest.raises(ValueError):
            ex.restate_problem("too early")

    def test_rejects_anything_after_close(self):
        ex = self._excursion()
        ex.force_fit("loud silence", "enclose the blade")
        ex.restate_problem("contained noise")
        with pytest.raises(ValueError):
            ex.add_analogy("direct", "late material")
        with pytest.raises(ValueError):
            ex.force_fit("loud silence", "late insight")


# ---------------------------------------------------------------------------
# brainwriting — Method 635: silent rounds, slot invariant enforced
# ---------------------------------------------------------------------------


class TestBrainwriting:
    def _drive(self, participants=("a", "b", "c"), per_round=2):
        sess = brainwriting.Session("quiet lawnmower", list(participants), ideas_per_round=per_round)
        n = len(participants)
        for rnd in range(n):
            for sheet in range(n):
                holder = participants[(sheet - rnd) % n]
                sess.submit(sheet, holder, ["%s-r%d-s%d-i%d" % (holder, rnd, sheet, k) for k in range(per_round)])
        return sess

    def test_full_session_hits_slot_invariant(self):
        sess = self._drive()
        assert sess.expected_slots() == 3 * 3 * 2
        subs = sess.finish()
        assert len(subs) == 9  # 3 sheets x 3 rounds
        assert len(sess.harvest()) == 18
        # every sheet seen by every mind
        holders = {s.author for s in subs}
        assert holders == {"a", "b", "c"}

    def test_rejects_too_few_participants(self):
        with pytest.raises(ValueError):
            brainwriting.Session("t", ["solo"])

    def test_rejects_duplicate_participants(self):
        with pytest.raises(ValueError):
            brainwriting.Session("t", ["a", "a", "b"])

    def test_rejects_wrong_idea_count(self):
        sess = brainwriting.Session("t", ["a", "b", "c"], ideas_per_round=2)
        with pytest.raises(ValueError):
            sess.submit(0, "a", ["only one"])

    def test_rejects_wrong_author_for_sheet(self):
        sess = brainwriting.Session("t", ["a", "b", "c"], ideas_per_round=2)
        with pytest.raises(ValueError):
            sess.submit(0, "b", ["x", "y"])  # round 0, sheet 0 belongs to a

    def test_rejects_duplicate_submit_same_round(self):
        sess = brainwriting.Session("t", ["a", "b", "c"], ideas_per_round=2)
        sess.submit(0, "a", ["x", "y"])
        with pytest.raises(ValueError):
            sess.submit(0, "a", ["p", "q"])

    def test_rejects_early_finish(self):
        sess = brainwriting.Session("t", ["a", "b", "c"], ideas_per_round=2)
        sess.submit(0, "a", ["x", "y"])
        with pytest.raises(ValueError):
            sess.finish()

    def test_rejects_submit_after_finish(self):
        sess = self._drive()
        sess.finish()
        with pytest.raises(ValueError):
            sess.submit(0, "a", ["x", "y"])


# ---------------------------------------------------------------------------
# gordon — the blind session: the group never hears the real problem
# ---------------------------------------------------------------------------


class TestGordon:
    def _session(self):
        s = gordon.BlindSession("design a quieter lawnmower", "remove grass silently", "lead")
        s.register("amy")
        s.register("bo")
        s.contribute("amy", "magnetic levitation trimmer")
        s.contribute("bo", "grass that never grows")
        return s

    def test_reveal_returns_sealed_problem_once(self):
        s = self._session()
        out = s.reveal()
        assert out["real_problem"] == "design a quieter lawnmower"
        assert len(out["harvest"]) == 2
        assert s.revealed is True

    def test_participants_only_see_abstraction(self):
        s = gordon.BlindSession("real", "abstract function", "lead")
        assert s.function_prompt == "abstract function"
        # no attribute path exposes the sealed string before reveal
        assert "real" not in s.function_prompt

    def test_rejects_leader_as_participant(self):
        s = gordon.BlindSession("real", "fn", "lead")
        with pytest.raises(ValueError):
            s.register("lead")

    def test_rejects_late_registration(self):
        s = self._session()
        with pytest.raises(ValueError):
            s.register("cy")

    def test_rejects_unregistered_contributor(self):
        s = gordon.BlindSession("real", "fn", "lead")
        s.register("amy")
        with pytest.raises(ValueError):
            s.contribute("stranger", "an idea")

    def test_rejects_reveal_with_no_contributions(self):
        s = gordon.BlindSession("real", "fn", "lead")
        s.register("amy")
        with pytest.raises(ValueError):
            s.reveal()

    def test_rejects_double_reveal_and_post_reveal_contribution(self):
        s = self._session()
        s.reveal()
        with pytest.raises(ValueError):
            s.reveal()
        with pytest.raises(ValueError):
            s.contribute("amy", "too late")


# ---------------------------------------------------------------------------
# value — Miles: verb-noun functions, cost on functions, waste itemized
# ---------------------------------------------------------------------------


class TestValue:
    def _study(self):
        st = value.ValueStudy("lawnmower blade")
        f1 = st.add_function("cut", "grass", value.USE, necessity=1.0)
        f2 = st.add_function("look", "sharp", value.ESTEEM, necessity=0.5)
        f3 = st.add_function("impress", "neighbors", value.ESTEEM, necessity=0.0)
        st.assign_cost(f1, 30.0)
        st.assign_cost(f2, 8.0)
        st.assign_cost(f3, 12.0)
        return st, f1, f2, f3

    def test_score_is_function_over_cost(self):
        st, _, _, _ = self._study()
        s = st.score()
        assert s["total_cost"] == 50.0
        assert s["weighted_function"] == pytest.approx(1.5)
        assert s["value_ratio"] == pytest.approx(1.5 / 50.0)

    def test_waste_names_zero_necessity_functions(self):
        st, _, _, f3 = self._study()
        assert st.waste() == [f3]
        assert st.score()["waste_cost"] == pytest.approx(12.0)

    def test_function_phrase_is_verb_noun(self):
        fn = value.Function("support", "weight", value.USE)
        assert fn.phrase == "support weight"

    def test_rejects_blank_verb_or_noun(self):
        with pytest.raises(ValueError):
            value.Function(" ", "weight", value.USE)
        with pytest.raises(ValueError):
            value.Function("support", "", value.USE)

    def test_rejects_bad_classification(self):
        with pytest.raises(ValueError):
            value.Function("support", "weight", "vibes")

    def test_rejects_negative_cost(self):
        st = value.ValueStudy("x")
        fid = st.add_function("cut", "grass", value.USE)
        with pytest.raises(ValueError):
            st.assign_cost(fid, -5.0)

    def test_rejects_score_with_no_functions(self):
        with pytest.raises(ValueError):
            value.ValueStudy("x").score()

    def test_rejects_score_with_zero_total_cost(self):
        st = value.ValueStudy("x")
        st.add_function("cut", "grass", value.USE)
        with pytest.raises(ValueError):
            st.score()
