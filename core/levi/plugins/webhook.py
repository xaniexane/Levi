"""Outbound webhook connector — one honest pipe to a user-owned URL.

Purpose: give LEVI a single, auditable way to notify an external
system the user owns (their own dashboard, a self-hosted inbox, a
serverless function) without building a bespoke connector per target.
The target URL lives in ``LEVI_WEBHOOK_URL`` and is treated as a
bearer secret: it is read from the environment, never logged, never
printed, never written to disk.

Honesty notes (blueprint §1.5, §3):

* ``post`` is a write operation, so ``requires_confirmation=True`` is
  forced at class-definition time — the confirmation gate cannot be
  bypassed by any caller.
* ``ok=True`` is returned only after the transport actually ran: a
  real stdlib-urllib POST when no transport is injected, or the
  injected transport in tests. Remote failures surface as
  ``api_error``; nothing is ever simulated.
* Payloads must be JSON objects (or JSON-serializable); anything else
  is refused with ``invalid_params`` before any network access.

Wire it up::

    export LEVI_WEBHOOK_URL="https://example.com/hook/abc123"
    levi plugin exec webhook post --param payload='{"hello": "world"}' --yes
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.parse import urlparse

from .registry import (
    Capability,
    Connector,
    ConnectorAPIError,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

#: Hard cap on the serialized payload body (1 MiB).
_MAX_BODY_BYTES = 1_048_576

#: Optional string metadata fields and their length caps.
_EVENT_MAX_CHARS = 128


def _validate_url(raw: str) -> str:
    """Accept only http/https absolute URLs; refuse anything else."""
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidParams(
            "LEVI_WEBHOOK_URL is blank — set it to the target "
            "https:// URL. Nothing was sent."
        )
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidParams(
            "LEVI_WEBHOOK_URL must be an absolute http(s) URL. Nothing was sent."
        )
    return raw.strip()


def _validate_payload(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = params.get("payload")
    if payload is None:
        raise InvalidParams("post needs a 'payload' object — nothing was sent.")
    try:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidParams(
            f"'payload' must be JSON-serializable ({type(exc).__name__}) "
            "— nothing was sent."
        ) from None
    if len(body) > _MAX_BODY_BYTES:
        raise InvalidParams(
            f"payload is {len(body)} bytes; the limit is {_MAX_BODY_BYTES} "
            "— nothing was sent."
        )

    event = params.get("event")
    if event is not None:
        if not isinstance(event, str) or not event.strip():
            raise InvalidParams("'event' must be a non-empty string.")
        if len(event) > _EVENT_MAX_CHARS:
            raise InvalidParams(
                f"'event' is {len(event)} chars; the limit is {_EVENT_MAX_CHARS}."
            )

    raw_headers = params.get("headers") or {}
    if not isinstance(raw_headers, dict):
        raise InvalidParams("'headers' must be an object of string pairs.")
    headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise InvalidParams("'headers' must be string-to-string pairs.")
        name = key.strip()
        if name.lower() in ("authorization", "proxy-authorization", "cookie"):
            raise InvalidParams(f"header {name!r} is not allowed on webhook posts.")
        headers[name] = value

    envelope: dict[str, Any] = {"payload": json.loads(body.decode("utf-8"))}
    if event is not None:
        envelope["event"] = event.strip()
    envelope_body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    return envelope_body, headers


def _urllib_post(url: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    """Default transport: one real POST over stdlib urllib.

    Returns the delivery record. Raises ConnectorAPIError (message never
    includes the URL — it may be a bearer secret) on any failure.
    """
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            try:
                snippet = response.read(4096).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 — read failure is non-fatal
                snippet = ""
    except Exception as exc:  # noqa: BLE001 — any transport failure
        raise ConnectorAPIError(
            f"webhook POST failed ({type(exc).__name__}); "
            "check LEVI_WEBHOOK_URL and network access."
        ) from None
    if not 200 <= status < 300:
        raise ConnectorAPIError(
            f"webhook target answered HTTP {status} (body starts: {snippet[:200]!r})."
        )
    return {
        "delivered": True,
        "http_status": status,
        "body_bytes": len(body),
        "response_snippet": snippet[:200],
    }


class WebhookConnector(Connector):
    """POST JSON envelopes to the URL in ``LEVI_WEBHOOK_URL``."""

    id = "webhook"
    display_name = "Outbound Webhook"
    credential_env_var = "LEVI_WEBHOOK_URL"
    capabilities = (
        Capability(
            "webhook.post",
            "POST a JSON envelope to the configured webhook URL",
            write=True,
        ),
    )
    operations = (
        Operation(
            "post",
            "POST {'payload': <json>, 'event'?: <str>} to the webhook URL",
            write=True,
            params=("payload", "event", "headers"),
        ),
    )

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        if operation != "post":
            raise InvalidParams(f"unknown operation {operation!r} for webhook.")
        url = _validate_url(token)
        body, headers = _validate_payload(params)
        if transport is not None:
            result = transport("POST", url, token, {"body": body, "headers": headers})
            if isinstance(result, dict):
                return {"delivered": True, **result}
            return {"delivered": True, "transport_result": result}
        return _urllib_post(url, body, headers)


register_connector(WebhookConnector)
