"""Cybrus inbound channel adapters — the wiring in front of FRONT-GUARD.

Email, text, and notification intake live HERE. Each adapter takes a raw
channel item, normalizes it to the screening message shape, and routes
it through ``levi.cybrus.front.screen_message`` — the screening DECISION
layer owned by 🏰 (FRONT-GUARD). This module never edits front.py and
never reimplements a single screening rule.

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_front_feed.py — honestly named invariant checks):
  AD1 One gate, no bypass. Every item passes through screening before
      any delivery. There is no direct-deliver path in this module —
      ``deliver`` does not exist as a public function; the only route
      to delivery crosses ``screen_message``.
  AD2 Decisions are not made here. Verdicts (CLEAN/WARN/QUARANTINE)
      come only from front. This module reads them and routes;
      it scores nothing and invents no thresholds.
  AD3 Fail closed. Any adapter error (bad raw shape, screening
      exception, normalization failure) yields HELD, never delivered.
  AD4 Receipts with every item. Every intake returns the screening
      receipt alongside the routing outcome — no receipt, no delivery
      claim.
  AD5 Metadata-only audit through the tamper-evident AuditEngine:
      message_id, channel, verdict, score, rules — never bodies,
      never secrets.
  AD6 No new egress. Stdlib only, zero network. Adapters never send,
      reply, fetch, or report upstream.
  AD7 Coverage, not bypass. Enforced through the existing 12 Cybrus
      laws; no exceptions to them.

Routing: CLEAN → delivered. WARN → delivered WITH a ``front_warning``
banner (never silently delivered). QUARANTINE → held, receipt returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

# --- standalone-safe sibling imports (same pattern as front.py) ---------
def _cybrus_module(name: str):
    try:
        from levi.cybrus import _paths as _p  # noqa: F401

        import importlib

        return importlib.import_module(f"levi.cybrus.{name}")
    except ImportError:
        import importlib.util

        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            f"levi.cybrus.{name}.standalone", here / f"{name}.py"
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError(f"cybrus module {name!r} unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _front():
    return _cybrus_module("front")


def _AuditEngine():
    """An AuditEngine instance (tamper-evident audit log)."""
    return _cybrus_module("audit").AuditEngine()


#: The only channels this module adapts — kept in step with front.CHANNELS.
CHANNELS = ("email", "text", "notification")


def _audit(receipt: Dict[str, Any], outcome: str) -> None:
    try:
        _AuditEngine().append(
            "cybrus.adapters.intake",
            "cybrus-adapters",
            {
                "message_id": receipt.get("message_id"),
                "channel": receipt.get("channel"),
                "verdict": receipt.get("verdict"),
                "score": receipt.get("score"),
                "rules": list(receipt.get("rules") or []),
                "outcome": outcome,
                "receipt_hash": receipt.get("receipt_hash"),
            },
        )
    except Exception:
        # AD3/AD5: audit failure must not flip a routing decision.
        pass


def _normalize(channel: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw channel item to the front.screen_message shape.

    front accepts missing keys as absent signals (never as evidence of
    cleanliness), so normalization is field-mapping only — no default
    sender, no invented subject, nothing that could look clean by
    construction.
    """
    return {
        "id": str(raw.get("id") or ""),
        "channel": channel,
        "from": str(raw.get("from") or ""),
        "reply_to": str(raw.get("reply_to") or ""),
        "subject": str(raw.get("subject") or ""),
        "body": str(raw.get("body") or raw.get("text") or ""),
        "urls": list(raw.get("urls") or []),
        "attachments": list(raw.get("attachments") or []),
    }


def _route(screened: Dict[str, Any], message: Dict[str, Any]) -> Dict[str, Any]:
    verdict = screened.get("verdict")
    if verdict == "CLEAN":
        outcome = {"delivered": True, "held": False, "item": message}
    elif verdict == "WARN":
        warned = dict(message)
        warned["front_warning"] = {
            "rules": list(screened.get("rules") or []),
            "score": screened.get("score"),
            "receipt_hash": screened.get("receipt_hash"),
        }
        outcome = {"delivered": True, "held": False, "item": warned}
    else:  # QUARANTINE and anything unexpected: hold, never deliver (AD3)
        outcome = {"delivered": False, "held": True, "item": None}
    return outcome


def intake(channel: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Intake one raw item on a channel. NEVER raises (AD3).

    The single crossing point: normalize → screen (front, 🏰's
    decision layer) → route. Returns ``{delivered, held, verdict,
    receipt, item}``; ``item`` is None when held.
    """
    try:
        ch = str(channel or "unknown")
        if ch not in CHANNELS:
            ch = "unknown"
        if not isinstance(raw, dict):
            raise TypeError(f"raw item must be a dict, got {type(raw).__name__}")
        message = _normalize(ch, dict(raw))
        front = _front()
        screened = front.screen_message(message)
        outcome = _route(screened, message)
        _audit(screened, "delivered" if outcome["delivered"] else "held")
        return {
            "delivered": outcome["delivered"],
            "held": outcome["held"],
            "verdict": screened.get("verdict"),
            "receipt": screened,
            "item": outcome["item"],
        }
    except Exception as exc:  # AD3: adapter failure = held, never delivered
        receipt = {
            "message_id": "",
            "channel": str(channel or "unknown"),
            "verdict": "QUARANTINE",
            "score": 100,
            "rules": ["AD99"],
            "error": f"{type(exc).__name__}",
        }
        _audit(receipt, "held")
        return {
            "delivered": False,
            "held": True,
            "verdict": "QUARANTINE",
            "receipt": receipt,
            "item": None,
        }


def email(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Intake on the email channel."""
    return intake("email", raw)


def text(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Intake on the text (SMS) channel."""
    return intake("text", raw)


def notification(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Intake on the notification channel."""
    return intake("notification", raw)


def describe_posture() -> Dict[str, Any]:
    """Backend posture, honestly reported (12-law L12)."""
    return {
        "module": "levi.cybrus.adapters",
        "laws": ["AD1", "AD2", "AD3", "AD4", "AD5", "AD6", "AD7"],
        "channels": list(CHANNELS),
        "screening": "levi.cybrus.front.screen_message (🏰 FRONT-GUARD, never edited here)",
        "delivery_paths": ["intake(email|text|notification) -> screen -> route"],
        "direct_deliver_exists": False,
        "proof": "tests/test_front_feed.py (invariant checks, not formal proof)",
    }
