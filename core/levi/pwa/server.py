"""LEVI's PWA chat organ — the Xeno rebirth, done right.

The old "LEVI Ultimate Xeno" single-file lineage is composted. Its good
ideas — an installable chat PWA, a tone picker, media commands — are
reincarnated here as a proper LEVI organ: a stdlib-only HTTP server that
serves a PWA frontend and routes chat through the *existing* agentic
loop (:mod:`levi.agent.chat` / :mod:`levi.agent.loop`). This module adds
no agent capabilities; it is a network skin plus a UI.

Endpoints (all JSON unless noted):

* ``GET /`` — the PWA shell (``index.html``); static assets under their
  real paths (``/app.js``, ``/styles.css``, ``/manifest.json``,
  ``/sw.js``, ``/icon.svg``).
* ``GET /api/health`` — ``{"status": "ok", "service": "levi-pwa"}``.
* ``GET /api/registers`` — LEVI's real registers (the 14 KAI-9000
  variants): ``[{"id", "name", "tagline", "voice"}]``. No joke modes.
* ``GET /api/models`` — the LEVI-first model family with live
  downloaded/runner status, plus the currently resolved default.
* ``POST /api/chat`` — ``{"session", "message", "register",
  "provider", "max_steps", "consent"}`` → runs one agentic-loop turn
  through :class:`levi.agent.chat.ConversationManager` and returns
  ``{"reply", "provider", "ok", "steps", "context_pct", "compressed",
  "session"}``. Sessions persist in ``~/.levi/agent/sessions/`` exactly
  like ``levi agent chat`` — the PWA and the CLI share sessions.
* ``POST /api/chat/stream`` — same body, Server-Sent Events. Emits
  ``event: status`` liveness notes while the turn runs, then
  ``event: done`` with the same payload as ``/api/chat`` (or
  ``event: error``). The loop does not stream tokens, so this is honest
  liveness, not fake token streaming.
* ``POST /api/image`` — ``{"prompt", "width", "height"}`` → LEVI's
  existing media pipeline (:mod:`levi.media.pollinations`).
  Cloud-backed (Pollinations); needs network.

Security posture (binding):

* Single-user local server. Default bind is ``127.0.0.1``.
* Optional bearer token: when ``LEVI_PWA_TOKEN`` is set and non-empty,
  every ``/api/*`` route requires
  ``Authorization: Bearer <token>`` (constant-time compare). Static
  files stay open (they carry no data).
* Binding a non-loopback host without ``LEVI_PWA_TOKEN`` prints a loud
  warning. Public exposure belongs behind a TLS reverse proxy, never
  this server directly on the open internet.
* ``confirm=None`` semantics like the cloud agent server: with
  ``consent=false`` (the default) a gated tool is honestly denied and
  the turn explains the gate tripped. The PWA sends ``consent:false``;
  a real approval UI is enterprise Phase 2 work.

Stdlib only: ``http.server.ThreadingHTTPServer``.
"""

from __future__ import annotations

import hmac
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import levi

STATIC_DIR = Path(__file__).resolve().parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}
# manifest.json must be served as a manifest for installability checks.
_SPECIAL_TYPES = {
    "/manifest.json": "application/manifest+json",
}

