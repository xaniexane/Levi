"""Port-watch connector — the ear on local service ports.

Polls a TCP ``host:port`` with a bare connect (no bytes are ever sent —
the handshake alone is the signal) and emits one event per status
change::

    {"kind": "baseline" | "status_changed",
     "status": "up" | "down", "prev_status": <status | None>,
     "host": "<host>", "port": <int>, "latency_ms": <float | None>}

The caller holds ``state`` (the last status) between polls; the
connector itself keeps nothing.

Laws
----
- observe-only: a TCP connect is opened and immediately closed; the
  poll never sends, writes, or mutates anything on either end
- honest baseline: the first poll (no state) emits a ``baseline`` event
  naming the current status — a watched port is never silently assumed
- edge-only: a steady status emits nothing; a flap — including
  recovery back to ``up`` — emits exactly one event

Deny-closed paths
-----------------
- ``host`` must be a non-empty string; ``port`` an int in 1..65535
- ``0 < timeout_sec <= 30`` — a poll must never hang the caller
- a ``state`` carrying an unknown status is refused, never guessed
"""

from __future__ import annotations

import socket
import time
from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_STATUSES = ("up", "down")

_DEFAULT_TIMEOUT_SEC = 2.0
_MAX_TIMEOUT_SEC = 30.0


def _guarded_host(host: Any) -> str:
    if not isinstance(host, str) or not host.strip():
        raise ConnectorError("portwatch: 'host' must be a non-empty string")
    return host.strip()


def _guarded_port(port: Any) -> int:
    if isinstance(port, bool) or not isinstance(port, int):
        raise ConnectorError("portwatch: 'port' must be an integer")
    if not 1 <= port <= 65535:
        raise ConnectorError(f"portwatch: 'port' must be 1..65535, got {port}")
    return port


def _guarded_timeout(timeout_sec: Any) -> float:
    if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float)):
        raise ConnectorError("portwatch: 'timeout_sec' must be a number")
    timeout = float(timeout_sec)
    if not 0.0 < timeout <= _MAX_TIMEOUT_SEC:
        raise ConnectorError(
            f"portwatch: need 0 < timeout_sec <= 30, got timeout_sec={timeout_sec!r}"
        )
    return timeout


def _probe(host: str, port: int, timeout: float) -> Tuple[str, float | None]:
    """Bare-connect probe. Returns (status, latency_ms). Never sends bytes."""
    start = time.monotonic()
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        pass
    finally:
        sock.close()
    latency_ms = (time.monotonic() - start) * 1000.0
    return "up", round(latency_ms, 2)


def poll_portwatch(
    host: Any = None,
    port: Any = None,
    timeout_sec: Any = _DEFAULT_TIMEOUT_SEC,
    state: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll contract: ``(events, new_state)``."""
    if host is None:
        raise ConnectorError("portwatch: 'host' is required")
    if port is None:
        raise ConnectorError("portwatch: 'port' is required")
    host = _guarded_host(host)
    port = _guarded_port(port)
    timeout = _guarded_timeout(timeout_sec)

    if state is None:
        state = {}
    if not isinstance(state, dict):
        raise ConnectorError("portwatch: 'state' must be a dict")
    prev_status = state.get("status")
    if prev_status is not None and prev_status not in _STATUSES:
        raise ConnectorError(f"portwatch: unknown status in state: {prev_status!r}")

    try:
        status, latency_ms = _probe(host, port, timeout)
    except (OSError, socket.timeout):
        status, latency_ms = "down", None

    reading = {
        "status": status,
        "prev_status": prev_status,
        "host": host,
        "port": port,
        "latency_ms": latency_ms,
    }

    if prev_status is None:
        events = [dict(reading, kind="baseline")]
    elif prev_status == status:
        events = []
    else:
        events = [dict(reading, kind="status_changed")]

    return events, {"status": status}


registry.register(
    Connector(
        id="portwatch",
        name="Port Watch",
        description="Polls a TCP host:port with a bare connect and emits "
        "one event per status change (up/down), including recovery. "
        "Observe-only: no bytes are ever sent. The caller holds the "
        "last status as state.",
        version="1.0.0",
        inputs=("host", "port", "timeout_sec", "state"),
        risk="info",
        poll=poll_portwatch,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-portwatch",
            provides=("connector.portwatch.poll",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
