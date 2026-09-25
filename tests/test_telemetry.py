"""Guard tests for levi.telemetry — the four declared invariants:

L1. Telemetry NEVER breaks the loop: every public entry point is total.
L2. Spans are valid OTLP/HTTP JSON (envelope, id formats, string int64s).
L3. Zero third-party dependencies: stdlib only.
L4. No binaries ship in the package (OpenObserve binary lives outside the repo).

These tests are hermetic: they never need a running OpenObserve. The one
wire-format test spins up a stdlib stub HTTP server on localhost.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from levi.telemetry import (
    configure,
    flush,
    llm_span,
    new_span_id,
    new_trace_id,
    reset,
    span,
    start_span,
    stats,
    traced,
)
from levi.telemetry import emitter as _emitter

_spanmod = sys.modules["levi.telemetry.span"]  # the module, not the re-exported fn

TELEMETRY_DIR = Path(__file__).resolve().parent.parent / "core" / "levi" / "telemetry"


@pytest.fixture(autouse=True)
def _clean():
    reset()
    old = (_emitter._ENDPOINT, _emitter._USER, _emitter._PASSWORD, _emitter._ENABLED)
    yield
    configure(endpoint=old[0], user=old[1], password=old[2], enabled=old[3])
    reset()


# ---------------------------------------------------------------------------
# L2: id formats and OTLP JSON validity
# ---------------------------------------------------------------------------


def test_trace_and_span_id_formats():
    assert re.fullmatch(r"[0-9a-f]{32}", new_trace_id())
    assert re.fullmatch(r"[0-9a-f]{16}", new_span_id())
    # two ids are (overwhelmingly likely) unique
    assert new_trace_id() != new_trace_id()
    assert new_span_id() != new_span_id()


def test_child_shares_trace_id_and_links_parent():
    parent = start_span("parent")
    child = start_span("child", parent=parent)
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id
    assert child.span_id != parent.span_id


def test_payload_is_valid_otlp_json():
    with span("test.op", {"s": "v", "b": True, "i": 7, "f": 1.5, "lst": [1, 2]}) as sp:
        sp.add_event("fired", {"why": "test"})
    payload = _emitter.build_payload([sp])
    body = json.loads(payload.decode("utf-8"))
    rs = body["resourceSpans"][0]
    assert rs["resource"]["attributes"][0] == {
        "key": "service.name",
        "value": {"stringValue": _emitter._SERVICE},
    }
    otlp = rs["scopeSpans"][0]["spans"][0]
    assert re.fullmatch(r"[0-9a-f]{32}", otlp["traceId"])
    assert re.fullmatch(r"[0-9a-f]{16}", otlp["spanId"])
    assert otlp["name"] == "test.op"
    assert otlp["kind"] == 1
    # int64 nanos MUST be strings per the OTLP JSON mapping
    assert isinstance(otlp["startTimeUnixNano"], str)
    assert isinstance(otlp["endTimeUnixNano"], str)
    assert int(otlp["endTimeUnixNano"]) >= int(otlp["startTimeUnixNano"])
    attrs = {a["key"]: a["value"] for a in otlp["attributes"]}
    assert attrs["s"] == {"stringValue": "v"}
    assert attrs["b"] == {"boolValue": True}
    assert attrs["i"] == {"intValue": "7"}
    assert attrs["f"] == {
        "stringValue": "1.5"
    }  # floats ride as strings (see emitter note)
    assert attrs["lst"] == {"stringValue": "[1, 2]"}
    assert otlp["events"][0]["name"] == "fired"
    assert isinstance(otlp["events"][0]["timeUnixNano"], str)


def test_error_status_marks_span_error():
    sp = start_span("boom")
    with pytest.raises(RuntimeError):
        with sp:
            raise RuntimeError("kablam")
    otlp = json.loads(_emitter.build_payload([sp]).decode())["resourceSpans"][0][
        "scopeSpans"
    ][0]["spans"][0]
    assert otlp["status"] == {"code": 2}  # ERROR


def test_llm_span_carries_token_and_cost_attributes():
    with llm_span(
        "ministral-3",
        input_tokens=1200,
        output_tokens=300,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.002,
    ) as sp:
        pass
    attrs = sp.attributes
    assert attrs["gen_ai.request.model"] == "ministral-3"
    assert attrs["gen_ai.usage.input_tokens"] == 1200
    assert attrs["gen_ai.usage.output_tokens"] == 300
    # 1.2 * 0.001 + 0.3 * 0.002 = 0.0018
    assert abs(attrs["llm.cost_usd"] - 0.0018) < 1e-9


def test_llm_span_direct_cost():
    with llm_span("x", cost_usd=0.05) as sp:
        pass
    assert sp.attributes["llm.cost_usd"] == 0.05


# ---------------------------------------------------------------------------
# L1: telemetry never breaks the loop
# ---------------------------------------------------------------------------


def test_disabled_emitter_drops_with_counter_and_never_raises():
    configure(enabled=False)
    sp = start_span("dropped-op")
    sp.finish()  # must not raise
    assert flush(timeout=1.0) is True
    s = stats()
    assert s["dropped"] >= 1
    assert s["failed"] == 0


def test_dead_endpoint_degrades_to_failed_counter_never_raises():
    configure(endpoint="http://127.0.0.1:9/api/default/v1/traces", enabled=True)
    for _ in range(3):
        with span("dead-endpoint-op"):
            pass
    assert flush(timeout=10.0) is True  # returns, never raises
    s = stats()
    assert s["failed"] >= 3  # all three batches failed honestly
    assert s["emitted"] == 0


def test_queue_full_drops_with_counter():
    configure(enabled=True)
    # jam the queue shut by filling it directly
    jammed = 0
    try:
        while True:
            _emitter._QUEUE.put_nowait(object())
            jammed += 1
    except Exception:
        pass
    assert jammed > 0
    sp = start_span("overflow-op")
    assert sp.finish() is None  # no raise
    assert stats()["dropped"] >= 1
    # the background worker will eventually drain the junk; leave it


def test_start_span_never_raises_even_if_construction_fails(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("construction exploded")

    monkeypatch.setattr(_spanmod, "Span", _boom)
    sp = start_span("anything")
    sp.set_attribute("k", "v")
    sp.add_event("e")
    sp.finish()
    with sp:  # context manager form also total
        pass


def test_traced_decorator_passes_results_and_errors_through():
    @traced("test.decorated")
    def ok_fn(x):
        return x * 2

    @traced("test.decorated-fail")
    def fail_fn():
        raise ValueError("nope")

    assert ok_fn(21) == 42
    with pytest.raises(ValueError):
        fail_fn()


def test_traced_decorator_survives_total_telemetry_failure(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("telemetry is on fire")

    monkeypatch.setattr("levi.telemetry.hooks._span", _boom)

    @traced("test.decorated-down")
    def fn():
        return "still works"

    assert fn() == "still works"


def test_span_attribute_mutation_never_raises():
    sp = start_span("mutate")
    sp.set_attribute("k", object())  # exotic value: JSON-encoded, not raised
    sp.add_event("e", None)
    sp.record_error()
    sp.finish()
    sp.finish()  # double finish is a no-op, not an error


# ---------------------------------------------------------------------------
# Wire format against a real (stub) HTTP server
# ---------------------------------------------------------------------------


class _Capture(BaseHTTPRequestHandler):
    received = []
    auth = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _Capture.received.append(self.rfile.read(length))
        _Capture.auth.append(self.headers.get("Authorization"))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def test_wire_format_to_stub_server():
    _Capture.received.clear()
    _Capture.auth.clear()
    server = HTTPServer(("127.0.0.1", 0), _Capture)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        configure(
            endpoint=f"http://127.0.0.1:{port}/api/default/v1/traces",
            user="u",
            password="p",
            enabled=True,
        )
        with llm_span("stub-model", input_tokens=10, output_tokens=5, cost_usd=0.01):
            pass
        assert flush(timeout=10.0) is True
    finally:
        server.shutdown()
    assert len(_Capture.received) >= 1
    assert _Capture.auth[0].startswith("Basic ")
    body = json.loads(_Capture.received[0].decode("utf-8"))
    spans = body["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert spans[0]["name"] == "llm.call"
    attr_keys = {a["key"] for a in spans[0]["attributes"]}
    assert {
        "gen_ai.request.model",
        "gen_ai.usage.input_tokens",
        "llm.cost_usd",
    } <= attr_keys


# ---------------------------------------------------------------------------
# L3: stdlib only. L4: no binaries in the package.
# ---------------------------------------------------------------------------


def test_package_is_stdlib_only():
    stdlib = set(sys.stdlib_module_names)
    stdlib |= {"__future__"}
    for path in sorted(TELEMETRY_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in stdlib, f"{path.name}: non-stdlib import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    assert top in stdlib, (
                        f"{path.name}: non-stdlib import {node.module}"
                    )


def test_package_contains_no_binaries():
    files = [p for p in TELEMETRY_DIR.iterdir() if p.is_file()]
    assert files, "telemetry package is empty"
    for p in files:
        assert p.suffix == ".py", f"non-Python file in telemetry package: {p.name}"


def test_hooks_do_not_change_wrapped_signatures():
    from levi.growth import cycle as _cycle
    from levi.revival.omega import loop as _loop

    assert _cycle.run_cycle.__name__ == "run_cycle"
    assert _loop.run_symbiotic_loop.__name__ == "run_symbiotic_loop"