_MAX_BODY = 256 * 1024  # 256 KiB — chat messages are small


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class _PWAHandler(BaseHTTPRequestHandler):
    # Set by serve(): static_dir, provider_factory, token, default_register
    static_dir: Path = STATIC_DIR
    provider_factory: Callable[[], Any] | None = None
    token: str = ""
    default_register: str | None = None

    server_version = "LeviPWA/" + getattr(levi, "__version__", "0")

    # -- helpers ------------------------------------------------------

    def log_message(self, fmt, *args):  # keep logs quiet but present
        pass

    def _send(
        self, code: int, body: bytes, ctype: str, extra: dict | None = None
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, code: int, payload: Any) -> None:
        self._send(code, _json_bytes(payload), "application/json")

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > _MAX_BODY:
            return None
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _authorized(self) -> bool:
        """Bearer check on /api/* when LEVI_PWA_TOKEN is configured."""
        if not self.token:
            return True
        auth = self.headers.get("Authorization") or ""
        scheme, _, value = auth.partition(" ")
        if scheme.lower() != "bearer":
            return False
        return hmac.compare_digest(value.strip(), self.token)

    # -- routing ------------------------------------------------------

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            self._route_api_get(path)
            return
        self._serve_static(path)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        if path == "/api/chat":
            self._handle_chat(stream=False)
        elif path == "/api/chat/stream":
            self._handle_chat(stream=True)
        elif path == "/api/image":
            self._handle_image()
        else:
            self._send_json(404, {"error": "not found"})

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    # -- static --------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        # Traversal guard: resolve and stay inside static_dir.
        target = (self.static_dir / rel).resolve()
        try:
            target.relative_to(self.static_dir.resolve())
        except ValueError:
            self._send_json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_json(404, {"error": "not found"})
            return
        ctype = _SPECIAL_TYPES.get(
            "/" + rel,
            _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream"),
        )
        try:
            body = target.read_bytes()
        except OSError:
            self._send_json(500, {"error": "read failed"})
            return
        # The service worker must always revalidate, or updates never land.
        extra = {"Cache-Control": "no-cache"} if target.name == "sw.js" else None
        self._send(200, body, ctype, extra)

    # -- api: get ------------------------------------------------------

    def _route_api_get(self, path: str) -> None:
        if path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "levi-pwa",
                    "version": getattr(levi, "__version__", "0"),
                },
            )
        elif path == "/api/registers":
            self._send_json(200, {"registers": _list_registers()})
        elif path == "/api/models":
            self._send_json(200, _model_status())
        else:
            self._send_json(404, {"error": "not found"})

    # -- api: chat -----------------------------------------------------

    def _provider(self, name: str | None):
        from levi.agent.providers import select_provider

        if self.provider_factory is not None:
            return self.provider_factory()
        return select_provider(name or None)

    def _manager(self, body: dict):
        from levi.agent.chat import ConversationManager, sanitize_session_name
        from levi.persona.kai9000 import get as _get, system_for

        session = sanitize_session_name(str(body.get("session") or "default"))
        register_id = (
            body.get("register") or self.default_register or ""
        ).strip() or None
        system_prompt = None
        if register_id:
            if _get(register_id) is None:
                raise ValueError("unknown register %r" % register_id)
            system_prompt = system_for(register_id)
        provider = self._provider(str(body.get("provider") or "").strip() or None)
        max_steps = body.get("max_steps", 10)
        try:
            max_steps = max(1, int(max_steps))
        except (TypeError, ValueError):
            max_steps = 10
        consent = bool(body.get("consent", False))
        return ConversationManager(
            session,
            provider=provider,
            max_steps=max_steps,
            consent=consent,
            confirm=None,  # non-interactive: gated tools honestly denied
            system_prompt=system_prompt,
        ), session

    def _turn_payload(self, mgr, message: str, session: str, consent: bool) -> dict:
        result = mgr.turn(message, consent=consent, confirm=None)
        t = result.transcript
        return {
            "reply": t.final or "",
            "provider": mgr.provider_name,
            "ok": bool(t.ok),
            "steps": len(t.steps),
            "context_pct": round(result.context_pct, 3),
            "compressed": bool(result.compressed),
            "session": session,
        }

    def _handle_chat(self, stream: bool) -> None:
        body = self._read_json()
        if body is None:
            self._send_json(400, {"error": "expected a JSON object body"})
            return
        message = (body.get("message") or "").strip()
        if not message:
            self._send_json(400, {"error": "message is required"})
            return
        try:
            mgr, session = self._manager(body)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        consent = bool(body.get("consent", False))
        if not stream:
            try:
                payload = self._turn_payload(mgr, message, session, consent)
            except Exception as exc:
                self._send_json(500, {"error": "%s: %s" % (type(exc).__name__, exc)})
                return
            self._send_json(200, payload)
            return
        self._handle_chat_stream(mgr, message, session, consent)

    def _handle_chat_stream(
        self, mgr, message: str, session: str, consent: bool
    ) -> None:
        """SSE: liveness events while the turn runs, then done/error.

        The agentic loop does not stream tokens, so these events are
        honest progress markers, not token streams.
        """
        out: queue.Queue = queue.Queue()

        def _run():
            try:
                payload = self._turn_payload(mgr, message, session, consent)
                out.put(("done", payload))
            except Exception as exc:  # never leave the stream hanging
                out.put(("error", {"error": "%s: %s" % (type(exc).__name__, exc)}))

        threading.Thread(target=_run, daemon=True).start()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def _emit(event: str, data: Any) -> bool:
            try:
                chunk = "event: %s\ndata: %s\n\n" % (
                    event,
                    json.dumps(data, ensure_ascii=False),
                )
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError):
                return False

        if not _emit("status", {"state": "thinking", "session": session}):
            return
        while True:
            try:
                event, data = out.get(timeout=15)
            except queue.Empty:
                if not _emit(
                    "status",
                    {"state": "working", "session": session, "ts": time.time()},
                ):
                    return
                continue
            _emit(event, data)
            return

    # -- api: image ----------------------------------------------------

    def _handle_image(self) -> None:
        from levi.media.pollinations import generate

        body = self._read_json()
        if body is None:
            self._send_json(400, {"error": "expected a JSON object body"})
            return
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            self._send_json(400, {"error": "prompt is required"})
            return
        try:
            width = max(256, min(2048, int(body.get("width", 1024))))
            height = max(256, min(2048, int(body.get("height", 1024))))
        except (TypeError, ValueError):
            width, height = 1024, 1024
        try:
            img = generate(prompt, width=width, height=height)
        except Exception as exc:
            # Cloud-backed generation; report failure honestly.
            self._send_json(
                502,
                {
                    "error": "image generation failed: %s: %s"
                    % (type(exc).__name__, exc)
                },
            )
            return
        self._send_json(
            200,
            {
                "prompt": img.prompt,
                "url": img.url,
                "path": img.path,
                "seed": img.seed,
                "model": img.model,
            },
        )


