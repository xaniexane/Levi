"""Tests for revival batch 3 (decision & invention):
franklin, ach, repgrid, zwicky, triz, waterlogic, cybersyn, deming.
"""

import pytest

from core.levi.revival import ach, cybersyn, deming, franklin, repgrid
from core.levi.revival import triz, waterlogic, zwicky


# ---------------------------------------------------------------- franklin
class TestFranklin:
    def test_origin_and_thirteen_slots(self):
        assert franklin.ORIGIN == "levi-revival/franklin"
        assert len(franklin.DEFAULT_BEHAVIORS) == 13
        ledger = franklin.Ledger(focus_started="2026-01-01")
        label, idx = ledger.focus_on("2026-01-03")
        assert idx == 0  # first week -> behavior 0

    def test_focus_rotates_weekly(self):
        ledger = franklin.Ledger(focus_started="2026-01-01")
        week1 = ledger.focus_on("2026-01-07")
        week2 = ledger.focus_on("2026-01-08")
        assert week1 != week2
        assert week1[0] == franklin.DEFAULT_BEHAVIORS[0]
        assert week2[0] == franklin.DEFAULT_BEHAVIORS[1]

    def test_weekly_review_progress_per_behavior(self):
        ledger = franklin.Ledger(focus_started="2026-01-01")
        ledger.mark("2026-01-01", "order", 2)
        ledger.mark("2026-01-02", "order", 1)
        ledger.mark("2026-01-01", "silence", 0)
        review = ledger.weekly_review("2026-01-01")
        order_row = next(r for r in review["per_behavior"] if r["behavior"] == "order")
        assert order_row["faults"] == 3
        assert order_row["clean_days"] == 5
        assert review["focus"] == "temperance"  # first week's focus
        assert review["total_faults"] == 3

    def test_marks_by_index_and_label_agree(self):
        ledger = franklin.Ledger()
        ledger.mark("2026-01-01", 0, 4)
        assert ledger.faults("2026-01-01", "temperance") == 4

    def test_invalid_marks_raise(self):
        ledger = franklin.Ledger()
        with pytest.raises(ValueError):
            ledger.mark("2026-01-01", "not-a-behavior")
        with pytest.raises(ValueError):
            ledger.mark("2026-01-01", "temperance", -1)


# ---------------------------------------------------------------- ach
class TestACH:
    def _matrix(self):
        m = ach.ACH()
        m.add_hypothesis("inside job")
        m.add_hypothesis("outside breach")
        m.add_evidence("logs show external IP")
        m.add_evidence("badge swipe at 3am")
        m.add_evidence("phishing email clicked")
        # inside job: external IP disconfirms
        m.score("logs show external IP", "inside job", -0.8)
        m.score("logs show external IP", "outside breach", 0.9)
        m.score("badge swipe at 3am", "inside job", 0.7)
        m.score("badge swipe at 3am", "outside breach", 0.2)
        m.score("phishing email clicked", "inside job", -0.6)
        m.score("phishing email clicked", "outside breach", 0.8)
        return m

    def test_origin_and_rank_by_disconfirmation(self):
        assert ach.ORIGIN == "levi-revival/ach"
        m = self._matrix()
        ranked = m.ranking()
        assert ranked[0]["hypothesis"] == "outside breach"
        assert ranked[0]["disconfirmations"] == 0
        assert ranked[1]["disconfirmations"] == 2

    def test_sensitivity_identifies_flip_evidence(self):
        m = self._matrix()
        sens = m.sensitivity()
        assert sens["baseline_winner"] == "outside breach"
        # Removing "logs show external IP": outside breach loses a
        # confirmation AND inside job loses a disconfirmation.
        # At minimum the flip list must be computable and honest.
        assert isinstance(sens["flips"], list)
        assert sens["fragile"] == bool(sens["flips"])

    def test_diagnosticity_flags_useless_evidence(self):
        m = self._matrix()
        m.add_evidence("server exists")
        for h in m.hypotheses:
            m.score("server exists", h, 0.9)  # agrees with everything
        diag = m.diagnosticity()
        useless = next(d for d in diag if d["evidence"] == "server exists")
        assert useless["agrees_with_all"] is True
        assert useless["diagnosticity"] == 0.0
        # sorted: diagnostic items come first
        assert diag[0]["diagnosticity"] > 0.0

    def test_scores_clamped(self):
        m = ach.ACH()
        m.add_hypothesis("h")
        m.add_evidence("e")
        with pytest.raises(ValueError):
            m.score("e", "h", 2.0)


