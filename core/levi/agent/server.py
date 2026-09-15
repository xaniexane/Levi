"""LEVI as the cloud: the same agent binary served over HTTP, multi-user.

Stdlib ``http.server`` only (``ThreadingHTTPServer``). This module is
the network skin over :func:`levi.agent.loop.run_subtask` — it adds
nothing to the agent's capabilities, only an authenticated HTTP front
door, now for many users.

Security posture (binding):

* ``serve()`` refuses to start without ``LEVI_AGENT_TOKEN`` set to a
  non-empty value — it exits 2 rather than ever serving unauthenticated.
* Two credential kinds, enforced **server-side by key type** (a client
  can never claim a wider profile):
  - the owner master token (``LEVI_AGENT_TOKEN``): full tool registry,
    no rate limit. It also manages API keys via ``levi cloud keys``.
  - per-user API keys (``levi_sk_…``, see :mod:`levi.cloud.apikeys`):
    the **cloud-safe tool profile** only
    (:mod:`levi.cloud.profile` — read-only tools, no shell, no file
    writes, no owner memory/schedule, no arbitrary network egress),
    plus a per-key token-bucket rate limit (default 60 req/min,
    ``LEVI_CLOUD_RATE_PER_MIN``).
* Bearer comparison is constant-time (:func:`hmac.compare_digest`);
  wrong or missing → ``401`` JSON ``{"error": "unauthorized"}``.
* Raw keys are never logged and never stored — only the short public
  prefix (``levi_sk_…``) appears in logs and usage metering.
* Chat sessions for API keys are namespaced per key
  (``cloud_<prefix-tail>_<session_id>``) so users cannot read each
  other's sessions by guessing a session id.
* Every ``/v1/`` call is metered to append-only JSONL
  (:mod:`levi.cloud.metering`): timestamp, key name/prefix, endpoint,
  steps, outcome. No billing — single-machine server by design.
* Default bind is ``127.0.0.1``. Remote exposure belongs behind a TLS
  reverse proxy (nginx/Caddy with a client secret), never by binding
  this server to ``0.0.0.0`` directly on the open internet.

``/healthz`` is open (load-balancers, uptime checks): ``{"status",
"ok", "service", "levi-agent", "version"}``. Everything under ``/v1/``
requires auth.

``/v1/agent/run`` runs non-interactively: ``confirm=None``, so a gated
tool with ``consent=false`` is honestly denied (the run ends with
``ok=false`` and explains the gate tripped). With ``consent=true`` the
caller accepts responsibility for the gated actions in that run — the
gate is bypassed by the caller's explicit choice, logged in the request,
not by a server-side switch. (API keys have no gated tools at all:
the cloud-safe profile excludes every ``requires_confirmation`` tool.)
"""

from __future__ import annotations

import hmac
import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

import levi

MAX_BODY_BYTES = 1_048_576  # 1 MiB
MAX_STEPS_CAP = 50


def _get_token() -> str:
    return os.environ.get("LEVI_AGENT_TOKEN", "")


def _constant_time_bearer(auth_header: str, token: str) -> bool:
    """True iff ``Authorization`` is exactly ``Bearer <token>``."""
    if not auth_header or not token:
        return False
    scheme, _, value = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(value.encode("utf-8"), token.encode("utf-8"))


def _presented_bearer(auth_header: str) -> str | None:
    """The raw bearer value, or None when the header is malformed."""
    if not auth_header:
        return None
    scheme, _, value = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value


