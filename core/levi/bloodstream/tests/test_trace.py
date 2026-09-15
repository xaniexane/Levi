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
    assert len(records) == 1
    record = records[0]
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
    assert len(records) == 1
    record = records[0]
    assert record["outcome"] == "failed"
    assert record["composted"] is not None
    assert record["composted"]["engine"] == "levi.lwp.model_engine.reim_forks"


def test_trace_writer_never_raises_on_bad_dir():
    writer = TraceWriter(base_dir="/proc/definitely-not-writable-xyz/traces")
    assert writer.write({"hello": "world"}) is None