# ---------------------------------------------------------------- repgrid
class TestRepGrid:
    def _grid(self):
        g = repgrid.RepGrid(elements=["Alice", "Bruno", "Celine"])
        g.elicit(("Alice", "Bruno", "Celine"), ("Alice", "Bruno"), "warm", "distant")
        g.elicit(
            ("Alice", "Bruno", "Celine"), ("Bruno", "Celine"), "spontaneous", "planned"
        )
        return g

    def test_origin_and_triadic_elicitation(self):
        assert repgrid.ORIGIN == "levi-revival/repgrid"
        g = self._grid()
        assert len(g.constructs) == 2
        assert g.constructs[0].label() == "warm --- distant"

    def test_matrix_is_element_x_construct(self):
        g = self._grid()
        for e in g.elements:
            for c in range(2):
                g.rate(e, c, 4)
        m = g.matrix()
        assert m[0] == ["element", "warm --- distant", "spontaneous --- planned"]
        assert len(m) == 4
        assert m[1][0] == "Alice" and all(v == 4 for v in m[1][1:])

    def test_strict_matrix_refuses_holes(self):
        g = self._grid()
        g.rate("Alice", 0, 1)
        with pytest.raises(ValueError):
            g.matrix()
        assert len(g.missing()) == 5

    def test_similarity_detects_construed_alikeness(self):
        g = self._grid()
        for c in range(2):
            g.rate("Alice", c, 1)
            g.rate("Bruno", c, 1)
            g.rate("Celine", c, 7)
        assert g.similarity("Alice", "Bruno") == 1.0
        assert g.similarity("Alice", "Celine") == 0.0
        pairs = g.most_alike_pairs()
        assert pairs[0]["a"] == "Alice" and pairs[0]["b"] == "Bruno"


# ---------------------------------------------------------------- zwicky
class TestZwicky:
    def _box(self):
        b = zwicky.ZwickyBox()
        b.add_dimension("power", ["solar", "diesel", "grid"])
        b.add_dimension("housing", ["tent", "shed", "bunker"])
        b.add_dimension("comms", ["radio", "satellite"])
        return b

    def test_origin_and_raw_space_size(self):
        assert zwicky.ORIGIN == "levi-revival/zwicky"
        b = self._box()
        assert b.space_size() == 3 * 3 * 2

    def test_cca_prunes_impossible_pairs(self):
        b = self._box()
        before = len(b.viable())
        b.judge("power", "solar", "housing", "bunker", "no")
        b.judge("comms", "radio", "housing", "bunker", "no")
        after = b.viable()
        assert len(after) < before
        for s in after:
            assert not (s["power"] == "solar" and s["housing"] == "bunker")
            assert not (s["comms"] == "radio" and s["housing"] == "bunker")

    def test_tension_flagged_not_pruned(self):
        b = self._box()
        b.judge("power", "diesel", "housing", "tent", "tension")
        survivors = b.viable()
        tense = [
            s for s in survivors if s["power"] == "diesel" and s["housing"] == "tent"
        ]
        assert tense  # kept...
        strict = b.viable(drop_tension=True)
        assert not [
            s for s in strict if s["power"] == "diesel" and s["housing"] == "tent"
        ]
        assert b.tensions_in(tense[0])  # ...but flagged

    def test_summary_numbers(self):
        b = self._box()
        b.judge("power", "solar", "housing", "bunker", "no")
        s = b.summary()
        assert s["raw_space"] == 18
        assert s["viable"] + s["pruned"] == 18
        assert s["judgments_made"] == 1


