"""Void-mind API — the real backend behind the void UI (``web/index.html``).

Stdlib only. Mounted by ``levi.serve.server`` under ``/api/*``; the static
half keeps serving the UI itself.

LAWS
----
- L1: every chat reply comes from the real local Orchestrator
  (``levi.orchestration.loop.Orchestrator``) — never canned, never faked.
- L2: offline is detected, never simulated — these endpoints only answer
  when the daemon itself is running. The UI treats any fetch failure as
  the daemon being down and refuses to fake chat.
- L3: the register list comes live from
  ``levi.persona.levi.all_variants()`` — never invented, never hard-coded.
- L4: growth state comes live from ``levi.growth.cycle.status()`` —
  never hard-coded, never cycled by a demo button.
- L5: tape ticks are a real sha256 hash chain, one chain per session.
- L6: tok/s is *measured* (tokens / wall-clock seconds of the real turn),
  never estimated for display.

Honest limits (stated, not hidden):
- The native loop is non-streaming by construction, so "streaming" here
  means: the core shows its generating shimmer while the daemon works,
  then the real reply lands with the real measured tok/s. No fake
  token-by-token typing is ever rendered.
- One Orchestrator is cached per session id; turns are serialized behind
  a lock (the loop is not built for concurrent turns).
- Hash chains live in daemon memory; a daemon restart starts new chains.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

MAX_MESSAGE_CHARS = 8000
MAX_BODY_BYTES = 65536


def _tick(prev: str, session_id: str, role: str, text: str) -> str:
    """Next link in the session hash chain (L5)."""
    payload = "\x00".join((prev, session_id, role, text))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class VoidState:
    """Daemon-lifetime state: hash chains + cached orchestrators."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chains: dict[str, dict[str, Any]] = {}
        self._orchestrators: dict[str, Any] = {}

    # -- hash chains ----------------------------------------------------

    def chain_tick(self, session_id: str, role: str, text: str) -> dict[str, Any]:
        with self._lock:
            chain = self._chains.get(session_id)
            if chain is None:
                chain = {"prev": "genesis", "n": 0}
                self._chains[session_id] = chain
            tick = _tick(chain["prev"], session_id, role, text)
            chain["prev"] = tick
            chain["n"] += 1
            return {"tick": tick, "n": chain["n"]}

    def fork_chain(self, session_id: str, from_tick: str) -> dict[str, Any]:
        """Start a new chain seeded from an existing tick (branch/clone)."""
        with self._lock:
            self._chains[session_id] = {"prev": from_tick, "n": 0}
            return {"tick": from_tick, "n": 0}

    def chain_head(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            chain = self._chains.get(session_id, {"prev": "genesis", "n": 0})
            return {"tick": chain["prev"], "n": chain["n"]}

    # -- orchestrators ---------------------------------------------------

    def orchestrator(self, session_id: str, register: str | None):
        """One cached Orchestrator per session; register switch is real."""
        from levi.orchestration.loop import Orchestrator

        with self._lock:
            orch = self._orchestrators.get(session_id)
            if orch is None:
                orch = Orchestrator(soft_power=False)
                self._orchestrators[session_id] = orch
        if register:
            orch.set_persona(register)
        return orch


_STATE = VoidState()
_TURN_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Pure data builders (importable by the proof gate without a socket)
# ---------------------------------------------------------------------------


def build_health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "void-mind",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def build_registers() -> dict[str, Any]:
    """L3: live from levi.persona.levi.all_variants()."""
    from levi.persona.levi import all_variants

    regs = [
        {
            "id": v.id,
            "name": v.name,
            "voice": v.voice,
            "tagline": v.tagline,
        }
        for v in all_variants()
    ]
    return {"registers": regs, "count": len(regs)}


def build_growth() -> dict[str, Any]:
    """L4: live from levi.growth.cycle.status()."""
    from levi.growth import cycle

    s = cycle.status()
    nxt = s.get("next_stage") or {}
    return {
        "stage": s.get("stage"),
        "stage_blurb": s.get("stage_blurb"),
        "learnings": s.get("learnings_consolidated"),
        "journal_records": s.get("journal_records"),
        "cycles_completed": s.get("cycles_completed"),
        "next_stage": {
            "name": nxt.get("name"),
            "requirements": nxt.get("requirements"),
        },
    }


def build_journal(limit: int = 20) -> dict[str, Any]:
    from levi.growth import journal as _journal

    limit = max(1, min(int(limit), 100))
    entries = _journal.read_entries(limit=limit)
    return {"entries": entries, "count": len(entries)}


def build_model() -> dict[str, Any]:
    """Honest model status: what actually answers chat turns."""
    import os

    weights = os.path.join(
        os.path.dirname(__file__), "..", "brain", "weights", "tiny-gpt.pt"
    )
    weights = os.path.realpath(weights)
    present = os.path.isfile(weights)
    return {
        "resolved": "levi-native · rules planner (offline companion path)",
        "note": (
            "The agentic loop runs locally with the rules planner. "
            + (
                "Native brain weights are present on this machine."
                if present
                else "No native brain weights on this machine yet."
            )
        ),
        "weights_present": present,
        "streaming": False,
        "streaming_note": (
            "The native loop is non-streaming by construction; the UI shows "
            "a generating state while the daemon works and reports measured "
            "tok/s per turn. Token-by-token streaming is never faked."
        ),
    }


def run_chat(
    session_id: str, message: str, register: str | None, state: VoidState | None = None
) -> dict[str, Any]:
    """L1+L6: one real turn through the local Orchestrator, measured."""
    from levi.agent.chat import estimate_tokens, sanitize_session_name

    st = state or _STATE
    session_id = sanitize_session_name(session_id)
    message = (message or "").strip()
    if not message:
        raise ValueError("'message' is required and must be non-empty")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError("'message' exceeds %d chars" % MAX_MESSAGE_CHARS)

    if register:
        valid = {v["id"] for v in build_registers()["registers"]}
        if register not in valid:
            raise ValueError("unknown register %r" % register)

    user_tick = st.chain_tick(session_id, "user", message)
    orch = st.orchestrator(session_id, register)
    t0 = time.monotonic()
    with _TURN_LOCK:
        result = orch.turn(message)
    elapsed = max(time.monotonic() - t0, 1e-6)
    reply = result.response or ""
    tokens = estimate_tokens(reply)
    bot_tick = st.chain_tick(session_id, "levi", reply)
    return {
        "session_id": session_id,
        "reply": reply,
        "persona_id": result.persona_id,
        "tokens": tokens,
        "elapsed_s": round(elapsed, 3),
        "tok_per_s": round(tokens / elapsed, 1),
        "user_tick": user_tick,
        "tick": bot_tick,
    }


def pin_note(
    session_id: str, text: str, state: VoidState | None = None
) -> dict[str, Any]:
    """A real note, appended to the persistent session log."""
    from levi.agent.chat import ChatSession, sanitize_session_name

    st = state or _STATE
    session_id = sanitize_session_name(session_id)
    text = (text or "").strip()
    if not text:
        raise ValueError("'text' is required and must be non-empty")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValueError("'text' exceeds %d chars" % MAX_MESSAGE_CHARS)
    ChatSession(session_id).append_note(text)
    tick = st.chain_tick(session_id, "note", text)
    return {"ok": True, "session_id": session_id, "tick": tick}


def session_log(session_id: str, limit: int = 50) -> dict[str, Any]:
    from levi.agent.chat import ChatSession, sanitize_session_name

    session_id = sanitize_session_name(session_id)
    sess = ChatSession(session_id)
    recs = sess.records[-max(1, min(int(limit), 200)) :]
    return {
        "session_id": session_id,
        "records": recs,
        "chain": _STATE.chain_head(session_id),
    }


# ---------------------------------------------------------------------------
# HTTP dispatch — called by the serve handler for /api/* paths
# ---------------------------------------------------------------------------


def _send_json(handler, status: int, obj: dict[str, Any]) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler) -> dict[str, Any] | None:
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        return None
    if length <= 0 or length > MAX_BODY_BYTES:
        return None
    try:
        raw = handler.rfile.read(length)
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def handle_api(handler) -> bool:
    """Route /api/* requests. Returns True when the path was handled."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(handler.path)
    path = parsed.path
    if not path.startswith("/api/"):
        return False
    method = handler.command

    try:
        if method == "GET" and path == "/api/health":
            _send_json(handler, 200, build_health())
        elif method == "GET" and path == "/api/registers":
            _send_json(handler, 200, build_registers())
        elif method == "GET" and path == "/api/growth":
            _send_json(handler, 200, build_growth())
        elif method == "GET" and path == "/api/model":
            _send_json(handler, 200, build_model())
        elif method == "GET" and path == "/api/journal":
            qs = parse_qs(parsed.query)
            limit = qs.get("limit", ["20"])[0]
            _send_json(handler, 200, build_journal(limit))
        elif method == "GET" and path.startswith("/api/session/"):
            sid = path[len("/api/session/") :]
            _send_json(handler, 200, session_log(sid))
        elif method == "POST" and path == "/api/chat":
            body = _read_json(handler)
            if body is None:
                _send_json(handler, 400, {"error": "invalid JSON body"})
            else:
                _send_json(
                    handler,
                    200,
                    run_chat(
                        body.get("session_id") or "void-01",
                        body.get("message") or "",
                        body.get("register"),
                    ),
                )
        elif method == "POST" and path == "/api/note":
            body = _read_json(handler)
            if body is None:
                _send_json(handler, 400, {"error": "invalid JSON body"})
            else:
                _send_json(
                    handler,
                    200,
                    pin_note(
                        body.get("session_id") or "void-01", body.get("text") or ""
                    ),
                )
        elif method == "POST" and path == "/api/fork":
            body = _read_json(handler)
            if body is None:
                _send_json(handler, 400, {"error": "invalid JSON body"})
            else:
                from levi.agent.chat import sanitize_session_name

                new_id = sanitize_session_name(body.get("new_session_id") or "")
                from_tick = str(body.get("from_tick") or "genesis")
                _send_json(handler, 200, _STATE.fork_chain(new_id, from_tick))
        else:
            _send_json(handler, 404, {"error": "unknown api route"})
    except ValueError as exc:
        _send_json(handler, 400, {"error": str(exc)})
    except Exception as exc:  # honest 500, never a fake reply
        _send_json(handler, 500, {"error": "daemon error: %s" % exc})
    return True
