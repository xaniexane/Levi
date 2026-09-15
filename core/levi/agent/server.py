"""LEVI as the cloud: the same agent binary served over HTTP.

Stdlib ``http.server`` only (``ThreadingHTTPServer``). This module is
the network skin over :func:`levi.agent.loop.run_subtask` — it adds
nothing to the agent's capabilities, only a token-authenticated HTTP
front door.

Security posture (binding):

* ``serve()`` refuses to start without ``LEVI_AGENT_TOKEN`` set to a
  non-empty value — it exits 2 rather than ever serving unauthenticated.
* ``/healthz`` is open (load-balancers, uptime checks). Everything
  under ``/v1/`` requires ``Authorization: Bearer <token>`` compared
  with :func:`hmac.compare_digest`; wrong or missing → ``401`` JSON
  ``{"error": "unauthorized"}``.
* The token is never logged.
* Default bind is ``127.0.0.1``. Remote exposure belongs behind a TLS
  reverse proxy (nginx/Caddy with a client secret), never by binding
  this server to ``0.0.0.0`` directly on the open internet.

``/v1/agent/run`` runs non-interactively: ``confirm=None``, so a gated
tool with ``consent=false`` is honestly denied (the run ends with
``ok=false`` and explains the gate tripped). With ``consent=true`` the
caller accepts responsibility for the gated actions in that run — the
gate is bypassed by the caller's explicit choice, logged in the request,
not by a server-side switch.
"""

from __future__ import annotations

import hmac
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

MAX_BODY_BYTES = 1_048_576  # 1 MiB
MAX_STEPS_CAP = 50


def _get_token() -> str:
    import os

    return os.environ.get("LEVI_AGENT_TOKEN", "")


def _constant_time_bearer(auth_header: str, token: str) -> bool:
    """True iff ``Authorization`` is exactly ``Bearer <token>``."""
    if not auth_header or not token:
        return False
    scheme, _, value = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(value.encode("utf-8"), token.encode("utf-8"))


class _AgentHandler(BaseHTTPRequestHandler):
    # Bound by serve(): the token, and a factory for a default registry.
    token: str = ""
    make_registry: Callable[[], Any] | None = None

    # -- plumbing ---------------------------------------------------------
    def log_message(self, fmt, *args):  # keep the stdlib access log
        sys.stderr.write("levi-agent: " + fmt % args + "\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self) -> bool:
        if _constant_time_bearer(self.headers.get("Authorization", ""), self.token):
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    # -- routing ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok", "service": "levi-agent"})
            return
        if self.path == "/v1/tools":
            if not self._require_auth():
                return
            from levi.agent.tools import build_default_registry

            factory = self.make_registry or build_default_registry
            registry = factory()
            self._send_json(
                200,
                {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters,
                            "requires_confirmation": t.requires_confirmation,
                        }
                        for t in registry.list()
                    ]
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path != "/v1/agent/run":
            self._send_json(404, {"error": "not found"})
            return
        if not self._require_auth():
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "request body too large (>1MB)"})
            return
        raw = self.rfile.read(length) if length > 0 else b""

        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "body must be a JSON object"})
            return

        task = body.get("task")
        if not isinstance(task, str) or not task.strip():
            self._send_json(400, {"error": "'task' is required and must be a non-empty string"})
            return
        provider = body.get("provider")
        if provider is not None and not isinstance(provider, str):
            self._send_json(400, {"error": "'provider' must be a string when given"})
            return
        try:
            max_steps = int(body.get("max_steps", 10))
        except (TypeError, ValueError):
            self._send_json(400, {"error": "'max_steps' must be an integer"})
            return
        max_steps = max(1, min(max_steps, MAX_STEPS_CAP))
        consent = body.get("consent", False)
        if not isinstance(consent, bool):
            self._send_json(400, {"error": "'consent' must be a boolean"})
            return

        from levi.agent.loop import run_subtask

        # Non-interactive by construction: confirm=None. Gated tools with
        # consent=false are honestly denied; with consent=true the caller
        # has accepted responsibility (see module docstring).
        transcript = run_subtask(
            task,
            provider=provider,
            registry=None,
            consent=consent,
            confirm=None,
            max_steps=max_steps,
        )
        self._send_json(200, {"transcript": transcript.to_dict()})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the agent over HTTP. Requires ``LEVI_AGENT_TOKEN``.

    Refuses to serve without a token: prints a clear refusal to stderr
    and raises :class:`SystemExit` with code 2.
    """
    token = _get_token()
    if not token:
        print(
            "levi-agent: refusing to serve — LEVI_AGENT_TOKEN is not set. "
            "Set it to a long random secret before serving (the server never "
            "runs unauthenticated).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    _AgentHandler.token = token
    server = ThreadingHTTPServer((host, int(port)), _AgentHandler)
    # Startup line: names the bind address, never the token.
    print(
        f"levi-agent: serving on http://{host}:{port} "
        "(token auth required for /v1/*; /healthz open)",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    # `python -m levi.agent.server [--host H] [--port P]`
    import argparse

    ap = argparse.ArgumentParser(description="Serve the LEVI agent over HTTP")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ns = ap.parse_args()
    serve(host=ns.host, port=ns.port)
