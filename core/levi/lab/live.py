"""Optional live chat against any OpenAI-compatible endpoint (stdlib only).

The endpoint is never hardcoded: it comes from the ``--endpoint`` argument
or the ``LEVI_LAB_ENDPOINT`` environment variable. ``probe()`` checks
reachability plus ``GET /v1/models``; ``chat()`` posts to
``POST /v1/chat/completions``. Failures are returned as dicts, never raised.
"""

from __future__ import annotations

import json
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


def probe(endpoint: str, timeout: float = 8.0) -> dict:
    """Check an endpoint: reachable + GET /v1/models. Never raises."""
    try:
        status, body = _get(endpoint + "/v1/models", timeout)
    except ConnectionError as exc:
        return {"ok": False, "endpoint": endpoint, "error": f"unreachable: {exc}"}
    try:
        data = json.loads(body)
        models = [m.get("id", "?") for m in data.get("data", [])]
    except (ValueError, AttributeError):
        models = []
    return {
        "ok": status == 200,
        "endpoint": endpoint,
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
    """POST /v1/chat/completions passthrough. Never raises."""
    try:
        status, body = _post(
            endpoint + "/v1/chat/completions",
            {"model": model, "messages": messages},
            timeout,
        )
    except ConnectionError as exc:
        return {"ok": False, "endpoint": endpoint, "error": f"unreachable: {exc}"}
    if status != 200:
        return {"ok": False, "endpoint": endpoint, "error": f"HTTP {status}: {body[:300]}"}
    try:
        data = json.loads(body)
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return {"ok": False, "endpoint": endpoint, "error": f"bad response: {exc}"}
    return {"ok": True, "endpoint": endpoint, "model": model, "text": text}


def format_probe(result: dict) -> str:
    if not result["ok"]:
        return f"lab chat: probe FAILED — {result.get('error')}"
    models = ", ".join(result["models"][:10]) or "(no models listed)"
    return (
        f"lab chat: endpoint reachable — {result['endpoint']}\n"
        f"  models: {models}"
    )
