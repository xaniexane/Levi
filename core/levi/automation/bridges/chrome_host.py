#!/usr/bin/env python3
"""LEVI Chrome extension bridge — native-messaging host.

Reads Chrome's native-messaging stdio framing (4-byte little-endian
length prefix + UTF-8 JSON), executes a tiny deny-closed protocol, and
writes length-prefixed JSON responses back to stdout:

- ``{"type": "ping"}``                       -> ``{"ok": true, "type": "pong"}``
- ``{"type": "fire-workflow", "flow_id": ..., "trigger": {...},
    "payload": {...}}``                     -> builds a trigger event and
    calls ``flows.dispatch_trigger``; response carries the results.
- anything else / malformed frames           -> ``{"ok": false, "error": ...}``,
    never a crash, never silence.

The event the extension fires looks like::

    {"kind": "webhook", "source": "chrome-extension",
     "payload": {"flow_id": ..., "trigger": {...}, "payload": {...}}}

Injection law: the extension's payload is **data**, never instructions —
it is passed through as the event payload, never evaluated.

Run by Chrome as the native host ``com.levi.automation`` (see
``chrome_ext/INSTALL.md``); also importable for tests.
"""

from __future__ import annotations

import json
import struct
import sys
from typing import Any, BinaryIO, Dict, List, Optional

HOST_NAME = "com.levi.automation"

# Deny cap: Chrome's own native-messaging limit is 1 MiB; refuse more.
_MAX_FRAME_BYTES = 1024 * 1024

__all__ = [
    "HOST_NAME",
    "FrameError",
    "encode_message",
    "read_message",
    "handle_message",
    "main",
]


class FrameError(Exception):
    """A length-prefix or payload that cannot be decoded into a message."""


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def encode_message(obj: Dict[str, Any]) -> bytes:
    """Encode a message as Chrome's native-messaging frame."""
    if not isinstance(obj, dict):
        raise TypeError("encode_message: message must be a dict")
    payload = json.dumps(obj, ensure_ascii=True).encode("utf-8")
    if len(payload) > _MAX_FRAME_BYTES:
        raise ValueError("encode_message: payload exceeds 1 MiB")
    return struct.pack("<I", len(payload)) + payload


def _read_exact(stream: BinaryIO, n: int) -> bytes:
    chunks: List[bytes] = []
    remaining = n
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_message(stream: BinaryIO) -> Optional[Dict[str, Any]]:
    """Read one frame; ``None`` on a clean EOF. Raises :class:`FrameError`."""
    header = _read_exact(stream, 4)
    if not header:
        return None
    if len(header) < 4:
        raise FrameError("truncated length prefix")
    (length,) = struct.unpack("<I", header)
    if length > _MAX_FRAME_BYTES:
        raise FrameError(f"frame length {length} exceeds 1 MiB cap")
    payload = _read_exact(stream, length)
    if len(payload) < length:
        raise FrameError("truncated frame payload")
    try:
        obj = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameError(f"payload is not JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise FrameError("payload must be a JSON object")
    return obj


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def _dispatch(event: Dict[str, Any]) -> List[Any]:
    """Hand the event to the workflow engine. Never silently faked."""
    try:
        from ..flows import dispatch_trigger
    except ImportError as exc:
        raise RuntimeError("workflow engine dispatch not yet available") from exc
    return dispatch_trigger(event)


def handle_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one protocol message; always returns a response dict."""
    if not isinstance(msg, dict):
        return {"ok": False, "error": "message must be a JSON object"}
    mtype = msg.get("type")

    if mtype == "ping":
        return {"ok": True, "type": "pong"}

    if mtype == "fire-workflow":
        event = {
            "kind": "webhook",
            "source": "chrome-extension",
            "payload": {
                "flow_id": msg.get("flow_id"),
                "trigger": msg.get("trigger"),
                "payload": msg.get("payload")
                if isinstance(msg.get("payload"), dict)
                else {},
            },
        }
        try:
            results = _dispatch(event)
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # deny-closed: report, never crash
            return {
                "ok": False,
                "error": f"dispatch failed: {type(exc).__name__}: {exc}",
            }
        return {"ok": True, "type": "workflow-fired", "results": results}

    return {"ok": False, "error": f"unknown message type {mtype!r}"}


def _write(stream: BinaryIO, response: Dict[str, Any]) -> None:
    stream.write(encode_message(response))
    stream.flush()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Native-host entry point: read frames until EOF, answer each."""
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        try:
            msg = read_message(stdin)
        except FrameError as exc:
            _write(stdout, {"ok": False, "error": f"malformed frame: {exc}"})
            continue
        except OSError as exc:
            sys.stderr.write(f"[levi-chrome-host] stdin error: {exc}\n")
            return 1
        if msg is None:
            return 0
        try:
            response = handle_message(msg)
        except Exception as exc:  # last-ditch guard; never silent, never crash
            sys.stderr.write(f"[levi-chrome-host] internal: {exc!r}\n")
            response = {"ok": False, "error": f"internal error: {type(exc).__name__}"}
        _write(stdout, response)


if __name__ == "__main__":
    sys.exit(main())
