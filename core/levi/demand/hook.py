"""DemandPulse webhook receiver — local authenticated ingress (greatness build).

Chauncey's order: webhooks. This is the local end of that: a tiny
stdlib-only HTTP listener that accepts signal events (e.g. from the
Termux on-device sensor via store-and-forward, or any local producer)
and feeds them into the existing watcher ingest path.

LAWS (law -> guard -> prove; Chauncey 2026-09-22):
  H1 LOCALHOST ONLY. The listener binds 127.0.0.1 and nothing else.
     Any other bind address is refused before a socket opens. This is a
     local ingress point, not a public endpoint — remote phones cannot
     POST here directly (honest limit; the Termux route uses
     store-and-forward + a trusted transport instead).
  H2 TOKEN AUTH. Every request carries ``Authorization: Bearer <token>``.
     The token comes from the DP_HOOK_TOKEN env var; the server refuses
     to start without it (fail closed). Comparison is constant-time.
  H3 BOUNDED + STRICT. Request bodies are capped (64KB); only
     POST /signal with a strict JSON schema is accepted. Anything else
     gets 4xx, never ingestion.
  H4 INGEST, DON'T INVENT. Accepted items flow through the watcher's
     own ``extract_needs`` heuristic and ``DemandPulse.scan_seed`` —
     HYPOTHESIS only, source labels preserved, seen-id dedupe honored.
     The receiver mints nothing on its own.
  H5 NO OUTBOUND FETCH. This module opens no outbound connections.
     It binds, listens, validates, and ingests. (Structural: there is a
     test that fails the build if an outbound fetch primitive appears.)

Sequential stdlib HTTPServer — one request at a time, no threads in
this module. Good enough for a local webhook; the tick budget, not the
listener, is the bottleneck.

Event schema (strict):
  POST /signal
  Authorization: Bearer <DP_HOOK_TOKEN>
  {
    "items": [
      {"id": "sms-123", "text": "...", "channel": "text", "ts": "..."},
      ...
    ]
  }
  - "channel" must be "text" or "notification" (defaults "notification").
  - "id" and "text" are required non-empty strings (<= 2000 chars).
  - "ts" is optional free text (passed through, never parsed for logic).

Receipts mirror the watcher poll receipts: {accepted, candidates,
signals, signal_ids, rejected}.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Laws as importable constants

LAWS = (
    "H1 localhost-only bind (127.0.0.1; any other addr refused)",
    "H2 token auth (DP_HOOK_TOKEN, constant-time compare)",
    "H3 bounded body + strict schema (64KB cap)",
    "H4 ingest via watcher path (HYPOTHESIS only)",
    "H5 no outbound fetch capability",
)

BIND_ADDR = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 65536  # 64KB
MAX_ITEMS_PER_EVENT = 100
CHANNELS = ("text", "notification")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_closed_token() -> str:
    """Read DP_HOOK_TOKEN; raise instead of starting unauthenticated (H2)."""
    import os

    token = os.environ.get("DP_HOOK_TOKEN", "")
    if not token:
        raise RuntimeError(
            "DP_HOOK_TOKEN is not set — the webhook receiver refuses to "
            "start without a token (H2, fail closed)."
        )
    return token


def check_bind_address(addr: str) -> None:
    """Guard H1: only the loopback address may be bound. Raises ValueError."""
    if addr != BIND_ADDR:
        raise ValueError(
            f"refusing to bind {addr!r}: the webhook receiver binds "
            f"{BIND_ADDR} only (H1)."
        )


def validate_event(payload: Any) -> List[Dict[str, Any]]:
    """Strict schema check (H3). Returns clean items or raises ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("event must be a JSON object")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("'items' must be a non-empty array")
    if len(items) > MAX_ITEMS_PER_EVENT:
        raise ValueError(
            f"'items' exceeds the per-event cap ({MAX_ITEMS_PER_EVENT})")
    clean = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"items[{i}] must be an object")
        iid = it.get("id")
        text = it.get("text")
        if not isinstance(iid, str) or not iid.strip():
            raise ValueError(f"items[{i}].id must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"items[{i}].text must be a non-empty string")
        channel = it.get("channel", "notification")
        if channel not in CHANNELS:
            raise ValueError(
                f"items[{i}].channel must be one of {CHANNELS}")
        ts = it.get("ts", "")
        if not isinstance(ts, str):
            raise ValueError(f"items[{i}].ts must be a string")
        clean.append({
            "id": iid.strip()[:256],
            "text": text.strip()[:2000],
            "channel": channel,
            "ts": ts.strip()[:64],
        })
    return clean


def ingest_items(dp, state, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Feed validated items through the watcher path (H4).

    Same rules as device ingest: seen-id dedupe per channel, the
    conservative ``extract_needs`` heuristic, ``scan_seed`` for the
    candidates (HYPOTHESIS, source = the item's channel).
    """
    from levi.demand.watcher import extract_needs

    receipt: Dict[str, Any] = {
        "at": _now_iso(), "accepted": len(items), "candidates": 0,
        "signals": 0, "signal_ids": [], "skipped_seen": 0,
    }
    for it in items:
        channel = it["channel"]
        if not state.mark_seen(channel, it["id"]):
            receipt["skipped_seen"] += 1
            continue
        for need in extract_needs(it["text"]):
            receipt["candidates"] += 1
            sig = dp.scan_seed(need, segment="general", source=channel)
            receipt["signals"] += 1
            if sig.id not in receipt["signal_ids"]:
                receipt["signal_ids"].append(sig.id)
    state.touch(channel)
    return receipt


class HookHandler(BaseHTTPRequestHandler):
    """Single endpoint: POST /signal. Everything else is 404/405."""

    server_version = "DemandPulseHook/1.0"

    def _send(self, code: int, obj: Dict[str, Any]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = self.server.hook_token  # type: ignore[attr-defined]
        got = self.headers.get("Authorization", "")
        if not got.startswith("Bearer "):
            return False
        return hmac.compare_digest(got[7:], expected)

    def _read_body(self) -> Optional[bytes]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        return self.rfile.read(length)

    def do_POST(self) -> None:  # noqa: N802 (http.server naming)
        if self.path != "/signal":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        raw = self._read_body()
        if raw is None:
            self._send(413, {"ok": False,
                             "error": "body missing or over 64KB cap"})
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, {"ok": False, "error": "malformed JSON"})
            return
        try:
            items = validate_event(payload)
        except ValueError as exc:
            self._send(422, {"ok": False, "error": str(exc)})
            return
        receipt = ingest_items(
            self.server.dp, self.server.watcher_state, items)  # type: ignore[attr-defined]
        self.server.watcher_state.save()  # type: ignore[attr-defined]
        self._send(200, {"ok": True, "receipt": receipt})

    def do_GET(self) -> None:  # noqa: N802
        self._send(405, {"ok": False, "error": "POST /signal only"})

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet
        pass


def make_server(port: int = DEFAULT_PORT, bind: str = BIND_ADDR,
                dp=None, state=None, token: Optional[str] = None) -> HTTPServer:
    """Build the listener. Refuses non-loopback bind (H1) and missing
    token (H2) before any socket opens."""
    check_bind_address(bind)
    token = token or _fail_closed_token()
    from levi.demand.pulse import DemandPulse
    from levi.demand.watcher import WatcherState

    server = HTTPServer((bind, port), HookHandler)
    server.hook_token = token  # type: ignore[attr-defined]
    server.dp = dp or DemandPulse()  # type: ignore[attr-defined]
    server.watcher_state = state or WatcherState.load()  # type: ignore[attr-defined]
    return server


def serve(port: int = DEFAULT_PORT, bind: str = BIND_ADDR,
          dp=None, state=None, token: Optional[str] = None) -> None:
    """Run the receiver until interrupted. Blocking."""
    server = make_server(port=port, bind=bind, dp=dp, state=state,
                         token=token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
