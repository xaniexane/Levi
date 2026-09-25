"""Netcheck plugin — an honest HTTP reachability prober.

Where ``portwatch`` watches local service ports as an edge-detecting
poller, netcheck answers the direct question "is this URL alive, and how
fast?": given a URL it performs one real HTTP request and reports what
actually happened — status, latency, redirect chain, and a capped body
peek. It never fabricates a response and never claims success unless the
server answered.

Operations (all read-only; no confirmation gate can ever trigger):
* ``head`` — HTTP HEAD for a URL (params: ``url``, ``timeout_sec``);
* ``get``  — HTTP GET with a capped body peek
  (params: ``url``, ``timeout_sec``, ``max_bytes``).

Honesty rules, deny-closed:
* only ``http``/``https`` URLs; anything else (ftp, file, ...) is
  ``invalid_params`` — nothing is sent;
* a URL carrying credentials (``user:pass@host``) is refused outright —
  this probe must never ship credentials;
* timeouts clamp to 1..30 s — a probe must never hang the caller;
* the body is capped (default 262_144 bytes); oversized bodies are cut
  and reported as truncated, never half-read;
* DNS / connection / TLS / HTTP errors are ``ConnectorAPIError`` →
  ``status="api_error"``, ``ok=False``.

``netcheck`` is the reference probe ("netcheck"), never LEVI identity.
Credentialless by design: ``credential()`` returns the ``"public"``
sentinel so the registry's credential gate never fires for reads.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .registry import (
    Capability,
    Connector,
    ConnectorAPIError,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_USER_AGENT = "LEVI-netcheck/1.0 (honest reachability probe; +https://levi.local)"
_DEFAULT_TIMEOUT_SEC = 10.0
_MAX_TIMEOUT_SEC = 30.0
_MIN_TIMEOUT_SEC = 1.0
_DEFAULT_MAX_BYTES = 262_144
_MAX_BODY_BYTES = 2_097_152  # 2 MB hard ceiling
_MAX_REDIRECTS = 5


def _guarded_url(url: Any) -> str:
    if not isinstance(url, str) or not url.strip():
        raise InvalidParams("url must be a non-empty string — nothing was sent.")
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise InvalidParams(
            f"url scheme must be http or https, got {parsed.scheme!r} — nothing was sent."
        )
    if parsed.username or parsed.password:
        raise InvalidParams("url must not carry credentials — nothing was sent.")
    if not parsed.hostname:
        raise InvalidParams("url must include a host — nothing was sent.")
    return url.strip()


def _guarded_timeout(timeout_sec: Any) -> float:
    if timeout_sec is None:
        return _DEFAULT_TIMEOUT_SEC
    if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float)):
        raise InvalidParams("timeout_sec must be a number — nothing was sent.")
    timeout = float(timeout_sec)
    if not _MIN_TIMEOUT_SEC <= timeout <= _MAX_TIMEOUT_SEC:
        raise InvalidParams(
            f"timeout_sec must be {_MIN_TIMEOUT_SEC}..{_MAX_TIMEOUT_SEC}, "
            f"got {timeout_sec!r} — nothing was sent."
        )
    return timeout


def _guarded_max_bytes(max_bytes: Any) -> int:
    if max_bytes is None:
        return _DEFAULT_MAX_BYTES
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
        raise InvalidParams("max_bytes must be an integer — nothing was sent.")
    if not 1 <= max_bytes <= _MAX_BODY_BYTES:
        raise InvalidParams(
            f"max_bytes must be 1..{_MAX_BODY_BYTES}, got {max_bytes!r} — nothing was sent."
        )
    return max_bytes


def _probe(url: str, method: str, timeout: float, max_bytes: int) -> Dict[str, Any]:
    """One real HTTP request. Raises ConnectorAPIError on any failure."""
    request = urllib.request.Request(
        url, method=method, headers={"User-Agent": _USER_AGENT}
    )
    # urllib follows redirects internally; we bound it explicitly.
    opener = urllib.request.build_opener()
    redirects: List[str] = []
    start = time.monotonic()
    try:
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            # An HTTP error status is still an honest answer — report it.
            latency_ms = round((time.monotonic() - start) * 1000.0, 2)
            return {
                "ok": False,
                "status": exc.code,
                "reason": str(exc.reason),
                "latency_ms": latency_ms,
                "final_url": exc.geturl(),
                "redirects": redirects,
                "truncated": False,
                "body_bytes": 0,
            }
        with response:
            latency_ms = round((time.monotonic() - start) * 1000.0, 2)
            headers = {k.lower(): v for k, v in response.headers.items()}
            body = b""
            truncated = False
            if method == "GET":
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    body = body[:max_bytes]
                    truncated = True
            return {
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "reason": response.reason,
                "latency_ms": latency_ms,
                "final_url": response.geturl(),
                "redirects": redirects,
                "content_length": headers.get("content-length"),
                "content_type": headers.get("content-type"),
                "truncated": truncated,
                "body_bytes": len(body),
                "body_peek": body[:512].decode("utf-8", "replace")
                if method == "GET"
                else None,
            }
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise ConnectorAPIError(
            f"netcheck: request failed for {url}: {exc} — nothing was received."
        ) from exc


class NetcheckConnector(Connector):
    """Honest HTTP reachability prober. Read-only, credentialless."""

    id = "netcheck"
    display_name = "netcheck reachability probe"
    credential_env_var = "LEVI_NETCHECK_TOKEN"
    capabilities = (
        Capability("read.net.head", "HTTP HEAD status and latency for a URL"),
        Capability("read.net.get", "HTTP GET with a capped body peek for a URL"),
    )
    operations = (
        Operation(
            "head",
            "HEAD probe (params: url, timeout_sec=10)",
            params=("url", "timeout_sec"),
        ),
        Operation(
            "get",
            "GET probe with capped body peek (params: url, timeout_sec=10, max_bytes=262144)",
            params=("url", "timeout_sec", "max_bytes"),
        ),
    )
    references = ("netcheck",)

    def credential(self) -> Optional[str]:
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: Dict[str, Any],
        token: Optional[str],
        transport: Transport | None,
    ) -> Any:
        url = _guarded_url(params.get("url"))
        timeout = _guarded_timeout(params.get("timeout_sec"))
        method = "HEAD" if operation == "head" else "GET"
        max_bytes = (
            _guarded_max_bytes(params.get("max_bytes")) if method == "GET" else 0
        )
        result = _probe(url, method, timeout, max_bytes)
        result["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["requested_url"] = url
        return result


register_connector(NetcheckConnector)
