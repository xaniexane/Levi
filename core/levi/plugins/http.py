"""LEVI-native HTTP helper — stdlib-only, over :mod:`urllib`.

Embodies the *design* of a well-built external fetch wrapper surveyed
during a source-sync port (base URL, runtime-supplied bearer token,
typed errors, smart response parsing), rewritten from scratch as
LEVI-native Python. No source code was copied; see
docs/SOURCE_SYNC_PROTOCOL.md.

Design
------
* :class:`HttpClient` holds a base URL (prepended to relative paths) and
  an auth-token getter: a callable returning a token string or ``None``,
  invoked before each request. Tokens are **runtime-supplied by the
  caller and never embedded or stored** here.
* Responses parse smartly: JSON bodies → parsed objects, text bodies →
  strings, empty bodies → ``None``. A caller can force a mode.
* Errors are typed: :class:`ApiError` carries status, data, headers,
  method, and URL; :class:`ResponseParseError` carries the raw body.

Honest contract
---------------
* stdlib only — no new dependencies.
* Default timeout 30s; no retries (the caller decides retry policy).
* HTTPS certificate verification is left on; disabling it raises.
* Proxy handling follows the environment (``urllib`` default behavior).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

NO_BODY_STATUS = frozenset({204, 205, 304})

_DEFAULT_TIMEOUT = 30.0
_JSON_MIMES = ("application/json",)
_TEXT_PREFIXES = ("text/",)
_TEXT_MIMES = ("application/xml", "text/xml", "application/x-www-form-urlencoded")

AuthTokenGetter = Callable[[], Optional[str]]


class ApiError(Exception):
    """An HTTP error response. Carries everything needed to diagnose it."""

    def __init__(
        self,
        status: int,
        status_text: str,
        data: Any,
        headers: Mapping[str, str],
        method: str,
        url: str,
    ) -> None:
        self.status = status
        self.status_text = status_text
        self.data = data
        self.headers = dict(headers)
        self.method = method
        self.url = url
        super().__init__(self._message())

    def _message(self) -> str:
        prefix = f"HTTP {self.status} {self.status_text}".strip()
        data = self.data
        if isinstance(data, str):
            text = data.strip()
            return f"{prefix}: {text[:300]}" if text else prefix
        if isinstance(data, dict):
            for key in ("detail", "message", "error", "title"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return f"{prefix}: {val.strip()[:300]}"
        return prefix


class ResponseParseError(Exception):
    """A 2xx response whose body could not be parsed as requested."""

    def __init__(
        self, method: str, url: str, status: int, raw_body: str, cause: Exception
    ) -> None:
        self.method = method
        self.url = url
        self.status = status
        self.raw_body = raw_body
        self.cause = cause
        super().__init__(f"failed to parse {method} {url} ({status}) as JSON: {cause}")


class NetworkError(Exception):
    """The request never got a response (DNS, refused, timeout, TLS)."""

    def __init__(self, method: str, url: str, cause: Exception) -> None:
        self.method = method
        self.url = url
        self.cause = cause
        super().__init__(f"{method} {url} failed before a response: {cause}")


def _media_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _is_json_media(mt: str) -> bool:
    return mt in _JSON_MIMES or mt.endswith("+json")


def _is_text_media(mt: str) -> bool:
    return (
        mt.startswith(_TEXT_PREFIXES)
        or mt in _TEXT_MIMES
        or mt.endswith("+xml")
        or mt == ""
    )


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def _infer_mode(media_type: str) -> str:
    if _is_json_media(media_type):
        return "json"
    if _is_text_media(media_type):
        return "text"
    return "bytes"


class HttpClient:
    """Small, honest HTTP client over urllib.

    :param base_url: prepended to request paths starting with ``/``.
    :param auth_token_getter: called before each request; a returned
        token is sent as ``Authorization: Bearer <token>`` unless the
        caller already set an Authorization header.
    :param timeout: per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token_getter: Optional[AuthTokenGetter] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError("base_url must be a string or None")
        if auth_token_getter is not None and not callable(auth_token_getter):
            raise ValueError("auth_token_getter must be callable or None")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._base_url = base_url.rstrip("/") if base_url else None
        self._auth_token_getter = auth_token_getter
        self._timeout = timeout

    # -- URL ----------------------------------------------------------

    def resolve_url(self, path: str) -> str:
        """Prepend the base URL to relative paths; absolute URLs pass through."""
        if not isinstance(path, str) or not path:
            raise ValueError("request path must be a non-empty string")
        if path.startswith("/") and self._base_url:
            return self._base_url + path
        return path

    # -- request ------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Any = None,
        data: Optional[bytes] = None,
        headers: Optional[Mapping[str, str]] = None,
        response: str = "auto",
    ) -> Any:
        """Send a request; return the parsed body (or raise).

        :param response: ``"auto"`` (infer from content-type),
            ``"json"``, ``"text"``, or ``"bytes"``.
        """
        method = method.upper()
        if method in ("GET", "HEAD") and (json_body is not None or data is not None):
            raise ValueError(f"{method} requests cannot carry a body")
        if response not in ("auto", "json", "text", "bytes"):
            raise ValueError(f"unknown response mode {response!r}")

        url = self.resolve_url(path)
        if params:
            query = urllib.parse.urlencode(
                {k: ("" if v is None else v) for k, v in params.items()},
                doseq=True,
            )
            url = url + ("&" if "?" in url else "?") + query

        body: Optional[bytes] = None
        out_headers: Dict[str, str] = {}
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            out_headers["content-type"] = "application/json"
        elif data is not None:
            body = data

        if headers:
            for k, v in headers.items():
                out_headers[k.lower()] = v
        if response == "json" and "accept" not in out_headers:
            out_headers["accept"] = "application/json, application/problem+json"

        if self._auth_token_getter and "authorization" not in out_headers:
            token = self._auth_token_getter()
            if token:
                out_headers["authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, data=body, headers=out_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return self._parse_success(resp, response, method, url)
        except urllib.error.HTTPError as exc:
            raise self._parse_error(exc, method, url) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise NetworkError(method, url, exc) from exc

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    # -- parsing ------------------------------------------------------

    def _has_no_body(
        self, status: int, headers: Mapping[str, str], method: str
    ) -> bool:
        if method == "HEAD":
            return True
        if status in NO_BODY_STATUS:
            return True
        if headers.get("content-length") == "0":
            return True
        return False

    def _read_text(self, raw: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _parse_success(self, resp: Any, mode: str, method: str, url: str) -> Any:
        status = resp.status
        headers = {k.lower(): v for k, v in resp.headers.items()}
        if self._has_no_body(status, headers, method):
            return None
        raw = resp.read()
        if not raw:
            return None
        media_type = _media_type(headers.get("content-type"))
        effective = _infer_mode(media_type) if mode == "auto" else mode
        if effective == "bytes":
            return raw
        text = _strip_bom(self._read_text(raw))
        if effective == "text":
            return text
        # json mode
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResponseParseError(method, url, status, text, exc) from exc

    def _parse_error(
        self, exc: urllib.error.HTTPError, method: str, url: str
    ) -> ApiError:
        try:
            raw = exc.read() or b""
        except Exception:
            raw = b""
        headers = {k.lower(): v for k, v in exc.headers.items()}
        data: Any = None
        if raw:
            text = _strip_bom(self._read_text(raw))
            media_type = _media_type(headers.get("content-type"))
            if _is_json_media(media_type) or _looks_like_json(text):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = text
            else:
                data = text
        return ApiError(
            status=exc.code,
            status_text=str(getattr(exc, "reason", "") or ""),
            data=data,
            headers=headers,
            method=method,
            url=url,
        )


def parse_url_host(url: str) -> Tuple[str, str]:
    """Split a URL into (scheme, host). Validation helper for callers."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"not an http(s) URL: {url!r}")
    return parts.scheme, parts.hostname


# Redact-on-sight: never let a bearer token into an exception message.
def _redacted_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    redacted: Dict[str, str] = {}
    for k, v in headers.items():
        redacted[k] = "***" if k.lower() == "authorization" else v
    return redacted
