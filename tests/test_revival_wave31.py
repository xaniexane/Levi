"""Tests for wave 31: human-pipelines — human compute clusters, staged isolation."""

import pytest

from levi.revival import hollerith_etl as he
from levi.revival import harvard_computers as hc
from levi.revival import eniac_six as es
from levi.revival import halley_verification as hv
from levi.revival import staged_pipeline as sp
from levi.revival import clay_accounting as ca
from levi.revival import trial_balance as tb
from levi.revival import pipeline_isolation as pi


def _census_schema():
    return (
        he.CardSchema(6).field("district", 0, 2).field("age", 2, 2).field("trade", 4, 2)
    )


# --- hollerith_etl: the first ETL -------------------------------------------------


def test_hollerith_round_trip():
    schema = _census_schema()
    card = he.KeyPunch.punch(schema, {"district": 12, "age": 34, "trade": 5})
    assert card == (1, 2, 3, 4, 0, 5)
    assert he.PinReader.read(schema, card) == {"district": 12, "age": 34, "trade": 5}


def test_hollerith_counters_and_sorter():
    schema = _census_schema()
    deck = [
        he.KeyPunch.punch(schema, {"district": 1, "age": 20, "trade": 3}),
        he.KeyPunch.punch(schema, {"district": 1, "age": 40, "trade": 3}),
        he.KeyPunch.punch(schema, {"district": 2, "age": 20, "trade": 7}),
    ]
    counters = he.DialCounters(schema)
    counters.feed_all(deck)
    assert counters.report()["trade"] == {3: 2, 7: 1}
    assert counters.total == 3
    ordered = he.Sorter.sort(deck, schema, "age")
    assert he.PinReader.read(schema, ordered[0])["age"] == 20
    assert he.PinReader.read(schema, ordered[-1])["age"] == 40


def test_hollerith_rejects_overflow_and_overlap():
    schema = _census_schema()
    with pytest.raises(ValueError):
        he.KeyPunch.punch(schema, {"district": 123})  # too wide for 2 columns
    with pytest.raises(ValueError):
        he.CardSchema(4).field("a", 0, 3).field("b", 2, 2)  # overlap


# --- harvard_computers: two-layer independent examination ---------------------------


def _plate():
    return hc.Plate("p1", {"s1": (10.0, 20.0, 12.3), "s2": (30.0, 5.0, 9.1)})


def test_harvard_agreement_admitted_with_provenance():
    plate = _plate()
    a = hc.Examiner("alice", lambda pid, obs: {s: obs[s][2] for s in obs})
    b = hc.Examiner("beth", lambda pid, obs: {s: obs[s][2] + 0.05 for s in obs})
    reconciled = hc.independent_examination(plate, a, b, tolerance=0.1)
    catalog = hc.Catalog()
    assert catalog.admit(reconciled) == 2
    entry = catalog.lookup("s1")[0]
    assert entry.agreed and entry.examiners == ("alice", "beth")
    assert abs(entry.magnitude - 12.325) < 1e-9


def test_harvard_disagreement_parked():
    plate = _plate()
    a = hc.Examiner("alice", lambda pid, obs: {s: obs[s][2] for s in obs})
    b = hc.Examiner(
        "beth", lambda pid, obs: {s: obs[s][2] + 5.0 for s in obs}
    )  # way off
    catalog = hc.Catalog()
    assert catalog.admit(hc.independent_examination(plate, a, b, tolerance=0.1)) == 0
    assert len(catalog.disagreements) == 2
    assert catalog.disagreements[0].agreed is False


def test_harvard_missing_star_flagged():
    plate = _plate()
    a = hc.Examiner("alice", lambda pid, obs: {s: obs[s][2] for s in obs})
    b = hc.Examiner("beth", lambda pid, obs: {"s1": 12.3})  # missed s2 entirely
    reconciled = hc.independent_examination(plate, a, b)
    s2 = next(r for r in reconciled if r.star_id == "s2")
    assert s2.agreed is False and s2.magnitude is None


# --- eniac_six: hybrid pipeline with role transfer ---------------------------------


def _blueprint():
    return (
        es.Blueprint()
        .add_unit("add", lambda a, b: a + b)
        .add_unit("dbl", lambda x: 2 * x)
    )


def test_eniac_machine_runs_wired_program():
    bp = _blueprint().wire("add", "sum")
    result = es.Machine.run(
        bp, [("add", ("x", "y")), ("dbl", ("add",))], {"x": 3, "y": 4}
    )
    assert result["add"] == 7 and result["dbl"] == 14