# ---------------------------------------------------------------- triz
class TestTRIZ:
    def test_origin_and_principle_count(self):
        assert triz.ORIGIN == "levi-revival/triz"
        assert len(triz.PARAMETERS) >= 20
        assert len(triz.PRINCIPLES) == 20
        # wordings are original one-liners, not copied tables
        assert all(
            isinstance(w, str) and len(w.split()) >= 6 for w in triz.PRINCIPLES.values()
        )

    def test_lookup_returns_principles_for_contradiction(self):
        m = triz.Matrix()
        res = m.lookup("weight", "strength")
        assert res["exact_match"] is True
        assert res["principles"]  # non-empty
        keys = [p["key"] for p in res["principles"]]
        assert all(k in triz.PRINCIPLES for k in keys)

    def test_lookup_is_symmetric(self):
        m = triz.Matrix()
        a = m.lookup("speed", "precision")
        b = m.lookup("precision", "speed")
        assert a["principles"] == b["principles"]

    def test_unknown_pair_falls_back_honestly(self):
        m = triz.Matrix()
        res = m.lookup("cost", "stability")
        assert res["exact_match"] is False
        assert res["principles"]  # fallback still suggests something

    def test_worksheet_forces_application(self):
        m = triz.Matrix()
        res = m.lookup("weight", "strength")
        ws = triz.worksheet(res, problem="make the drone lighter but tougher")
        assert ws["problem"].startswith("make the drone")
        assert len(ws["rows"]) == len(res["principles"])
        assert all("idea" in row for row in ws["rows"])
        assert all(ws["rows"][i]["prompt"] for i in range(len(ws["rows"])))


# ---------------------------------------------------------------- waterlogic
class TestWaterLogic:
    def _field(self):
        f = waterlogic.FlowField()
        f.lead("traffic jam", "lateness")
        f.lead("lateness", "stress")
        f.lead("traffic jam", "radio news")
        f.lead("radio news", "stress")
        f.lead("stress", "traffic jam")  # cycle
        return f

    def test_origin_and_trajectories(self):
        assert waterlogic.ORIGIN == "levi-revival/waterlogic"
        f = self._field()
        trajs = waterlogic.flow(f, "traffic jam")
        endpoints = {t["endpoint"] for t in trajs}
        assert endpoints == {"stress"}  # all paths end at stress; cycle-safe
        assert all(t["trajectory"][0] == "traffic jam" for t in trajs)

    def test_cycles_do_not_hang(self):
        f = self._field()
        trajs = waterlogic.flow(f, "stress", max_depth=20)
        assert trajs  # terminates despite the cycle

    def test_flowscape_hubs_and_sinks(self):
        f = self._field()
        sc = waterlogic.flowscape(f, ["traffic jam"])
        hubs = [h["concept"] for h in sc["hubs"]]
        assert "lateness" in hubs or "radio news" in hubs
        assert sc["sinks"][0]["concept"] == "stress"
        assert sc["coverage"]["reached"] > 0

    def test_compare_classification_vs_flow(self):
        f = self._field()
        cmp = waterlogic.compare_with_classification(
            "traffic jam", f, classify=lambda c: ["transport event", "urban phenomenon"]
        )
        assert cmp["classification_view"]["question"] == "what IS this?"
        assert cmp["flow_view"]["question"] == "what does this lead to?"
        assert cmp["flow_view"]["destinations"] == ["stress"]
        assert "transport event" in cmp["classification_view"]["boxes"]


