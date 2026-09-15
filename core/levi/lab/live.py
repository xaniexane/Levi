"""Optional live chat against any OpenAI-compatible endpoint (stdlib only).

The endpoint is never hardcoded: it comes from the ``--endpoint`` argument
or the ``LEVI_LAB_ENDPOINT`` environment variable. ``probe()`` checks
reachability plus ``GET /v1/models``; ``chat()`` posts to
``POST /v1/chat/completions``. Failures are returned as dicts, never raised.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
import urllib.error


def resolve_endpoint(explicit: str | None = None) -> str | None:
    """Endpoint from explicit arg, else LEVI_LAB_ENDPOINT env, else None."""
    ep = (explicit or os.environ.get("LEVI_LAB_ENDPOINT") or "").strip().rstrip("/")
    return ep or None


def _get(url: str, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # unreachable host, timeout, DNS, …
        raise ConnectionError(str(exc)) from exc


def _post(url: str, payload: dict, timeout: float) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        raise ConnectionError(str(exc)) from exc


def _validate_endpoint(endpoint: object) -> str | None:
    if not isinstance(endpoint, str) or not endpoint.strip():
        return None
    return endpoint.strip().rstrip("/")


def _validate_timeout(timeout: object) -> float | None:
    try:
        t = float(timeout)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(t) or t <= 0:
        return None
    return t


def probe(endpoint: str, timeout: float = 8.0) -> dict:
    """Check an endpoint: reachable + GET /v1/models. Never raises.

    Failures — including invalid arguments — come back as dicts.
    """
    ep = _validate_endpoint(endpoint)
    t = _validate_timeout(timeout)
    if ep is None or t is None:
        return {
            "ok": False,
            "endpoint": endpoint,
            "error": "invalid endpoint or timeout "
            "(endpoint must be a non-empty URL string, timeout a positive number)",
        }
    try:
        status, body = _get(ep + "/v1/models", t)
    except ConnectionError as exc:
        return {"ok": False, "endpoint": ep, "error": f"unreachable: {exc}"}
    try:
        data = json.loads(body)
        models = [m.get("id", "?") for m in data.get("data", [])]
    except (ValueError, AttributeError):
        models = []
    return {
        "ok": status == 200,
        "endpoint": ep,
        "http_status": status,
        "models": models,
        "error": None if status == 200 else f"HTTP {status}: {body[:200]}",
    }


def chat(
    endpoint: str,
    model: str,
    messages: list[dict],
    timeout: float = 60.0,
) -> dict:
    """POST /v1/chat/completions passthrough. Never raises (failures -> dict)."""
    ep = _validate_endpoint(endpoint)
    t = _validate_timeout(timeout)
    if ep is None or t is None:
        return {
            "ok": False,
            "endpoint": endpoint,
            "error": "invalid endpoint or timeout "
            "(endpoint must be a non-empty URL string, timeout a positive number)",
        }
    if not isinstance(model, str) or not model.strip():
        return {
            "ok": False,
            "endpoint": ep,
            "error": "model must be a non-empty string",
        }
    if (
        not isinstance(messages, list)
        or not messages
        or any(not isinstance(m, dict) for m in messages)
    ):
        return {
            "ok": False,
            "endpoint": ep,
            "error": "messages must be a non-empty list of message dicts",
        }
    for i, m in enumerate(messages):
        if not isinstance(m.get("content"), str):
            return {
                "ok": False,
                "endpoint": ep,
                "error": f"messages[{i}] needs a string 'content'",
            }
    try:
        status, body = _post(
            ep + "/v1/chat/completions",
            {"model": model.strip(), "messages": messages},
            t,
        )
    except ConnectionError as exc:
        return {"ok": False, "endpoint": ep, "error": f"unreachable: {exc}"}
    if status != 200:
        return {
            "ok": False,
            "endpoint": ep,
            "error": f"HTTP {status}: {body[:300]}",
        }
    try:
        data = json.loads(body)
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return {"ok": False, "endpoint": ep, "error": f"bad response: {exc}"}
    return {"ok": True, "endpoint": ep, "model": model, "text": text}


def format_probe(result: dict) -> str:
    """One-line human-readable rendering of :func:`probe`.

    Tolerates malformed results: renders a FAILED line rather than a
    KeyError.
    """
    if not isinstance(result, dict) or not result.get("ok"):
        err = (
            result.get("error", "invalid probe result")
            if isinstance(result, dict)
            else "invalid probe result"
        )
        return f"lab chat: probe FAILED — {err}"
    models = ", ".join(result["models"][:10]) or "(no models listed)"
    return f"lab chat: endpoint reachable — {result['endpoint']}\n  models: {models}"