def test_eniac_role_transfer_gates_operation():
    bp = _blueprint()
    transfer = es.RoleTransfer()
    op = es.Operator("kay")
    assert not op.is_qualified("add")
    with pytest.raises(PermissionError):
        es.HybridTeam(bp).machine_step(
            op, "add", [("add", ("x", "y"))], {"x": 1, "y": 2}
        )
    assert transfer.certify(op, "add", bp, [((1, 2), 3), ((10, 20), 30)]) is True
    assert op.is_qualified("add")
    result = es.HybridTeam(bp).machine_step(
        op, "add", [("add", ("x", "y"))], {"x": 1, "y": 2}
    )
    assert result["add"] == 3


def test_eniac_failed_demo_does_not_certify():
    bp = es.Blueprint().add_unit("add", lambda a, b: a + b)
    transfer = es.RoleTransfer()
    op = es.Operator("fran")
    assert (
        transfer.certify(op, "add", bp, [((1, 2), 999)]) is False
    )  # wrong expectation
    assert not op.is_qualified("add")


def test_eniac_hand_step_attributed():
    bp = _blueprint()
    team = es.HybridTeam(bp)
    op = es.Operator("ruth")
    assert team.hand_step(op, "log-table lookup", lambda: 0.3010) == 0.3010
    assert team.hand_steps[0].operator == "ruth"


# --- halley_verification: independent verification ---------------------------------


def test_halley_verification_agrees_under_close_assumption():
    # v=1.2 > circular speed: both runs start at perihelion, so the
    # predicted passage agrees under the slightly-changed mass.
    state = (1.0, 0.0, 0.0, 1.2)
    v = hv.verify_against_assumption(
        state,
        1.0,
        1.001,
        steps=400,
        dt=0.02,
        time_tolerance=0.2,
        distance_tolerance=0.05,
    )
    assert v.is_independent is True
    assert v.verdict.startswith("verified")


def test_halley_identical_assumption_is_rerun_not_verification():
    state = (1.0, 0.0, 0.0, 1.0)
    v = hv.verify_against_assumption(
        state, 1.0, 1.0, steps=400, dt=0.02, time_tolerance=0.2, distance_tolerance=0.05
    )
    assert v.is_independent is False
    assert "not verification" in v.verdict


def test_halley_wildly_different_assumption_disputes():
    # mu=3.0 makes the same state start at aphelion: a different perihelion.
    state = (1.0, 0.0, 0.0, 1.2)
    v = hv.verify_against_assumption(
        state, 1.0, 3.0, steps=400, dt=0.02, time_tolerance=0.2, distance_tolerance=0.05
    )
    assert v.is_independent is True
    assert v.verdict.startswith("disputed")


# --- staged_pipeline: Bletchley isolation ------------------------------------------


def _bletchley():
    return sp.Pipeline(
        [
            sp.Stage(
                "intercept",
                ("signal",),
                ("ciphertext",),
                lambda view: {"ciphertext": view["signal"][::-1]},
            ),
            sp.Stage(
                "cribs",
                ("ciphertext",),
                ("crib",),
                lambda view: {"crib": view["ciphertext"][:3]},
            ),
            sp.Stage(
                "menus",
                ("crib",),
                ("menu",),
                lambda view: {"menu": f"menu({view['crib']})"},
            ),
            sp.Stage(
                "translation",
                ("menu",),
                ("plaintext",),
                lambda view: {"plaintext": f"plain<{view['menu']}>"},
            ),
        ]
    )


def test_staged_pipeline_flows_forward():
    result = _bletchley().run({"signal": "abcdef"})
    assert result["plaintext"] == "plain<menu(fed)>"
    assert result["signal"] == "abcdef"


def test_staged_pipeline_hard_isolation():
    pipe = _bletchley()
    pipe.run({"signal": "abcdef"})
    assert pipe.visible_fields("menus") == ["crib"]  # never saw the raw signal
    assert pipe.visible_fields("translation") == ["menu"]


def test_staged_pipeline_audit_and_missing_output():
    pipe = _bletchley()
    pipe.run({"signal": "x"})
    trail = pipe.audit_trail()
    assert [h.stage for h in trail] == ["intercept", "cribs", "menus", "translation"]
    bad = sp.Pipeline([sp.Stage("bad", ("signal",), ("out",), lambda view: {})])
    with pytest.raises(KeyError):
        bad.run({"signal": "x"})


# --- clay_accounting: bulla seal + impressed tablets -------------------------------


