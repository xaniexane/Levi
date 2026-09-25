"""Hermetic tests for forgotten-methods wave-3 entries 29-40 (Part A).

Modules: pecia, duplex, t5, therbligs, pneumatic, codebook, qcodes,
prowords, chappe, quipu, kriegsspiel, randgame.

Hermetic: no network, deterministic, persistence isolated via LEVI_HOME
pointed at tmp_path. Stdlib only.
"""

import pytest

from core.levi.methods import (
    chappe,
    codebook,
    duplex,
    kriegsspiel,
    pecia,
    pneumatic,
    prowords,
    qcodes,
    quipu,
    randgame,
    t5,
    therbligs,
)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))


# ===========================================================================
# 29. pecia — university stationer discipline
# ===========================================================================


def _stationer(store="pec-t"):
    ex = pecia.Exemplar("T", "line1\nline2\nline3\nline4\n")
    return pecia.Stationer(ex, ex.split(2), store=store)


def test_pecia_one_pecia_per_scribe():
    st = _stationer()
    st.checkout("ada")
    with pytest.raises(pecia.LeaseError):
        st.checkout("ada")


def test_pecia_verify_and_assemble():
    st = _stationer()
    p0 = st.checkout("ada")
    st.submit("ada", p0.pecia_id, p0.text)  # exact copy verifies
    assert st.progress() == (1, 2)
    with pytest.raises(pecia.AssemblyError):
        st.assemble()  # refuses while a pecia is unverified
    p1 = st.checkout("bob")
    st.submit("bob", p1.pecia_id, p1.text)
    text, report = st.assemble()
    assert text == "line1\nline2\nline3\nline4\n"
    assert len(report) == 2


def test_pecia_corrupt_copy_rejected():
    st = _stationer()
    p0 = st.checkout("ada")
    with pytest.raises(pecia.VerificationError):
        st.submit("ada", p0.pecia_id, p0.text + "CORRUPT")


def test_pecia_persists_progress():
    st = _stationer(store="pec-persist")
    p0 = st.checkout("ada")
    st.submit("ada", p0.pecia_id, p0.text)
    st.save()
    ex = pecia.Exemplar("T", "line1\nline2\nline3\nline4\n")
    st2 = pecia.Stationer(ex, ex.split(2), store="pec-persist")
    assert st2.progress() == (1, 2)


# ===========================================================================
# 30. duplex — N-version execution
# ===========================================================================


def test_duplex_agreement():
    v = duplex.verify({"a": lambda: 42, "b": lambda: 42})
    assert v.value == 42
    assert v.per_path == {"a": 42, "b": 42}


def test_duplex_divergence_quarantined():
    with pytest.raises(duplex.DivergenceQuarantined):
        duplex.verify({"a": lambda: 1, "b": lambda: 2})


def test_duplex_verify_n():
    v = duplex.verify_n(lambda: "x", lambda: "x", lambda: "x", names=("p1", "p2", "p3"))
    assert v.value == "x"


# ===========================================================================
# 31. t5 — load-bearing pipeline
# ===========================================================================


def test_t5_pipeline_run():
    pipe = t5.Pipeline(
        "p", [t5.Stage("double", lambda x: x * 2), t5.Stage("inc", lambda x: x + 1)]
    )
    rep = pipe.run(21)
    assert rep.ok and rep.final == 43
    assert [c.stage for c in rep.cards] == ["double", "inc"]


def test_t5_stage_check_fails_closed():
    # check() validates the stage's INPUT before it runs
    pipe = t5.Pipeline("p", [t5.Stage("s", lambda x: x, check=lambda y: y >= 0)])
    with pytest.raises(t5.StageCheckError) as exc_info:
        pipe.run(-5)
    card = exc_info.value.cards[0]
    assert not card.ok and "check" in card.error.lower()


def test_t5_microbatch():
    assert list(t5.microbatch(range(7), 3)) == [[0, 1, 2], [3, 4, 5], [6]]
    with pytest.raises(ValueError):
        list(t5.microbatch(range(3), 0))


# ===========================================================================
# 32. therbligs — task-step analysis
# ===========================================================================


def test_therbligs_describe_known():
    d = therbligs.describe("Search")
    assert d["code"] == "Sh"


def test_therbligs_analyze_totals():
    tp = therbligs.TaskPlan("morning", store="th-t")
    tp.add_step("Search", "find the thread", 12.0)
    tp.add_step("Select", "pick the reply", 3.0)
    a = tp.analyze()
    assert a.total_seconds == pytest.approx(15.0)
    assert a.recommendations  # waste gets named, not hidden
    assert "15.0s" in a.summary()


def test_therbligs_unknown_rejected():
    tp = therbligs.TaskPlan("x", store="th-t2")
    with pytest.raises(ValueError):
        tp.add_step("Teleport", "nope", 1.0)


