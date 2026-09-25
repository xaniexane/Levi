"""Trace contract: one JSONL record per turn, all fields, decision path."""

import json

from levi.bloodstream.stages import RouteKind
from levi.bloodstream.trace import TRACE_FIELDS, TraceWriter
from levi.bloodstream.turn import run_turn


def test_trace_written_with_all_required_fields(ctx, data_dir):
    result = run_turn("what is recursion in one sentence", ctx)
    assert result.ok
    traces_dir = data_dir / "traces"
    files = list(traces_dir.glob("*.jsonl"))
    assert len(files) == 1
    records = [
        json.loads(line) for line in files[0].read_text().splitlines() if line.strip()
    ]
    # 2 records: the turn trace + the levi.turn.completed bus event
    # (axis 2: every turn publishes to the event bus, which appends to the
    # trace while the turn's trace scope is active).
    assert len(records) == 2
    bus_events = [r for r in records if r.get("event") == "bus.publish"]
    turn_traces = [r for r in records if "event" not in r]
    assert len(bus_events) == 1 and len(turn_traces) == 1
    bus_event = bus_events[0]
    assert bus_event["topic"] == "levi.turn.completed"
    assert bus_event["payload"]["outcome"] == "replied"
    record = turn_traces[0]
    assert bus_event["trace_id"] == record["trace_id"]
    for field in TRACE_FIELDS:
        assert field in record, f"missing trace field: {field}"
    assert record["trace_id"] == result.trace_id
    assert record["route"] == RouteKind.MODEL.value
    assert record["policy_receipt_id"] == result.policy_receipt_id
    assert record["risk_level"] == 1
    assert isinstance(record["provider"], str) and record["provider"]
    assert isinstance(record["skills_invoked"], list)
    stages = record["stages"]
    assert [s["stage"] for s in stages] == result.stage_names()
    assert all(s["decision"] for s in stages)


def test_failed_turn_still_writes_trace_with_compost(ctx_for, monkeypatch, data_dir):
    # Force a mid-turn failure in the route executor.
    def boom(text, data_dir):
        raise RuntimeError("factory exploded")

    monkeypatch.setattr("levi.bloodstream.turn._execute_factory", boom)
    result = run_turn("build me a todo app", ctx_for(confirm=lambda p: True))
    assert result.ok is False
    assert result.route is RouteKind.FAILED
    assert result.error and "RuntimeError" in result.error

    records = []
    for f in data_dir.joinpath("traces").glob("*.jsonl"):
        records += [
            json.loads(line) for line in f.read_text().splitlines() if line.strip()
        ]
    assert len(records) == 2
    bus_events = [r for r in records if r.get("event") == "bus.publish"]
    turn_traces = [r for r in records if "event" not in r]
    assert len(bus_events) == 1 and len(turn_traces) == 1
    assert bus_events[0]["topic"] == "levi.turn.completed"
    assert bus_events[0]["payload"]["outcome"] == "failed"
    record = turn_traces[0]
    assert bus_events[0]["trace_id"] == record["trace_id"]
    assert record["outcome"] == "failed"
    assert record["composted"] is not None
    assert record["composted"]["engine"] == "levi.lwp.model_engine.reim_forks"


def test_trace_writer_never_raises_on_bad_dir():
    writer = TraceWriter(base_dir="/proc/definitely-not-writable-xyz/traces")
    assert writer.write({"hello": "world"}) is None