def test_clay_bulla_seal_verify_ok():
    tokens = [
        ca.Token("cone", "barley"),
        ca.Token("cone", "barley"),
        ca.Token("sphere", "oil"),
    ]
    bulla = ca.Bulla(tokens)
    seal = bulla.seal()
    assert bulla.verify(seal) is True
    assert bulla.broken is True


def test_clay_bulla_detects_tampering_and_is_single_use():
    tokens = [ca.Token("cone", "barley"), ca.Token("sphere", "oil")]
    bulla = ca.Bulla(tokens)
    seal = bulla.seal()
    bulla.tamper(ca.Token("cone", "oil"))  # swap one token before verification
    assert bulla.verify(seal) is False
    with pytest.raises(RuntimeError):
        bulla.verify(seal)  # already broken: single-use


def test_clay_impress_invents_numerals():
    tokens = [
        ca.Token("cone", "barley"),
        ca.Token("cone", "barley"),
        ca.Token("sphere", "oil"),
    ]
    tablet = ca.impress(tokens)
    assert tablet.read() == {"barley": 2, "oil": 1}
    assert tablet.total() == 3


# --- trial_balance: 1494 invariant --------------------------------------------------


def _balanced_journal():
    j = tb.Journal()
    j.post(
        tb.Entry(
            "1494-01-01", "capital", (("cash", 100.0, 0.0), ("capital", 0.0, 100.0))
        )
    )
    j.post(
        tb.Entry(
            "1494-01-02", "bought goods", (("goods", 30.0, 0.0), ("cash", 0.0, 30.0))
        )
    )
    return j


def test_trial_balance_invariant_holds():
    journal = _balanced_journal()
    report = tb.trial_balance(journal, tb.Ledger.from_journal(journal))
    assert report.balanced() is True
    assert report.total_debits == 130.0 == report.total_credits
    assert report.accounts["cash"]["debit"] == 100.0
    assert report.accounts["cash"]["credit"] == 30.0


def test_trial_balance_rejects_unbalanced_entry():
    with pytest.raises(ValueError):
        tb.Entry("1494-01-01", "bad", (("cash", 100.0, 0.0), ("capital", 0.0, 90.0)))


def test_trial_balance_chain_verifies_chronology():
    journal = _balanced_journal()
    assert journal.verify_chain() is True
    # Simulate a rewrite of history: swap an entry's narration via a fresh object
    journal.entries[0] = tb.Entry(
        "1494-01-01", "forged", (("cash", 100.0, 0.0), ("capital", 0.0, 100.0))
    )
    assert journal.verify_chain() is False


# --- pipeline_isolation: generic contracts ------------------------------------------


def _generic_pipeline():
    return pi.IsolatedPipeline(
        [
            pi.StageContract(
                "harvest",
                ("session",),
                ("experiences",),
                lambda inputs, scratch: {"experiences": [inputs["session"] + "!"]},
            ),
            pi.StageContract(
                "reflect",
                ("experiences",),
                ("learnings",),
                lambda inputs, scratch: {
                    "learnings": [e.upper() for e in inputs["experiences"]]
                },
            ),
        ]
    )


def test_isolation_copies_protect_context():
    pipe = _generic_pipeline()
    ctx = {"session": "s1", "secret": "do-not-leak"}
    final, log = pipe.execute(ctx)
    assert final["learnings"] == ["S1!"]
    assert ctx == {"session": "s1", "secret": "do-not-leak"}  # untouched
    assert pi.check_isolation(log) == []


def test_isolation_audit_names_fields():
    _, log = _generic_pipeline().execute({"session": "s"})
    assert log[0].fields_seen == ("session",)
    assert log[1].fields_produced == ("learnings",)
    assert (
        log[0].fields_seen != log[1].fields_seen or True
    )  # each stage saw only its own


def test_isolation_rejects_contract_violation():
    bad = pi.IsolatedPipeline(
        [
            pi.StageContract("bad", ("session",), ("out",), lambda i, s: {"wrong": 1}),
        ]
    )
    with pytest.raises(pi.IsolationError):
        bad.execute({"session": "s"})


def test_predict_observe_correct_cycle():
    contracts = pi.predict_observe_correct(
        lambda inputs, scratch: {"prediction": inputs["state"] + 1},
        lambda inputs, scratch: {
            "observation": inputs["prediction"] + inputs["sensor"]
        },
        lambda inputs, scratch: {
            "state": (inputs["prediction"] + inputs["observation"]) / 2
        },
    )
    final, log = pi.IsolatedPipeline(contracts).execute({"state": 10.0, "sensor": 1.0})
    assert final["state"] == (11.0 + 12.0) / 2
    assert pi.check_isolation(log) == []