# ===========================================================================
# 33. pneumatic — deterministic dispatch
# ===========================================================================


def test_pneumatic_routes_by_rule():
    rt = pneumatic.RoutingTable()
    rt.add_rule(".*urgent.*", pneumatic.COURIER, reason="triage")
    d = pneumatic.Dispatcher(rt)
    dec = d.dispatch(pneumatic.Task("t1", "email", "urgent: fix prod"))
    assert dec.channel == pneumatic.COURIER
    assert dec.task_id == "t1"
    assert d.courier_log and d.courier_log[0]["task_id"] == "t1"


def test_pneumatic_tube_tasks_held_then_flushed():
    d = pneumatic.Dispatcher(pneumatic.RoutingTable())
    dec = d.dispatch(pneumatic.Task("t2", "digest", "weekly rollup"))
    assert dec.channel == pneumatic.TUBE
    # deny-closed: held in the manifest, not dropped, not sent
    assert [t.task_id for t in d.held()] == ["t2"]
    assert not d.courier_log
    manifest = d.flush_tubes()
    assert manifest["count"] == 1
    assert d.held() == []


def test_pneumatic_default_rule_urgent_goes_courier():
    d = pneumatic.Dispatcher(pneumatic.RoutingTable())
    dec = d.dispatch(pneumatic.Task("t3", "alert", "prod is down", urgency=9))
    assert dec.channel == pneumatic.COURIER
    assert dec.rule == "<default>"


def test_pneumatic_bad_rule_rejected():
    rt = pneumatic.RoutingTable()
    with pytest.raises(ValueError):
        rt.add_rule("([invalid", pneumatic.TUBE)


# ===========================================================================
# 34. codebook — symbol compression with edition control
# ===========================================================================


def test_codebook_roundtrip():
    cb = codebook.Codebook("t", store="cb-t")
    cb.add("A1", "alpha")
    encoded, subs = cb.encode("say alpha now")
    assert encoded == "say A1 now"
    decoded, _ = cb.decode(encoded)
    assert decoded == "say alpha now"
    assert subs == [("alpha", "A1")]


def test_codebook_collision_refused():
    cb = codebook.Codebook("t", store="cb-t2")
    cb.add("A1", "alpha")
    with pytest.raises(codebook.CollisionError):
        cb.add("A1", "beta")
    cb.add("A1", "alpha")  # identical re-add is a no-op


def test_codebook_unknown_code_refused():
    cb = codebook.Codebook("t", store="cb-t3")
    with pytest.raises(codebook.UnknownCode):
        cb.lookup("ZZ")


def test_codebook_edition_divergence_visible():
    a = codebook.Codebook("t", store="cb-a")
    b = codebook.Codebook("t", store="cb-b")
    a.add("A1", "alpha")
    b.add("A1", "alpha")
    assert a.check_sync(b) == []
    b.add("B2", "beta")
    assert a.check_sync(b)  # divergence is listed, not hidden


# ===========================================================================
# 35. qcodes — compressed signaling
# ===========================================================================


def test_qcodes_parse_query():
    _sig = qcodes.parse("QTH?")
    assert qcodes.is_qcode("QTH")
    assert "QTH" in qcodes.query("QTH")


def test_qcodes_unknown_refused():
    with pytest.raises(qcodes.UnknownSignal):
        qcodes.parse("ZZZ")


def test_qcodes_status_report():
    report = qcodes.status_report("morning-net", "QTH", "in position")
    assert "QTH" in report and "morning-net" in report


# ===========================================================================
# 36. prowords — readback discipline
# ===========================================================================


def test_prowords_readback_mismatch():
    e = prowords.Exchange()
    ins = e.order("turn left")
    with pytest.raises(prowords.ReadbackMismatch):
        e.read_back(ins, "turn right")


def test_prowords_acknowledged_exchange():
    e = prowords.Exchange()
    ins = e.say("alpha this is bravo")
    assert e.read_back(ins, "alpha this is bravo") is True
    e.acknowledge(ins, prowords.Ack.WILCO)
    assert len(e.log) == 2  # read-back confirmation + typed acknowledgment


def test_prowords_correct_marks_superseded():
    e = prowords.Exchange()
    ins = e.order("turn left")
    fixed = e.correct(ins, "turn right")
    assert fixed.text == "turn right"
    assert any("correct" in entry.get("proword", "").lower() for entry in e.log)


# ===========================================================================
# 37. chappe — codebook-compressed signaling
# ===========================================================================


def test_chappe_encode_decode():
    c = chappe.Codebook("t", store="ch-t")
    c.set_entry(3, 42, "go")
    assert c.encode("go") == (3, 42)
    assert c.decode(3, 42) == "go"