# ---------------------------------------------------------------------------
# Introspection helpers (also used by the CLI/tests)
# ---------------------------------------------------------------------------


def _list_registers() -> list[dict]:
    from levi.persona.kai9000 import all_variants

    return [
        {"id": v.id, "name": v.name, "tagline": v.tagline, "voice": v.voice}
        for v in all_variants()
    ]


def _model_status() -> dict:
    from levi.agent import model_family

    try:
        resolved = model_family.resolve_family()
    except Exception:
        resolved = None
    return {
        "family": model_family.entries(),
        "resolved": resolved,
        "note": (
            "LEVI-first: native brain and remixes head the list; "
            "other providers are selectable sources."
        ),
    }


# ---------------------------------------------------------------------------
# serve()
# ---------------------------------------------------------------------------


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    provider_factory: Callable[[], Any] | None = None,
    default_register: str | None = None,
    token: str | None = None,
) -> ThreadingHTTPServer:
    """Start the PWA server. Returns the server (caller serves/poll it).

    ``provider_factory`` lets tests inject a stub provider; production
    uses :func:`levi.agent.providers.select_provider`.
    """
    if token is None:
        token = os.environ.get("LEVI_PWA_TOKEN", "").strip()
    if host != "127.0.0.1" and host != "localhost" and not token:
        print(
            "WARNING: binding %s without LEVI_PWA_TOKEN — anyone on the "
            "network can chat with your LEVI. Set LEVI_PWA_TOKEN for LAN "
            "use; public exposure belongs behind a TLS reverse proxy." % host
        )
    handler = type(
        "_PWAHandler",
        (_PWAHandler,),
        {
            "provider_factory": staticmethod(provider_factory)
            if provider_factory
            else None,
            "token": token or "",
            "default_register": default_register,
        },
    )
    server = ThreadingHTTPServer((host, int(port)), handler)
    return server


def run(host: str = "127.0.0.1", port: int = 8000, **kwargs) -> None:
    """Start the PWA server and serve forever (Ctrl-C stops)."""
    server = serve(host, port, **kwargs)
    print(
        "LEVI PWA serving at http://%s:%d/  (Ctrl-C to stop)"
        % (host, server.server_address[1])
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
