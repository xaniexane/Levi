"""Acceptance tests T1-T10 for the scan-mind (Phase-2 flagship, middle team).

Working names only — **naming is Chauncey's**.

These tests verify the scan-mind as a deterministic decision procedure:
frozen process image in, ordered rung evaluation, staged intents flushed
through a permission gate, typed faults, one receipt per cycle. No
sentience or subjective-experience claims are made or implied.

Hermetic: no network, no daemons, no HOME writes (tmp_path only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.gtpm import scanmind
from levi.gtpm.scanmind import (
    compose_program,
    evaluate,
    freeze_image,
    make_program,
    render_rung,
    run_scan_cycle,
)

_ALLOW_ALL = lambda intent: True  # noqa: E731
_NOOP = lambda intent: None  # noqa: E731


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _contact(signal, pred, value=None):
    contact = {"signal": signal, "pred": pred}
    if value is not None:
        contact["value"] = value
    return contact


def _rung(name, branches, coil_intent, mode="normal", safety=False,
          unlatch_target=None, args=None, risk=0):
    return {
        "name": name,
        "safety": safety,
        "branches": branches,
        "coil": {"intent": coil_intent, "args": args or {}, "risk": risk},
        "mode": mode,
        "unlatch_target": unlatch_target,
    }


def _safety_rung(name="interlock", signal="e_stop"):
    # Trips (true) exactly when e_stop is truthy.
    return _rung(name, [[_contact(signal, "is_true")]], "safety_ok", safety=True)


def _states_by_name(rung_states):
    return {entry["name"]: entry for entry in rung_states}


# ---------------------------------------------------------------------------
# T1 — determinism: fixed inputs -> identical outputs, 500 runs + subprocess
# ---------------------------------------------------------------------------

def test_t1_determinism_across_runs_and_processes(tmp_path):
    program = make_program([
        _safety_rung(),
        _rung("heat", [[_contact("temp", "lt", 70.0)]], "heater_on",
              args={"target": "$setpoint"}, risk=1),
        _rung("seal", [[_contact("consent", "is_true")]], "armed", mode="latch"),
        _rung("edge", [[_contact("pulse", "changed")]], "ping", mode="one_shot"),
    ])
    world = {"e_stop": False, "temp": 68.5, "setpoint": 72.0,
             "consent": True, "pulse": 1}
    image, _ = freeze_image(world)
    latch_bits = {"seal": True}
    prev_image = {"pulse": 0, "temp": 68.5}

    expected = evaluate(program, image, latch_bits, prev_image)
    for _ in range(500):
        assert evaluate(program, image, latch_bits, prev_image) == expected

    # Cross-process: different PYTHONHASHSEED proves no hash()-based ordering.
    payload = {"program": program, "image": image,
               "latch": latch_bits, "prev": prev_image}
    payload_path = tmp_path / "t1_payload.json"
    payload_path.write_text(json.dumps(payload))
    core_dir = str(Path(scanmind.__file__).resolve().parents[2])
    script = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from levi.gtpm.scanmind import evaluate\n"
        "payload = json.load(open(sys.argv[2]))\n"
        "rs, oi, lu = evaluate(payload['program'], payload['image'],\n"
        "                      payload['latch'], payload['prev'])\n"
        "print(json.dumps({'rung_states': rs, 'output_image': oi,\n"
        "                'latch_updates': lu}, sort_keys=True))\n"
    )
    env = dict(os.environ, PYTHONHASHSEED="987654321")
    proc = subprocess.run(
        [sys.executable, "-c", script, core_dir, str(payload_path)],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    other = json.loads(proc.stdout)
    assert other["rung_states"] == expected[0]
    assert other["output_image"] == expected[1]
    assert other["latch_updates"] == expected[2]


# ---------------------------------------------------------------------------
# T2 — frozen input: mutating the world after FREEZE changes nothing
# ---------------------------------------------------------------------------

def test_t2_frozen_input():
    program = make_program([
        _safety_rung(),
        _rung("act", [[_contact("go", "is_true")]], "do_it"),
    ])
    world = {"e_stop": False, "go": True}
    image, _ = freeze_image(world)

    before = evaluate(program, image, {}, None)

    # Mutate the live world after the freeze.
    world["go"] = False
    world["e_stop"] = True
    world["injected"] = "mid-cycle write"

    after = evaluate(program, image, {}, None)
    assert after == before

    # Proof the freeze mattered: the live world now evaluates differently.
    live_image, _ = freeze_image(world)
    assert evaluate(program, live_image, {}, None) != before


def test_freeze_image_hash_deterministic():
    image_a, hash_a = freeze_image({"b": 2, "a": [1, {"x": None}]})
    image_b, hash_b = freeze_image({"a": [1, {"x": None}], "b": 2})
    assert hash_a == hash_b
    assert image_a == image_b
    assert len(hash_a) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# T3 — rung-0 supremacy
# ---------------------------------------------------------------------------

def test_t3_rung0_supremacy():
    program = make_program([
        _safety_rung(),
        _rung("act", [[_contact("go", "is_true")]], "do_it"),
    ])
    world = {"e_stop": True, "go": True}  # interlock tripped, rung 1 also true
    calls = []
    receipt, _new_state = run_scan_cycle(
        world, program, gate=_ALLOW_ALL, executor=calls.append,
        state=None, scan_id="t3",
    )
    assert [f["type"] for f in receipt["faults"]] == ["INTERLOCK"]
    assert receipt["rung_states"][0]["state"] is True
    assert receipt["commits"] == []
    assert calls == []


def test_t3_make_program_rejects_missing_safety():
    with pytest.raises(ValueError):
        make_program([
            _rung("not_safety", [[_contact("go", "is_true")]], "do_it"),
        ])
    with pytest.raises(ValueError):
        make_program([
            {**_safety_rung(), "safety": False},
        ])


# ---------------------------------------------------------------------------
# T4 — order/conflict: later rung wins, override recorded
# ---------------------------------------------------------------------------

def test_t4_order_conflict_last_wins():
    program = make_program([
        _safety_rung(),
        _rung("slow_down", [[_contact("hot", "is_true")]], "pump",
              args={"speed": "$slow"}),
        _rung("speed_up", [[_contact("hot", "is_true")]], "pump",
              args={"speed": "$fast"}),
    ])
    world = {"e_stop": False, "hot": True, "slow": 1, "fast": 9}
    rung_states, output_image, _ = evaluate(program, world, {}, None)

    assert output_image["pump"]["args"]["speed"] == 9  # later rung wins
    by_name = _states_by_name(rung_states)
    assert by_name["slow_down"]["overridden_by"] == "speed_up"
    assert by_name["speed_up"]["overridden_by"] is None

    # Exactly one commit per coil per cycle (I4).
    calls = []
    receipt, _ = run_scan_cycle(
        world, program, gate=_ALLOW_ALL, executor=lambda i: calls.append(i),
        scan_id="t4",
    )
    assert receipt["commits"] == [{"intent": "pump", "ok": True}]
    assert calls[0]["args"]["speed"] == 9


# ---------------------------------------------------------------------------
# T5 — latch / unlatch timing across 3 cycles
# ---------------------------------------------------------------------------

def test_t5_latch_unlatch_timing():
    # Unlatch rung is placed BEFORE its target latch rung so its
    # same-cycle write is visible to the latch rung's evaluation.
    program = make_program([
        _safety_rung(),
        _rung("release", [[_contact("release_cmd", "is_true")]], "released",
              mode="unlatch", unlatch_target="pump_seal", risk=1),
        _rung("pump_seal", [[_contact("start_cmd", "is_true")]], "pump",
              mode="latch", args={"speed": "$speed_set"}, risk=2),
    ])
    state = None

    # Cycle k: latch rung true -> coil staged, bit sealed in.
    r0, state = run_scan_cycle(
        {"e_stop": False, "start_cmd": True, "release_cmd": False, "speed_set": 5},
        program, gate=_ALLOW_ALL, executor=_NOOP, state=state, scan_id="t5k0",
    )
    assert [c["intent"] for c in r0["commits"]] == ["pump"]
    assert state["latch_bits"] == {"pump_seal": True}

    # Cycle k+1: raw false, seal-in holds -> coil still staged.
    r1, state = run_scan_cycle(
        {"e_stop": False, "start_cmd": False, "release_cmd": False, "speed_set": 5},
        program, gate=_ALLOW_ALL, executor=_NOOP, state=state, scan_id="t5k1",
    )
    assert [c["intent"] for c in r1["commits"]] == ["pump"]
    assert _states_by_name(r1["rung_states"])["pump_seal"]["state"] is True

    # Cycle k+2: unlatch fires -> coil false in the same cycle.
    r2, state = run_scan_cycle(
        {"e_stop": False, "start_cmd": False, "release_cmd": True, "speed_set": 5},
        program, gate=_ALLOW_ALL, executor=_NOOP, state=state, scan_id="t5k2",
    )
    assert [c["intent"] for c in r2["commits"]] == ["released"]
    assert _states_by_name(r2["rung_states"])["pump_seal"]["state"] is False
    assert state["latch_bits"] == {"pump_seal": False}


# ---------------------------------------------------------------------------
# T6 — one-shot: rising edge true exactly one cycle
# ---------------------------------------------------------------------------

def test_t6_one_shot_rising_edge():
    program = make_program([
        _safety_rung(),
        _rung("edge", [[_contact("trig", "is_true")]], "ping", mode="one_shot"),
    ])
    state = None
    seen = []
    for trig in (False, True, True, False, True):
        receipt, state = run_scan_cycle(
            {"e_stop": False, "trig": trig},
            program, gate=_ALLOW_ALL, executor=_NOOP, state=state,
        )
        seen.append(_states_by_name(receipt["rung_states"])["edge"]["state"])
    assert seen == [False, True, False, False, True]


# ---------------------------------------------------------------------------
# T7 — watchdog: EXECUTE exceeding ops_budget -> OVERRUN + SAFE
# ---------------------------------------------------------------------------

def test_t7_watchdog_ops_budget():
    # 3000 contacts, all false (missing signals): no staged intents,
    # but the contact-evaluation count blows the ops budget deterministically.
    big_branch = [[_contact(f"s{i}", "is_true")] for i in range(3000)]
    program = make_program([
        _rung("interlock", big_branch, "safety_ok", safety=True),
        _rung("idle", [[_contact("never", "is_true")]], "noop"),
    ])
    receipt, _ = run_scan_cycle(
        {}, program, gate=_ALLOW_ALL, executor=_NOOP,
        ops_budget=100, scan_id="t7",
    )
    assert any(f["type"] == "OVERRUN" for f in receipt["faults"])
    assert receipt["watchdog_ok"] is False
    assert receipt["commits"] == []  # SAFE: nothing committed
    assert "INTERLOCK" not in [f["type"] for f in receipt["faults"]]


# ---------------------------------------------------------------------------
# T8 — replay: receipt + retained (image, program) re-derives rung states
# ---------------------------------------------------------------------------

def test_t8_replay_from_receipt():
    program = make_program([
        _safety_rung(),
        _rung("seal", [[_contact("go", "is_true")]], "do_it", mode="latch"),
    ])
    world = {"e_stop": False, "go": True}
    image, image_hash = freeze_image(world)
    state0 = {"latch_bits": {"seal": False},
              "prev_image": {"go": False}, "scan_count": 7}

    receipt, _ = run_scan_cycle(
        world, program, gate=_ALLOW_ALL, executor=_NOOP,
        state=state0, scan_id="t8",
    )
    assert receipt["image_hash"] == image_hash
    assert receipt["program_version"] == program["version"]

    replay_states, _oi, _lu = evaluate(
        program, image, state0["latch_bits"], state0["prev_image"])
    assert replay_states == receipt["rung_states"]


# ---------------------------------------------------------------------------
# T9 — gate denial halts the flush; no silent skip
# ---------------------------------------------------------------------------

def test_t9_gate_denial_halts_flush():
    program = make_program([
        _safety_rung(),
        _rung("first", [[_contact("go", "is_true")]], "alpha"),
        _rung("second", [[_contact("go", "is_true")]], "beta"),
        _rung("third", [[_contact("go", "is_true")]], "gamma"),
    ])
    calls = []

    def gate(intent):
        return intent["intent"] != "beta"  # deny the 2nd intent only

    receipt, _ = run_scan_cycle(
        {"e_stop": False, "go": True}, program,
        gate=gate, executor=calls.append, scan_id="t9",
    )
    assert [f["type"] for f in receipt["faults"]] == ["DENIED"]
    assert receipt["commits"] == [{"intent": "alpha", "ok": True}]
    # Halted, not skipped: gamma was never attempted.
    assert [c["intent"] for c in calls] == ["alpha"]


def test_executor_failure_records_failed():
    def boom(intent):
        raise RuntimeError("commit transport down")

    program = make_program([
        _safety_rung(),
        _rung("act", [[_contact("go", "is_true")]], "do_it"),
    ])
    receipt, _ = run_scan_cycle(
        {"e_stop": False, "go": True}, program,
        gate=_ALLOW_ALL, executor=boom, scan_id="t9b",
    )
    assert [f["type"] for f in receipt["faults"]] == ["FAILED"]
    assert receipt["commits"] == [{"intent": "do_it", "ok": False}]


# ---------------------------------------------------------------------------
# T10 — interop: receipt validates against the schema; no foreign mutations
# ---------------------------------------------------------------------------

RECEIPT_SCHEMA = {
    "kind": str,
    "scan_id": str,
    "t": (int, float),
    "image_hash": str,
    "program_version": int,
    "rung_states": list,
    "commits": list,
    "faults": list,
    "duration_ms": (int, float),
    "watchdog_ok": bool,
}

RUNG_STATE_SCHEMA = {
    "name": str,
    "state": bool,
    "mode": str,
    "overridden_by": (str, type(None)),
}


def test_t10_receipt_schema_and_no_foreign_mutations():
    program = make_program([
        _safety_rung(),
        _rung("act", [[_contact("go", "is_true")]], "do_it"),
    ])
    receipt, _ = run_scan_cycle(
        {"e_stop": False, "go": True}, program,
        gate=_ALLOW_ALL, executor=_NOOP, scan_id="t10",
    )
    assert set(receipt.keys()) == set(RECEIPT_SCHEMA.keys())
    for key, types in RECEIPT_SCHEMA.items():
        assert isinstance(receipt[key], types), f"receipt[{key!r}]"
    for entry in receipt["rung_states"]:
        assert set(entry.keys()) == set(RUNG_STATE_SCHEMA.keys())
        for key, types in RUNG_STATE_SCHEMA.items():
            assert isinstance(entry[key], types), f"rung_state[{key!r}]"
    for commit in receipt["commits"]:
        assert set(commit.keys()) == {"intent", "ok"}
    for fault in receipt["faults"]:
        assert set(fault.keys()) == {"type", "detail"}

    # Latch writes are conceptually growth-tagged: the receipt carries no
    # tool/policy/memory-mutation fields of its own — the scan-mind never
    # writes tools, policy, identity, or charter, only latch bits + receipt.
    assert not (set(receipt.keys()) & {"tools", "policy", "memory_write",
                                       "tool_calls", "identity", "charter"})


# ---------------------------------------------------------------------------
# Unit: predicate integration (changed / present) through evaluate
# ---------------------------------------------------------------------------

def test_predicates_changed_and_present_integration():
    program = make_program([
        _safety_rung(),
        _rung("edge_detect", [[_contact("level", "changed")]], "on_change"),
        _rung("exists", [[_contact("level", "present")]], "on_present"),
    ])
    image = {"e_stop": False, "level": 3}

    states, _oi, _lu = evaluate(program, image, {}, {"level": 2})
    by_name = _states_by_name(states)
    assert by_name["edge_detect"]["state"] is True
    assert by_name["exists"]["state"] is True

    states, _oi, _lu = evaluate(program, image, {}, {"level": 3})
    assert _states_by_name(states)["edge_detect"]["state"] is False

    states, _oi, _lu = evaluate(program, image, {}, None)
    assert _states_by_name(states)["edge_detect"]["state"] is False


# ---------------------------------------------------------------------------
# Unit: fail-closed $signal resolution
# ---------------------------------------------------------------------------

def test_signal_ref_missing_fail_closed():
    program = make_program([
        _safety_rung(),
        _rung("act", [[_contact("go", "is_true")]], "do_it",
              args={"speed": "$missing_signal"}),
    ])
    with pytest.raises(ValueError):
        evaluate(program, {"e_stop": False, "go": True}, {}, None)

    # ... and the scan wraps it as a typed EVAL fault, never a silent skip.
    receipt, _ = run_scan_cycle(
        {"e_stop": False, "go": True}, program,
        gate=_ALLOW_ALL, executor=_NOOP, scan_id="tfc",
    )
    assert [f["type"] for f in receipt["faults"]] == ["EVAL"]
    assert receipt["commits"] == []


# ---------------------------------------------------------------------------
# Unit: render_rung — readable card line, no ladder glyphs
# ---------------------------------------------------------------------------

def test_render_rung_readable_no_glyphs():
    rung = _rung("no_consequential_without_consent",
                 [[_contact("consent", "is_false")]],
                 "require_permission", mode="latch")
    line = render_rung(rung)
    assert line == ('rung "no_consequential_without_consent": '
                    '[consent is_false] → coil: require_permission (latch)')
    for glyph in ("XIC", "XIO", "OTE", "─", "│", "┤", "├", "┬", "┴", "┼"):
        assert glyph not in line


def test_render_rung_multi_branch():
    rung = _rung("mix", [[_contact("a", "is_true"), _contact("n", "gt", 3)],
                         [_contact("b", "present")]],
                 "do_mix")
    line = render_rung(rung)
    assert "[a is_true AND n gt 3] OR [b present]" in line
    assert "coil: do_mix (normal)" in line


# ---------------------------------------------------------------------------
# Unit: make_program version handling + compose_program (end-team hook)
# ---------------------------------------------------------------------------

def test_make_program_version_and_compose():
    base = make_program({"version": 4, "rungs": [_safety_rung()]})
    assert base["version"] == 4
    assert make_program([_safety_rung()])["version"] == 1

    extra = [_rung("extra", [[_contact("go", "is_true")]], "do_extra")]
    composed = compose_program(base, extra)
    assert composed["version"] == 5
    assert [r["name"] for r in composed["rungs"]] == ["interlock", "extra"]
    assert composed["rungs"][0]["safety"] is True  # rung-0 supremacy preserved

    # Re-validation: a bad extra rung fails closed.
    with pytest.raises(ValueError):
        compose_program(base, [_rung("interlock",
                                     [[_contact("go", "is_true")]], "dup")])

    # Appended rungs run after rung 0 in evaluation order.
    world = {"e_stop": False, "go": True}
    states, output, _ = evaluate(composed, world, {}, None)
    assert [s["name"] for s in states] == ["interlock", "extra"]
    assert output["do_extra"]["intent"] == "do_extra"


@pytest.mark.parametrize("bad_rungs", [
    [],  # no rungs at all
    [{"name": "x"}],  # rung 0 without safety
    [_safety_rung(), {"name": "interlock"}],  # duplicate rung name
    [_safety_rung(),
     _rung("weird", [[_contact("go", "is_true")]], "do_it", mode="turbo")],
    [_safety_rung(),
     _rung("un", [[_contact("go", "is_true")]], "do_it", mode="unlatch")],
    [_safety_rung(),
     _rung("risky", [[_contact("go", "is_true")]], "do_it", risk=5)],
    [_safety_rung(), "not-a-dict"],
])
def test_make_program_validation(bad_rungs):
    with pytest.raises(ValueError):
        make_program(bad_rungs)