class _AgentHandler(BaseHTTPRequestHandler):
    # Bound by serve(): the owner token, a RateLimiter, and an optional
    # factory for the owner's default registry.
    token: str = ""
    owner_token: str = ""
    rate_limiter: Any = None
    make_registry: Callable[[], Any] | None = None

    # Per-request auth, set by _require_auth().
    _auth_kind: str = ""  # "owner" | "key"
    _auth_record: dict | None = None

    # -- plumbing ---------------------------------------------------------
    def log_message(self, fmt, *args):  # keep the stdlib access log
        sys.stderr.write("levi-agent: " + fmt % args + "\n")

    def _send_json(
        self, status: int, payload: dict, extra_headers: dict | None = None
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # -- auth -------------------------------------------------------------
    def _auth(self) -> tuple[str, dict | None] | None:
        """Resolve the bearer credential.

        Returns ``("owner", None)``, ``("key", record)``, or None.
        The owner token is checked first; API keys never collide with it
        (different scheme prefix), and only active (non-revoked) keys
        verify.
        """
        header = self.headers.get("Authorization", "")
        if _constant_time_bearer(header, self.owner_token or self.token):
            return ("owner", None)
        raw = _presented_bearer(header)
        if raw is None:
            return None
        from levi.cloud.apikeys import find_key

        record = find_key(raw)
        if record is None:
            return None
        return ("key", record)

    def _key_label(self) -> str:
        """Log-safe identity: 'owner' or the key's public prefix."""
        if self._auth_kind == "owner":
            return "owner"
        rec = self._auth_record or {}
        return "key %s" % (rec.get("prefix", "?"),)

    def _require_auth(self) -> bool:
        resolved = self._auth()
        if resolved is None:
            self._send_json(401, {"error": "unauthorized"})
            return False
        kind, record = resolved
        self._auth_kind = kind
        self._auth_record = record
        if kind == "key":
            limiter = self.rate_limiter
            if limiter is None:
                from levi.cloud.ratelimit import RateLimiter

                limiter = RateLimiter()
                self.rate_limiter = limiter
            allowed, retry_after = limiter.check(record.get("prefix", "?"))
            if not allowed:
                self._send_json(
                    429,
                    {"error": "rate limit exceeded"},
                    extra_headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
                )
                return False
        return True

    def _meter(
        self, endpoint: str, steps: int = 0, ok: bool = True, error: str | None = None
    ) -> None:
        """Usage metering. Never raises; never sees a raw key."""
        try:
            from levi.cloud.metering import log_usage

            if self._auth_kind == "owner":
                name, prefix = "owner", "owner"
            else:
                rec = self._auth_record or {}
                name, prefix = rec.get("name", "?"), rec.get("prefix", "?")
            log_usage(
                key_name=name,
                key_prefix=prefix,
                endpoint=endpoint,
                steps=steps,
                ok=ok,
                error=error,
            )
        except Exception:
            pass

    def _registry_for_caller(self) -> Any:
        """Full registry for the owner, cloud-safe profile for API keys."""
        if self._auth_kind == "owner":
            from levi.agent.tools import build_default_registry

            factory = self.make_registry or build_default_registry
            return factory()
        from levi.cloud.profile import build_cloud_registry

        return build_cloud_registry()

    # -- routing ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path == "/healthz":
            self._send_json(
                200,
                {"status": "ok", "service": "levi-agent", "version": levi.__version__},
            )
            return
        if self.path == "/v1/tools":
            if not self._require_auth():
                return
            registry = self._registry_for_caller()
            self._meter("/v1/tools")
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
        if self.path == "/v1/learning/packs/latest":
            if not self._require_auth():
                return
            from levi.growth import sync as _sync

            try:
                payload = _sync.latest_pack_payload()
            except Exception:  # never leak internals
                self._meter(
                    "/v1/learning/packs/latest", ok=False, error="pack read failed"
                )
                self._send_json(500, {"error": "could not read learning packs"})
                return
            self._meter("/v1/learning/packs/latest")
            self._send_json(200, payload)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path not in ("/v1/agent/run", "/v1/agent/chat"):
            self._send_json(404, {"error": "not found"})
            return
        if not self._require_auth():
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            # Drain the body before answering so the client reliably
            # receives the 413 instead of a connection reset mid-upload.
            remaining = length
            try:
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except Exception:
                pass
            self._meter(self.path, ok=False, error="request body too large")
            self._send_json(413, {"error": "request body too large (>1MB)"})
            return
        raw = self.rfile.read(length) if length > 0 else b""

        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._meter(self.path, ok=False, error="invalid JSON body")
            self._send_json(400, {"error": "invalid JSON body"})
            return
        if not isinstance(body, dict):
            self._meter(self.path, ok=False, error="body must be a JSON object")
            self._send_json(400, {"error": "body must be a JSON object"})
            return

        if self.path == "/v1/agent/chat":
            self._handle_chat(body)
            return
        self._handle_run(body)

    def _run_kwargs(self, body: dict) -> tuple[dict | None, dict | None]:
        """Validate the shared run/chat fields. Returns (kwargs, error)."""
        provider = body.get("provider")
        if provider is not None and not isinstance(provider, str):
            return None, {"error": "'provider' must be a string when given"}
        try:
            max_steps = int(body.get("max_steps", 10))
        except (TypeError, ValueError):
            return None, {"error": "'max_steps' must be an integer"}
        max_steps = max(1, min(max_steps, MAX_STEPS_CAP))
        consent = body.get("consent", False)
        if not isinstance(consent, bool):
            return None, {"error": "'consent' must be a boolean"}
        return {"provider": provider, "max_steps": max_steps, "consent": consent}, None

    def _session_id_for_caller(self, session_id: str) -> str:
        """Namespace chat sessions per API key so users cannot read each
        other's sessions. The owner keeps un-namespaced sessions."""
        if self._auth_kind == "owner":
            return session_id
        rec = self._auth_record or {}
        tail = (
            "".join(c for c in str(rec.get("prefix", "")) if c.isalnum())[-8:] or "key"
        )
        namespaced = "cloud_%s_%s" % (tail, session_id)
        max_plain = 64 - (len(namespaced) - len(session_id))
        if len(namespaced) > 64:
            raise ValueError(
                "session_id too long for cloud sessions "
                "(max %d chars after per-key namespacing)" % (max_plain,)
            )
        return namespaced

    def _handle_run(self, body: dict) -> None:
        task = body.get("task")
        if not isinstance(task, str) or not task.strip():
            self._meter("/v1/agent/run", ok=False, error="task required")
            self._send_json(
                400, {"error": "'task' is required and must be a non-empty string"}
            )
            return
        kwargs, err = self._run_kwargs(body)
        if err:
            self._meter("/v1/agent/run", ok=False, error=err["error"])
            self._send_json(400, err)
            return

        from levi.agent.loop import run_subtask

        # Non-interactive by construction: confirm=None. Gated tools with
        # consent=false are honestly denied; with consent=true the caller
        # has accepted responsibility (see module docstring). API keys
        # run the cloud-safe profile: the dangerous tools are not in the
        # registry at all, so no consent flag can reach them.
        transcript = run_subtask(
            task,
            provider=kwargs["provider"],
            registry=self._registry_for_caller(),
            consent=kwargs["consent"],
            confirm=None,
            max_steps=kwargs["max_steps"],
        )
        result = transcript.to_dict()
        self._meter(
            "/v1/agent/run",
            steps=len(result.get("steps", [])),
            ok=result.get("ok", False),
            error=result.get("error"),
        )
        self._send_json(200, {"transcript": result})

    def _handle_chat(self, body: dict) -> None:
        """One chat turn inside a persistent server-side session."""
        from levi.agent.chat import ConversationManager, sanitize_session_name

        session_id = body.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            self._meter("/v1/agent/chat", ok=False, error="session_id required")
            self._send_json(
                400,
                {"error": "'session_id' is required and must be a non-empty string"},
            )
            return
        try:
            session_id = sanitize_session_name(session_id)
            session_id = self._session_id_for_caller(session_id)
        except ValueError as exc:
            self._meter("/v1/agent/chat", ok=False, error=str(exc))
            self._send_json(400, {"error": str(exc)})
            return
        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            self._meter("/v1/agent/chat", ok=False, error="message required")
            self._send_json(
                400, {"error": "'message' is required and must be a non-empty string"}
            )
            return
        kwargs, err = self._run_kwargs(body)
        if err:
            self._meter("/v1/agent/chat", ok=False, error=err["error"])
            self._send_json(400, err)
            return

        # Non-interactive by construction: confirm=None (same discipline
        # as /v1/agent/run).
        manager = ConversationManager(
            session_id,
            provider=kwargs["provider"],
            registry=self._registry_for_caller(),
            max_steps=kwargs["max_steps"],
            consent=kwargs["consent"],
            confirm=None,
        )
        try:
            result = manager.turn(message)
        except ValueError as exc:
            self._meter("/v1/agent/chat", ok=False, error=str(exc))
            self._send_json(400, {"error": str(exc)})
            return
        transcript = result.transcript.to_dict()
        self._meter(
            "/v1/agent/chat",
            steps=len(transcript.get("steps", [])),
            ok=transcript.get("ok", False),
            error=transcript.get("error"),
        )
        self._send_json(
            200,
            {
                "session_id": session_id,
                "transcript": transcript,
                "context_pct": result.context_pct,
                "compressed": result.compressed,
            },
        )


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

    from levi.cloud.ratelimit import RateLimiter

    _AgentHandler.token = token
    _AgentHandler.owner_token = token
    _AgentHandler.rate_limiter = RateLimiter()
    server = ThreadingHTTPServer((host, int(port)), _AgentHandler)
    # Startup line: names the bind address, never the token.
    print(
        f"levi-agent: serving on http://{host}:{port} "
        "(owner token or API key required for /v1/*; /healthz open)",
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
