"""LEVI MacroDroid bridge: live webhook path, both directions.

INBOUND (MacroDroid -> LEVI): MacroDroid's "HTTP Request" action POSTs
to a LEVI webhook URL (see ``SETUP.md``). Whatever serves LEVI webhooks
hands the ``(webhook_path, payload)`` pair to :func:`macrodroid_event`,
which builds a trigger event and calls the workflow engine::

    {"kind": "webhook", "source": "macrodroid:<path>", "payload": {...}}

This module complements the sibling ``_macrodroid_macro`` artifact
generator in ``..executor``: that one produces importable macro
scaffolds; this one is the *live* path.

OUTBOUND (LEVI -> MacroDroid): a workflow step that needs MacroDroid to
act calls :func:`fire_macrodroid` with the URL of the MacroDroid
"Webhook" trigger. Real HTTP POST via ``urllib`` (stdlib, 10s timeout);
returns an ok/evidence dict — never a silent failure.

Out of scope by design: a minimal inbound HTTP receiver. LEVI has no
standing server in this task; the webhook URL is served by whatever
serves LEVI webhooks. The event builder stays pure and testable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

__all__ = [
    "build_macrodroid_event",
    "macrodroid_event",
    "fire_macrodroid",
]


# ---------------------------------------------------------------------------
# Inbound: MacroDroid -> LEVI
# ---------------------------------------------------------------------------


def build_macrodroid_event(
    webhook_path: str, payload: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Pure event builder: ``(path, payload)`` -> trigger event dict.

    Raises :class:`ValueError` on a bad path, :class:`TypeError` on a
    non-dict payload. The payload is data, never instructions.
    """
    if not isinstance(webhook_path, str) or not webhook_path.strip():
        raise ValueError("macrodroid event: webhook_path must be a non-empty string")
    path = webhook_path.strip().lstrip("/")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise TypeError("macrodroid event: payload must be a dict")
    return {
        "kind": "webhook",
        "source": f"macrodroid:{path}",
        "payload": dict(payload),
    }


def macrodroid_event(
    webhook_path: str, payload: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build the trigger event and dispatch it. Returns the event dict.

    Raises :class:`RuntimeError` if the workflow engine's dispatch is not
    yet available — never silently fakes a dispatch.
    """
    event = build_macrodroid_event(webhook_path, payload)
    try:
        from ..flows import dispatch_trigger
    except ImportError as exc:
        raise RuntimeError("workflow engine dispatch not yet available") from exc
    dispatch_trigger(event)
    return event


# ---------------------------------------------------------------------------
# Outbound: LEVI -> MacroDroid
# ---------------------------------------------------------------------------


def fire_macrodroid(
    url: str, payload: Dict[str, Any], timeout: float = 10.0
) -> Dict[str, Any]:
    """POST a JSON payload to a MacroDroid Webhook trigger URL.

    Returns ``{"ok": bool, "status": int|None, "evidence": str}``.
    Only ``http``/``https`` URLs are accepted; everything else raises
    :class:`ValueError` deny-closed.
    """
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        raise ValueError("fire_macrodroid: url must be http:// or https://")
    if not isinstance(payload, dict):
        raise TypeError("fire_macrodroid: payload must be a dict")

    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Levi-Source": "levi-automation-macrodroid-bridge",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            status = resp.status
            snippet = resp.read(2048).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        snippet = (
            exc.read(2048).decode("utf-8", "replace") if hasattr(exc, "read") else ""
        )
        return {
            "ok": False,
            "status": exc.code,
            "evidence": f"MacroDroid webhook returned HTTP {exc.code}: {snippet[:200]}",
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": None,
            "evidence": f"MacroDroid webhook unreachable: {exc}",
        }

    return {
        "ok": 200 <= status < 300,
        "status": status,
        "evidence": f"POST {url} -> HTTP {status}: {snippet[:200]}",
    }
