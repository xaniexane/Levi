"""Hermetic tests for the bloodstream event bus (levi.bloodstream.bus).

Everything runs under a tmp HOME; nothing touches the real ~/.levi.
"""

import json

import pytest

from levi.bloodstream.bus import (
    publish,
    reset_bus,
    subscribe,
    topics,
    trace_scope,
    unsubscribe,
)
from levi.bloodstream.stages import TurnContext
from levi.bloodstream.turn import reset_session_state, run_turn


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    monkeypatch.delenv("LEVI_MODEL_DIR", raising=False)
    reset_bus()
    reset_session_state()
    yield
    reset_bus()
    reset_session_state()


def _ctx(tmp_path):
    data_dir = tmp_path / "levi-home"
    data_dir.mkdir(exist_ok=True)
    return TurnContext(session_id="test", data_dir=data_dir, max_model_steps=1)


# -- pub/sub ------------------------------------------------------------


def test_pub_sub_roundtrip():
    received = []
    token = subscribe("levi.growth.learning", lambda t, p: received.append((t, p)))
    assert isinstance(token, str) and token
    publish("levi.growth.learning", {"kind": "fact", "text": "x"})
    assert len(received) == 1
    topic, payload = received[0]
    assert topic == "levi.growth.learning"
    assert payload == {"kind": "fact", "text": "x"}


def test_unsubscribe_stops_delivery():
    received = []
    token = subscribe("levi.hunt.finding", lambda t, p: received.append(p))
    assert unsubscribe(token) is True
    assert unsubscribe(token) is False  # already gone
    publish("levi.hunt.finding", {"title": "y"})
    assert received == []


def test_topics_lists_published_and_subscribed():
    subscribe("levi.archive.ingested", lambda t, p: None)
    publish("levi.turn.completed", {"ok": True})
    got = topics()
    assert "levi.archive.ingested" in got
    assert "levi.turn.completed" in got
    assert got == sorted(got)


def test_handler_errors_are_isolated():
    def bad(topic, payload):
        raise RuntimeError("boom")

    good = []
    subscribe("levi.turn.completed", bad)
    subscribe("levi.turn.completed", lambda t, p: good.append(p))
    publish("levi.turn.completed", {"ok": True})  # must not raise
    assert good == [{"ok": True}]


# -- validation ----------------------------------------------------------


@pytest.mark.parametrize(
    "topic",
    ["", "nope", "LEVI.turn.completed", "levi.", "levi.turn completed", 42, None],
)
def test_bad_topic_names_rejected(topic):
    with pytest.raises(ValueError, match="invalid topic"):
        publish(topic, {"a": 1})


def test_non_json_serializable_payload_rejected():
    with pytest.raises(TypeError, match="JSON-serializable"):
        publish("levi.turn.completed", {"cb": lambda: 1})
    with pytest.raises(TypeError, match="must be a dict"):
        publish("levi.turn.completed", ["not", "a", "dict"])


def test_non_callable_handler_rejected():
    with pytest.raises(TypeError, match="callable"):
        subscribe("levi.turn.completed", "not-a-handler")


# -- trace binding --------------------------------------------------------


def test_publish_appends_to_trace_when_scope_active(tmp_path):
    home = tmp_path / "home"
    base = home / ".levi" / "traces"
    with trace_scope("trace-abc", base):
        publish("levi.hunt.finding", {"title": "dead software"})
    files = list(base.glob("*.jsonl"))
    assert len(files) == 1
    records = [json.loads(l) for l in files[0].read_text().splitlines()]
    assert len(records) == 1
    rec = records[0]
    assert rec["trace_id"] == "trace-abc"
    assert rec["event"] == "bus.publish"
    assert rec["topic"] == "levi.hunt.finding"
    assert rec["payload"] == {"title": "dead software"}
    assert rec["handler_errors"] == []


def test_publish_without_trace_scope_writes_nothing(tmp_path):
    publish("levi.turn.completed", {"ok": True})
    assert not (tmp_path / "home" / ".levi" / "traces").exists()


def test_handler_errors_recorded_in_trace(tmp_path):
    home = tmp_path / "home"
    base = home / ".levi" / "traces"

    def bad(topic, payload):
        raise RuntimeError("subscriber exploded")

    subscribe("levi.turn.completed", bad)
    with trace_scope("trace-xyz", base):
        publish("levi.turn.completed", {"ok": True})
    records = [
        json.loads(l) for l in next(base.glob("*.jsonl")).read_text().splitlines()
    ]
    assert records[0]["handler_errors"] == ["RuntimeError: subscriber exploded"]


# -- turn pipeline emission ------------------------------------------------


def test_run_turn_emits_turn_completed(tmp_path):
    received = []
    subscribe("levi.turn.completed", lambda t, p: received.append((t, p)))
    result = run_turn("what is recursion in one sentence", _ctx(tmp_path))
    assert result.ok
    assert len(received) == 1
    topic, payload = received[0]
    assert topic == "levi.turn.completed"
    assert payload["trace_id"] == result.trace_id
    assert payload["outcome"] == "replied"
    assert payload["route"] == "model"
    assert payload["risk_level"] == 1
    assert payload["session_id"] == "test"
    assert isinstance(payload["stage_names"], list) and payload["stage_names"]


def test_turn_completed_event_lands_in_turn_trace(tmp_path):
    data_dir = tmp_path / "levi-home"
    data_dir.mkdir(exist_ok=True)
    ctx = TurnContext(session_id="test", data_dir=data_dir, max_model_steps=1)
    result = run_turn("what is recursion in one sentence", ctx)
    assert result.ok
    traces = list((data_dir / "traces").glob("*.jsonl"))
    assert len(traces) == 1
    records = [json.loads(l) for l in traces[0].read_text().splitlines()]
    bus_events = [r for r in records if r.get("event") == "bus.publish"]
    assert len(bus_events) == 1
    assert bus_events[0]["topic"] == "levi.turn.completed"
    assert bus_events[0]["trace_id"] == result.trace_id
