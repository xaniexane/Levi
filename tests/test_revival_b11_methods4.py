"""Tests for revival batch B11 (methods 4): trivium, ratio, monitorial,
pecia, duplex, t5pipe, therbligs, pneumatic.

Each module gets >= 3 meaningful tests against its real mechanisms.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------- trivium

from levi.revival.trivium import Artifact, GateError, Stage


def _grammared() -> Artifact:
    a = Artifact(topic="photosynthesis")
    a.capture_term("chlorophyll", "the pigment that captures light")
    a.capture_term("stoma", "leaf pore for gas exchange")
    a.capture_term("thylakoid", "membrane where light reactions run")
    a.complete_grammar()
    return a


def test_trivium_full_pipeline():
    a = _grammared()
    a.add_premise("chlorophyll absorbs light in thylakoids")
    a.add_premise("light reactions split water at the thylakoid")
    arg = a.build_argument("photosynthesis converts light to chemical energy")
    assert arg.conclusion
    a.teach_back(
        "Chlorophyll in the thylakoid captures light; stomata admit CO2; "
        "together they show photosynthesis converts light to chemical energy."
    )
    a.complete_rhetoric()
    a.record_measure("quantum yield", 0.125, "mol/mol")
    a.complete()
    assert a.stage is Stage.COMPLETE
    assert a.status()["stage"] == "COMPLETE"


def test_trivium_logic_gated_on_vocabulary():
    a = Artifact(topic="x")
    with pytest.raises(GateError):
        a.add_premise("too early")  # still GRAMMAR
    a.capture_term("a", "def a")
    with pytest.raises(GateError):  # gate refuses: too few terms
        a.complete_grammar()


def test_trivium_rhetoric_demands_coverage():
    a = _grammared()
    a.add_premise("p1 about chlorophyll")
    a.add_premise("p2 about stoma")
    a.build_argument("conclusion about photosynthesis")
    a.teach_back("I do not remember anything")  # no terms, no conclusion
    with pytest.raises(GateError):
        a.complete_rhetoric()  # coverage 0% -> gate closed


def test_trivium_measure_gated_on_rhetoric():
    a = _grammared()
    with pytest.raises(GateError):
        a.record_measure("m", 1.0)  # still LOGIC, measure is later


# ---------------------------------------------------------------- ratio

from levi.revival.ratio import LessonPlan, Ratio, RatioError  # noqa: E402


def _plan() -> LessonPlan:
    p = LessonPlan(subject="logic")
    p.set_prelection("Walk through the syllogism: major, minor, conclusion.")
    p.add_review_item("Recite the four figures of the syllogism.")
    p.add_thesis(
        "All valid syllogisms are sound arguments",
        ["Soundness needs true premises, validity does not"],
    )
    p.published = True
    return p


def test_ratio_full_loop():
    r = Ratio()
    r.register(_plan())
    report = r.teach(
        "logic",
        {
            "All valid syllogisms are sound arguments": "A valid syllogism can have false premises, so validity does not need true premises — soundness does."
        },
    )
    assert report.prelection_delivered
    assert report.repetitions_done == 1
    claim, held, score = report.disputations[0]
    assert held and score > 0.5


def test_ratio_edition_incorporates_field_notes():
    r = Ratio()
    plan = _plan()
    r.register(plan)
    plan.add_field_note(
        "Students stumble on the prelection's syllogism walk-through.", "tutor-1"
    )
    plan.add_field_note("Add a repetition drill on the figures.", "tutor-2")
    edition = plan.new_edition(editor="rector")
    assert edition.version == 2
    assert edition.published
    assert any("walk-through" in entry for entry in [edition.prelection])
    assert len(edition.review_items) == 2
    assert plan.notes[0].incorporated
    r.register(edition)
    assert r.current("logic").version == 2
    history = r.editions("logic")
    assert [e["version"] for e in history] == [1, 2]


def test_ratio_disputatio_fails_on_empty_defense():
    r = Ratio()
    with pytest.raises(RatioError):
        r.defend(_plan(), _plan().theses[0], "   ")


def test_ratio_teach_unknown_subject():
    r = Ratio()
    with pytest.raises(RatioError):
        r.teach("astronomy", {})


# ---------------------------------------------------------------- monitorial

from levi.revival.monitorial import Lesson, MonitorialError, MonitorialSchool  # noqa: E402


def _school() -> MonitorialSchool:
    s = MonitorialSchool("Master")
    s.add_monitor("M1")
    s.add_pupil("M1", "P1")
    s.add_pupil("M1", "P2")
    lesson = Lesson("multiplication")
    lesson.add("2 x 3", "six")
    lesson.add("4 x 5", "twenty")
    for node in ("M1", "P1", "P2"):
        s.set_lesson(lesson, node)
    return s


def test_monitorial_cascade_with_propagation():
    s = _school()
    passed, score = s.drill("M1", ["six", "twenty"])
    assert passed
    results = s.drill_group("M1", {"P1": ["six", "twenty"], "P2": ["five", "twenty"]})
    assert results["P1"][0] is True
    assert results["P2"][0] is False  # missed one item
    report = s.cascade_report()
    branch = report["branches"][0]
    assert branch["monitor"] == "M1"
    assert branch["pupils_tested"] == 2
    assert branch["pupils_passed"] == 1
    assert branch["re_drill"] is True
    assert report["weak_branches"] == ["M1"]


def test_monitorial_protocol_refuses_untaught_monitor():
    s = _school()
    with pytest.raises(MonitorialError):  # M1 never passed its own drill
        s.drill_group("M1", {"P1": ["six", "twenty"], "P2": ["six", "twenty"]})


def test_monitorial_drill_arity_checked():
    s = _school()
    with pytest.raises(MonitorialError):
        s.drill("M1", ["six"])  # 2 items expected


def test_monitorial_master_report_counts():
    s = _school()
    s.drill("M1", ["six", "twenty"])
    s.drill_group("M1", {"P1": ["six", "twenty"], "P2": ["six", "twenty"]})
    report = s.cascade_report()
    assert report["weak_branches"] == []  # 100% pass -> no re-drill
    assert report["pupils"] == 2


# ---------------------------------------------------------------- pecia

from levi.revival.pecia import Exemplar, PeciaError, Stationer  # noqa: E402


TEXT = "line one\nline two\nline three\nline four\nline five\nline six"


def test_pecia_parallel_copy_and_reassembly():
    exemplar = Exemplar.from_text("demo", TEXT, chunk_lines=2)
    assert len(exemplar) == 3
    stationer = Stationer(exemplar)
    copies = {}
    for worker in ("w1", "w2", "w3"):
        idx = stationer.checkout(worker)
        copies[worker] = (idx, exemplar.pecia(idx))  # perfect copies
    for worker, (_idx, text) in copies.items():
        assert stationer.checkin(worker, text) is True
    assert stationer.reassemble() == TEXT


def test_pecia_rejects_bad_copy_and_returns_it_to_pool():
    exemplar = Exemplar.from_text("demo", TEXT, chunk_lines=2)
    stationer = Stationer(exemplar)
    idx = stationer.checkout("w1")
    assert stationer.checkin("w1", "WRONG TEXT") is False
    assert stationer.progress()["rejections"] == 1
    # rejected pecia is back in the pool: w1 can check out the same index again
    idx2 = stationer.checkout("w1")
    assert idx2 == idx
    assert stationer.checkin("w1", exemplar.pecia(idx2)) is True


def test_pecia_one_pecia_at_a_time():
    exemplar = Exemplar.from_text("demo", TEXT, chunk_lines=2)
    stationer = Stationer(exemplar)
    stationer.checkout("w1")
    with pytest.raises(PeciaError):
        stationer.checkout("w1")  # already holds one


def test_pecia_reassemble_refuses_gaps():
    exemplar = Exemplar.from_text("demo", TEXT, chunk_lines=2)
    stationer = Stationer(exemplar)
    idx = stationer.checkout("w1")
    stationer.checkin("w1", exemplar.pecia(idx))
    with pytest.raises(PeciaError) as exc:
        stationer.reassemble()
    assert "unverified" in str(exc.value)


# ---------------------------------------------------------------- duplex

from levi.revival.duplex import Comparer, Mismatch, Status, require_agreement, verify  # noqa: E402


def test_duplex_agreement_accepts():
    r = verify(lambda x: x * 2, lambda x: x + x, 21)
    assert r.status is Status.AGREE and r.agreed and r.value == 42


def test_duplex_disagreement_flagged_with_both_values():
    r = verify(lambda x: x * 2, lambda x: x * 3, 21)
    assert r.status is Status.DISAGREE
    assert r.value_a == 42 and r.value_b == 63 and r.delta == 21
    assert not r.agreed


def test_duplex_worker_error_assumed_not_hoped_away():
    def boom(x):
        raise ValueError("slipped")

    r = verify(boom, lambda x: x, 1)
    assert r.status is Status.WORKER_ERROR
    assert "worker A failed" in r.error


def test_duplex_tolerance_and_require():
    r = verify(lambda: 1.0, lambda: 1.0005, tol=0.001)
    assert r.agreed
    r2 = verify(lambda: 1.0, lambda: 1.0005, tol=0.0001)
    assert not r2.agreed
    with pytest.raises(Mismatch):
        require_agreement(lambda x: x * 2, lambda x: x * 3, 21)
    assert require_agreement(lambda x: x * 2, lambda x: x + x, 21) == 42


def test_duplex_comparer_log_and_summary():
    c = Comparer()
    c.check("good", lambda: 1, lambda: 1)
    c.check("bad", lambda: 1, lambda: 2)
    summary = c.summary()
    assert summary == {"total": 2, "AGREE": 1, "DISAGREE": 1, "WORKER_ERROR": 0}
    assert [e["label"] for e in c.log()] == ["good", "bad"]


# ---------------------------------------------------------------- t5pipe

from levi.revival.t5pipe import OP, Pipeline, T5Error, ref  # noqa: E402


def test_t5pipe_decomposed_polynomial():
    # 2x^3 + 3 evaluated at x=2, one op per stage:
    # x^2 = x*x; x^3 = x^2*x; 2x^3; +3
    p = Pipeline("poly")
    x2 = p.add(OP.MUL, 2.0, 2.0)
    x3 = p.add(OP.MUL, ref(x2), 2.0)
    t = p.add(OP.MUL, 2.0, ref(x3))
    p.add(OP.ADD, ref(t), 3.0)
    cards = p.run()
    assert [c.output for c in cards] == [4.0, 8.0, 16.0, 19.0]
    assert p.result() == 19.0


def test_t5pipe_refuses_forward_reference_and_bad_arity():
    p = Pipeline()
    with pytest.raises(T5Error):
        p.add(OP.ADD, ref(5), 1.0)  # card 5 does not exist yet
    with pytest.raises(T5Error):
        p.add(OP.ADD, 1.0)  # ADD needs 2 operands


def test_t5pipe_audit_trail_is_inspectable():
    p = Pipeline("demo")
    p.add(OP.DIV, 10.0, 4.0)
    p.add(OP.NEG, ref(0))
    audit = p.audit()
    assert "[0] div(10.0, 4.0) = 2.5" in audit
    assert "[1] neg(2.5) = -2.5" in audit


def test_t5pipe_division_by_zero_refused():
    p = Pipeline()
    p.add(OP.DIV, 1.0, 0.0)
    with pytest.raises(T5Error):
        p.run()


# ---------------------------------------------------------------- therbligs

from levi.revival.therbligs import MotionSequence, Therblig, TherbligError  # noqa: E402


def _task() -> MotionSequence:
    s = MotionSequence("assemble widget")
    s.add(Therblig.SEARCH, 12.0)
    s.add(Therblig.FIND, 2.0)
    s.add(Therblig.SELECT, 5.0)
    s.add(Therblig.GRASP, 1.0)
    s.add(Therblig.TRANSPORT_LOADED, 4.0)
    s.add(Therblig.POSITION, 3.0)
    s.add(Therblig.ASSEMBLE, 20.0)
    s.add(Therblig.USE, 30.0)
    s.add(Therblig.AVOIDABLE_DELAY, 15.0)
    s.add(Therblig.REST, 10.0)
    return s


def test_therbligs_analysis_names_waste():
    report = _task().analyze()
    assert report.total_seconds == 102.0
    assert report.waste_seconds == 32.0  # 12 + 5 + 15
    assert report.waste_fraction == pytest.approx(round(32 / 102, 3))
    names = [f.therblig.name for f in report.waste_motions]
    assert names == ["SEARCH", "SELECT", "AVOIDABLE_DELAY"]
    assert all(f.recommendation for f in report.waste_motions)


def test_therbligs_optimize_eliminates_waste():
    seq, changelog = _task().optimize()
    report = seq.analyze()
    assert report.waste_seconds == 0.0
    assert len(changelog) == 3
    remaining = [m.therblig.name for m in seq.motions()]
    assert "AVOIDABLE_DELAY" not in remaining
    assert "REST" in remaining  # rest is not waste; fatigue recovery stays


def test_therbligs_budget_sorted_and_summary():
    summary = _task().summary()
    assert "waste 31%" in summary  # 32/102 = 31.4%
    report = _task().analyze()
    top = list(report.budget.items())[0]
    assert top[0] == "USE" and top[1] == 30.0


def test_therbligs_empty_sequence_refused():
    with pytest.raises(TherbligError):
        MotionSequence("nothing").analyze()


# ---------------------------------------------------------------- pneumatic

from levi.revival.pneumatic import Dispatcher, DispatchError, WorkItem  # noqa: E402


HUBS = ["central", "north", "south"]


def test_pneumatic_dispatcher_splits_lanes():
    d = Dispatcher(HUBS)
    items = [
        WorkItem(
            "digest",
            "weekly report",
            from_hub="north",
            to_hub="central",
            scheduled=True,
        ),
        WorkItem(
            "backup", "nightly dump", from_hub="south", to_hub="central", scheduled=True
        ),
        WorkItem(
            "complaint",
            "angry customer",
            from_hub="north",
            to_hub="central",
            needs_judgment=True,
            context="VIP account, handle personally",
        ),
        WorkItem("override", "special", override="courier"),
    ]
    report = d.route(items)
    assert report.trunk_items == 2
    assert report.courier_items == 2
    lane_of = {i: lane for i, lane, _ in report.decisions}
    assert lane_of == {
        "digest": "trunk",
        "backup": "trunk",
        "complaint": "courier",
        "override": "courier",
    }
    assert len(report.batches) == 2  # north->central, south->central
    courier = next(a for a in report.assignments if a.item_id == "complaint")
    assert courier.context == "VIP account, handle personally"


def test_pneumatic_judgment_beats_scheduled():
    d = Dispatcher(HUBS)
    lane, reason = d.classify(WorkItem("x", "y", scheduled=True, needs_judgment=True))
    assert lane == "courier" and "judgment" in reason


def test_pneumatic_flush_groups_hub_to_hub():
    d = Dispatcher(HUBS)
    for i in range(3):
        d.trunk.collect(WorkItem(f"m{i}", "bulk", from_hub="north", to_hub="central"))
    d.trunk.collect(WorkItem("m3", "bulk", from_hub="south", to_hub="central"))
    batches = d.trunk.flush()
    assert sorted(len(b.item_ids) for b in batches) == [1, 3]
    assert d.trunk.pending() == 0  # flushed


def test_pneumatic_unknown_hub_refused():
    d = Dispatcher(HUBS)
    with pytest.raises(DispatchError):
        d.trunk.collect(WorkItem("x", "y", from_hub="nowhere", to_hub="central"))