def test_chappe_message_roundtrip():
    c = chappe.Codebook("t", store="ch-t2")
    c.set_entry(3, 42, "go")
    c.set_entry(1, 7, "stop")
    msg = c.encode_message(["go", "stop"])
    assert c.decode_message(msg) == ["go", "stop"]


def test_chappe_unknown_phrase_refused():
    c = chappe.Codebook("t", store="ch-t3")
    with pytest.raises(chappe.UnknownPhrase):
        c.encode("nope")


# ===========================================================================
# 38. quipu — knot-encoded tallies with checksums
# ===========================================================================


def test_quipu_knot_roundtrip():
    for value in (0, 7, 42, 507, 9999):
        assert quipu.decode_knots(quipu.encode_knots(value)) == value


def test_quipu_cord_verify_and_rollup():
    k = quipu.Khipu("rev", store="kh-t")
    k.add_cord("sales")
    k.add_cord("sales.online")
    k.record("sales.online", 507)
    assert k.verify() == []  # no checksum violations
    assert k.rollup() == 507
    assert "507" in k.summary()


def test_quipu_unknown_cord_refused():
    k = quipu.Khipu("rev2", store="kh-t2")
    with pytest.raises(KeyError):
        k.record("nope", 1)


def test_quipu_verify_reports_missing_pendant():
    k = quipu.Khipu("rev3", store="kh-t3")
    k.add_cord("sales")
    k.record("sales", 507)
    assert k.verify() == []
    k._cords["root"].children.append("ghost")  # structural corruption
    problems = k.verify()  # reports, never raises
    assert any("ghost" in p and "missing" in p for p in problems)


# ===========================================================================
# 39. kriegsspiel — umpired adversarial testing
# ===========================================================================


def _umpire():
    u = kriegsspiel.Umpire(10, 10, seed=1)
    u.add_unit(kriegsspiel.Unit("a1", "red", 1, 1))
    u.add_unit(kriegsspiel.Unit("b1", "blue", 8, 8))
    return u


def test_kriegsspiel_turn_advances():
    u = _umpire()
    u.submit_orders("red", [kriegsspiel.Order("a1", "move", dx=1, dy=0)])
    u.submit_orders("blue", [kriegsspiel.Order("b1", "move", dx=-1, dy=0)])
    u.resolve_turn()
    assert u.turn == 1
    assert u.units["a1"].x == 2


def test_kriegsspiel_fog_of_war():
    u = _umpire()
    u.submit_orders("red", [])
    u.submit_orders("blue", [])
    obs = u.resolve_turn()
    red_obs = obs["red"]
    assert red_obs.side == "red"
    # blue is 7+ away: outside red's sight — fog holds
    assert all(e["unit_id"] != "b1" for e in red_obs.seen_enemy)


def test_kriegsspiel_unknown_unit_order_rejected():
    u = _umpire()
    with pytest.raises(kriegsspiel.OrderRejected):
        u.submit_orders("red", [kriegsspiel.Order("ghost", "move")])


def test_kriegsspiel_debrief_and_outcome():
    u = _umpire()
    u.submit_orders("red", [])
    u.submit_orders("blue", [])
    u.resolve_turn()
    d = u.debrief()
    assert d["turns"] == 1
    assert "winner" in u.outcome()


# ===========================================================================
# 40. randgame — assumption-testing scenario games
# ===========================================================================


def _game(rounds=3):
    wm = randgame.WorldModel(
        "m", step=lambda s, mv: (dict(s, n=s.get("n", 0) + 1), [f"ev{mv}"])
    )
    sc = randgame.Scenario("s", "d", rounds=rounds)
    teams = [
        randgame.Team("A", wm, lambda s, r: {"choice": "a"}),
        randgame.Team("B", wm, lambda s, r: {"choice": "b"}),
    ]
    return randgame.Game(sc, teams)


def test_randgame_runs_all_rounds():
    g = _game()
    g.run()
    d = g.debrief()
    assert d["rounds"] == 3
    assert all(t["final_state"]["n"] == 3 for t in d["teams"])


def test_randgame_divergence_flagged():
    w1 = randgame.WorldModel("m1", step=lambda s, mv: (dict(s, n=1), []))
    w2 = randgame.WorldModel("m2", step=lambda s, mv: (dict(s, n=2), []))
    sc = randgame.Scenario("s", "d", rounds=2)
    g = randgame.Game(
        sc,
        [
            randgame.Team("A", w1, lambda s, r: 1),
            randgame.Team("B", w2, lambda s, r: 1),
        ],
    )
    g.run()
    assert g.debrief()["divergent_rounds"] == 2  # count of divergent rounds
    assert all(d["differing_keys"] == ["n"] for d in g.debrief()["divergences"])


def test_randgame_summary_mentions_agreement():
    g = _game(rounds=1)
    g.run()
    assert "agreed" in g.summary()