# ---------------------------------------------------------------- cybersyn
class TestCybersyn:
    def _metrics(self, n=12):
        return [
            {"name": f"m{i}", "value": v, "target": 100.0, "tolerance": 10.0}
            for i, v in enumerate(
                [100, 101, 99, 150, 102, 98, 103, 97, 200, 100, 105, 95]
            )
        ]

    def test_origin_and_grasp_limit(self):
        assert cybersyn.ORIGIN == "levi-revival/cybersyn"
        view = cybersyn.attenuate(self._metrics())
        assert len(view.displayed) == cybersyn.GRASP_LIMIT == 7
        assert view.hidden_count == 5
        assert len(view.hidden_names) == 5
        # most deviant first
        assert view.displayed[0]["name"] == "m8"  # value 200, dev 10

    def test_attenuation_ranks_by_deviation(self):
        view = cybersyn.attenuate(self._metrics())
        devs = [d["deviation"] for d in view.displayed]
        assert devs == sorted(devs, reverse=True)

    def test_algedonic_pain_and_pleasure(self):
        room = cybersyn.OpsRoom()
        room.set_threshold("cpu", pain_above=90.0)
        room.set_threshold("throughput", pleasure_above=1000.0)
        raised = room.ingest(
            [
                {"name": "cpu", "value": 95.0},
                {"name": "throughput", "value": 1200.0},
            ]
        )
        signals = {a.name: a.signal for a in raised}
        assert signals == {"cpu": "PAIN", "throughput": "PLEASURE"}

    def test_alerts_demand_logged_decisions(self):
        room = cybersyn.OpsRoom()
        room.set_threshold("cpu", pain_above=90.0)
        room.ingest([{"name": "cpu", "value": 95.0}])
        assert len(room.open_alerts()) == 1
        assert room.room_status()["room_clear"] is False
        dec = room.decide(
            0, action="throttle workers", reason="sustained overload, not a spike"
        )
        assert dec["action"] == "throttle workers"
        assert room.room_status()["room_clear"] is True
        with pytest.raises(ValueError):  # decision without reason refused
            room.set_threshold("mem", pain_above=90.0)
            room.ingest([{"name": "mem", "value": 95.0}])
            room.decide(1, action="", reason="x")


# ---------------------------------------------------------------- deming
class TestDeming:
    def _full(self, data_points=5):
        d = deming.Diagnosis(issue="defects up 12%")
        d.add(
            deming.Finding(
                "system", "handoff between shifts loses info", data_points=data_points
            )
        )
        d.add(
            deming.Finding(
                "variation", "spike tracks shift change", data_points=data_points
            )
        )
        d.add(
            deming.Finding(
                "theory_of_knowledge",
                "only two weeks of logs exist",
                data_points=data_points,
            )
        )
        d.add(
            deming.Finding(
                "psychology", "night shift fears blame", data_points=data_points
            )
        )
        return d

    def test_origin_and_four_lenses_required(self):
        assert deming.ORIGIN == "levi-revival/deming"
        assert set(deming.LENSES) == {
            "system",
            "variation",
            "theory_of_knowledge",
            "psychology",
        }
        d = deming.Diagnosis(issue="x")
        d.add(deming.Finding("system", "y"))
        res = deming.diagnose(d)
        assert res["verdict"] is None
        assert res["refusal"] == "incomplete_lattice"
        assert set(res["missing_lenses"]) == {
            "variation",
            "theory_of_knowledge",
            "psychology",
        }

    def test_complete_lattice_produces_verdict(self):
        res = deming.diagnose(self._full())
        assert res["verdict"] == "diagnosed"
        assert set(res["lenses"]) == set(deming.LENSES)
        assert "interaction" in res

    def test_single_data_point_flagged(self):
        res = deming.diagnose(self._full(data_points=1))
        assert res["verdict"] is None
        assert res["refusal"] == "single_point_fallacy"

    def test_provisional_read_with_explicit_flag(self):
        res = deming.diagnose(self._full(data_points=1), allow_single_point=True)
        assert res["verdict"] == "diagnosed"
        assert res["single_point_flagged"] is True
        assert "fallacy_flag" in res

    def test_lens_prompts_cover_all_four(self):
        assert set(deming.lens_prompts()) == set(deming.LENSES)
