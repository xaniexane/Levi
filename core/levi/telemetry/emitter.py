"""Fire-and-forget OTLP/HTTP JSON emission. The invariant: never raises.

A bounded in-memory queue feeds a single daemon background thread that
serializes finished spans into OTLP/HTTP JSON and POSTs them to the
configured endpoint. Every failure mode — queue full, network down,
bad endpoint, serializer bug — degrades to drop-with-counter. The
background thread must never take the loop down with it.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import threading
import time
import urllib.request

# ---------------------------------------------------------------------------
# Configuration (env-overridable; no secrets hardcoded)
# ---------------------------------------------------------------------------

_ENDPOINT = os.environ.get(
    "LEVI_OTLP_ENDPOINT", "http://localhost:5080/api/default/v1/traces"
)
_USER = os.environ.get("LEVI_OTLP_USER", "root@example.com")
_PASSWORD = os.environ.get("LEVI_OTLP_PASSWORD", "")
_SERVICE = os.environ.get("LEVI_TELEMETRY_SERVICE", "levi")
_ENABLED = os.environ.get("LEVI_TELEMETRY_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)
_MAX_QUEUE = 4096
_FLUSH_INTERVAL = 0.5
_BATCH_MAX = 200
_HTTP_TIMEOUT = 5.0


def configure(
    *,
    endpoint: str | None = None,
    user: str | None = None,
    password: str | None = None,
    service: str | None = None,
    enabled: bool | None = None,
) -> None:
    """Override emission settings at runtime (tests, alternate orgs)."""
    global _ENDPOINT, _USER, _PASSWORD, _SERVICE, _ENABLED
    if endpoint is not None:
        _ENDPOINT = endpoint
    if user is not None:
        _USER = user
    if password is not None:
        _PASSWORD = password
    if service is not None:
        _SERVICE = service
    if enabled is not None:
        _ENABLED = bool(enabled)


# ---------------------------------------------------------------------------
# Counters: the honest ledger of what telemetry did
# ---------------------------------------------------------------------------

_counters = {"emitted": 0, "dropped": 0, "failed": 0}
_counters_lock = threading.Lock()


def _bump(key: str, n: int = 1) -> None:
    try:
        with _counters_lock:
            _counters[key] = _counters.get(key, 0) + n
    except Exception:
        pass  # counters must never break anything either


def stats() -> dict:
    """Snapshot of emission counters. Never raises."""
    try:
        with _counters_lock:
            return dict(_counters)
    except Exception:
        return {"emitted": 0, "dropped": 0, "failed": 0}


def reset() -> None:
    """Test seam: drain the queue and zero the counters. Never raises."""
    try:
        while True:
            _QUEUE.get_nowait()
    except Exception:
        pass
    try:
        with _counters_lock:
            for k in _counters:
                _counters[k] = 0
    except Exception:
        pass


# ---------------------------------------------------------------------------
# OTLP/HTTP JSON serialization (valid per the OTLP JSON mapping)
# ---------------------------------------------------------------------------


def _encode_value(value) -> dict:
    """Encode one attribute value into OTLP AnyValue JSON."""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}  # int64 -> string per OTLP JSON
    if isinstance(value, float):
        # OpenObserve v1.0.2's OTLP/HTTP JSON parser rejects {"doubleValue": x}
        # (HTTP 400 "invalid type: map, expected f64"), so floats ride as
        # full-precision strings. The attribute KEY is unchanged, so a future
        # parser fix can restore {"doubleValue": value} without touching any
        # dashboards or queries built on the key name.
        return {"stringValue": repr(value)}
    if isinstance(value, str):
        return {"stringValue": value}
    if value is None:
        return {"stringValue": ""}
    # lists/dicts and anything exotic: JSON-encode into a string
    try:
        return {"stringValue": json.dumps(value, default=str)}
    except Exception:
        return {"stringValue": str(value)}


def _encode_attributes(attributes: dict | None) -> list:
    out = []
    try:
        for k, v in (attributes or {}).items():
            out.append({"key": str(k), "value": _encode_value(v)})
    except Exception:
        pass
    return out


def _span_to_json(span) -> dict:
    """Serialize one finished Span into an OTLP span JSON object."""
    try:
        start_ns = str(int(span.start_ns))
        end_ns = str(int(span.end_ns if span.end_ns else span.start_ns))
    except Exception:
        start_ns = end_ns = "0"
    data: dict = {
        "traceId": span.trace_id,
        "spanId": span.span_id,
        "name": str(span.name),
        "kind": 1,  # SPAN_KIND_INTERNAL
        "startTimeUnixNano": start_ns,
        "endTimeUnixNano": end_ns,
        "attributes": _encode_attributes(span.attributes),
        "status": {"code": 2 if span.error else 1},  # ERROR : OK
    }
    if getattr(span, "parent_span_id", None):
        data["parentSpanId"] = span.parent_span_id
    events = []
    try:
        for ev in span.events or []:
            events.append(
                {
                    "name": str(ev.get("name", "event")),
                    "timeUnixNano": str(int(ev.get("time_ns", 0))),
                    "attributes": _encode_attributes(ev.get("attributes")),
                }
            )
    except Exception:
        pass
    if events:
        data["events"] = events
    return data


def build_payload(spans: list) -> bytes:
    """Build the OTLP/HTTP JSON request body for a batch of spans."""
    scope_spans = {"scope": {"name": "levi.telemetry", "version": "0.1"}, "spans": []}
    for sp in spans:
        try:
            scope_spans["spans"].append(_span_to_json(sp))
        except Exception:
            _bump("dropped")
    body = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": _SERVICE}}
                    ]
                },
                "scopeSpans": [scope_spans],
            }
        ]
    }
    return json.dumps(body).encode("utf-8")


# ---------------------------------------------------------------------------
# Background delivery: bounded queue + daemon thread
# ---------------------------------------------------------------------------

_QUEUE: "queue.Queue" = queue.Queue(maxsize=_MAX_QUEUE)


def enqueue(span) -> bool:
    """Hand a finished span to the background sender. Never blocks, never
    raises. Returns False when the span was dropped."""
    if not _ENABLED:
        _bump("dropped")
        return False
    try:
        _QUEUE.put_nowait(span)
        return True
    except Exception:
        _bump("dropped")  # queue full or broken: drop, count, move on
        return False


def _post(payload: bytes) -> None:
    """One HTTP POST to the OTLP endpoint. Raises on failure (caught by caller)."""
    auth = base64.b64encode(f"{_USER}:{_PASSWORD}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        status = getattr(resp, "status", 200)
    if status >= 400:
        raise RuntimeError(f"OTLP endpoint returned HTTP {status}")


def _drain() -> None:
    """Send everything currently queued, in batches. Never raises."""
    while True:
        batch = []
        try:
            while len(batch) < _BATCH_MAX:
                batch.append(_QUEUE.get_nowait())
        except queue.Empty:
            pass
        except Exception:
            pass
        if not batch:
            return
        try:
            _post(build_payload(batch))
            _bump("emitted", len(batch))
        except Exception:
            _bump("failed", len(batch))  # drop the batch, count it, move on


def _worker() -> None:
    """Background thread body. Dies only when the interpreter exits."""
    while True:
        try:
            time.sleep(_FLUSH_INTERVAL)
            _drain()
        except Exception:
            # the worker itself must never die loudly
            try:
                time.sleep(_FLUSH_INTERVAL)
            except Exception:
                return


_worker_thread = threading.Thread(target=_worker, name="levi-telemetry", daemon=True)
_worker_thread.start()


def flush(timeout: float = 5.0) -> bool:
    """Best-effort synchronous flush of the queue. Never raises.

    Returns True when the queue drained within the timeout.
    """
    try:
        deadline = time.time() + max(0.0, timeout)
        _drain()
        while time.time() < deadline:
            try:
                if _QUEUE.empty():
                    return True
            except Exception:
                return True
            _drain()
            time.sleep(0.05)
        try:
            return _QUEUE.empty()
        except Exception:
            return True
    except Exception:
        return False
