"""Dynamic-UI protocol emitter — lets the agent build interactive chat UI
(button rows, cards, forms, progress) as structured JSON.

The agent emits **data only**: a ``{"kind": "dynamic-ui", "version": 1,
"elements": [...]}`` envelope the web client renders.  No JavaScript, no
HTML, no raw URLs-without-confirmation ever leaves the agent side.

Every builder validates its input against the protocol allowlist defined in
``docs/DYNAMIC_UI.md`` and raises :class:`DynamicUIError` on violation, so
the agent can only emit what the client can safely render.

Only the standard library is used.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "DynamicUIError",
    "PROTOCOL_VERSION",
    "buttons",
    "card",
    "envelope",
    "form",
    "intent_action",
    "progress",
    "text",
    "url_action",
    "validate_payload",
]

PROTOCOL_VERSION = 1

ELEMENT_TYPES = ("text", "buttons", "card", "form", "progress")
FIELD_TYPES = ("text", "number", "select", "toggle")
BUTTON_STYLES = ("primary", "ghost", "danger")
TEXT_TONES = ("body", "muted", "accent")
ACTION_KINDS = ("intent", "url")
URL_SCHEMES = ("http", "https")

MAX_ELEMENTS = 16
MAX_TEXT_LENGTH = 2000
MAX_TITLE_LENGTH = 120
MAX_BUTTONS = 8
MAX_FIELDS = 10
MAX_SELECT_OPTIONS = 12
MAX_LABEL_LENGTH = 80

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
# Intent names containing one of these verbs are destructive and MUST be
# emitted with confirm=True (the client also enforces a two-tap confirm).
_DESTRUCTIVE_VERBS = ("delete", "remove", "pay", "publish", "share", "grant", "revoke")


class DynamicUIError(ValueError):
    """Raised when a dynamic-UI payload violates the protocol allowlist."""


def _require_str(value: Any, field: str, max_len: int) -> str:
    if not isinstance(value, str) or not value:
        raise DynamicUIError(f"{field} must be a non-empty string")
    if len(value) > max_len:
        raise DynamicUIError(f"{field} exceeds {max_len} characters")
    return value


def _require_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise DynamicUIError(f"{field} must match {_NAME_RE.pattern} (got {value!r})")
    return value


def _check_jsonable(value: Any, field: str) -> None:
    """Reject values that cannot survive a JSON round-trip as plain data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _check_jsonable(item, field)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DynamicUIError(f"{field}: arg keys must be strings")
            _check_jsonable(item, field)
        return
    raise DynamicUIError(
        f"{field}: args must be plain JSON data, got {type(value).__name__}"
    )


def intent_action(
    intent: str, args: dict[str, Any] | None = None, confirm: bool = False
) -> dict[str, Any]:
    """Build an action that routes back to the agent as a structured intent."""
    _require_name(intent, "intent")
    payload: dict[str, Any] = {"kind": "intent", "intent": intent}
    if args is not None:
        if not isinstance(args, dict):
            raise DynamicUIError("args must be a dict")
        _check_jsonable(args, "args")
        payload["args"] = args
    lowered = intent.lower()
    if any(verb in lowered for verb in _DESTRUCTIVE_VERBS) and not confirm:
        raise DynamicUIError(
            f"intent {intent!r} looks destructive and requires confirm=True"
        )
    if confirm:
        payload["confirm"] = True
    return payload


def url_action(url: str, confirm: bool = True) -> dict[str, Any]:
    """Build an external-link action. http(s) only; confirmation by default."""
    _require_str(url, "url", 2000)
    scheme = url.split(":", 1)[0].lower()
    if scheme not in URL_SCHEMES:
        raise DynamicUIError(
            f"url scheme must be one of {URL_SCHEMES}, got {scheme!r} "
            "(never javascript:, data:, file:, …)"
        )
    payload: dict[str, Any] = {"kind": "url", "url": url}
    if confirm:
        payload["confirm"] = True
    return payload


def _validate_action(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise DynamicUIError("action must be a dict")
    kind = action.get("kind")
    if kind == "intent":
        return intent_action(
            action.get("intent"),
            action.get("args"),
            bool(action.get("confirm", False)),
        )
    if kind == "url":
        return url_action(action.get("url"), bool(action.get("confirm", True)))
    raise DynamicUIError(f"unknown action kind {kind!r}; allowed: {ACTION_KINDS}")


def _validate_button(button: Any) -> dict[str, Any]:
    if not isinstance(button, dict):
        raise DynamicUIError("button must be a dict")
    style = button.get("style", "primary")
    if style not in BUTTON_STYLES:
        raise DynamicUIError(f"button style must be one of {BUTTON_STYLES}")
    return {
        "label": _require_str(button.get("label"), "button label", MAX_LABEL_LENGTH),
        "action": _validate_action(button.get("action")),
        "style": style,
    }


def text(text_content: str, tone: str = "body") -> dict[str, Any]:
    """A plain text block inside the dynamic-UI envelope."""
    if tone not in TEXT_TONES:
        raise DynamicUIError(f"tone must be one of {TEXT_TONES}")
    return {
        "type": "text",
        "text": _require_str(text_content, "text", MAX_TEXT_LENGTH),
        "tone": tone,
    }


def buttons(button_defs: list[dict[str, Any]]) -> dict[str, Any]:
    """A row of 1–8 action buttons."""
    if not isinstance(button_defs, list) or not 1 <= len(button_defs) <= MAX_BUTTONS:
        raise DynamicUIError(f"buttons needs 1–{MAX_BUTTONS} button definitions")
    return {"type": "buttons", "buttons": [_validate_button(b) for b in button_defs]}


def card(
    title: str, body: str | None = None, actions: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """A titled card with optional body text and action buttons."""
    element: dict[str, Any] = {
        "type": "card",
        "title": _require_str(title, "card title", MAX_TITLE_LENGTH),
    }
    if body is not None:
        element["body"] = _require_str(body, "card body", MAX_TEXT_LENGTH)
    if actions is not None:
        if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_BUTTONS:
            raise DynamicUIError(f"card actions need 1–{MAX_BUTTONS} buttons")
        element["actions"] = [_validate_button(b) for b in actions]
    return element


def _validate_field(field: Any) -> dict[str, Any]:
    if not isinstance(field, dict):
        raise DynamicUIError("form field must be a dict")
    kind = field.get("field")
    if kind not in FIELD_TYPES:
        raise DynamicUIError(f"field type must be one of {FIELD_TYPES}, got {kind!r}")
    out: dict[str, Any] = {
        "name": _require_name(field.get("name"), "field name"),
        "label": _require_str(field.get("label"), "field label", MAX_LABEL_LENGTH),
        "field": kind,
    }
    if "placeholder" in field and field["placeholder"] is not None:
        out["placeholder"] = _require_str(
            field["placeholder"], "placeholder", MAX_LABEL_LENGTH
        )
    if "required" in field:
        out["required"] = bool(field["required"])
    if kind == "select":
        options = field.get("options")
        if not isinstance(options, list) or not 2 <= len(options) <= MAX_SELECT_OPTIONS:
            raise DynamicUIError(f"select needs 2–{MAX_SELECT_OPTIONS} options")
        for opt in options:
            _require_str(opt, "select option", MAX_LABEL_LENGTH)
        out["options"] = list(options)
    if kind == "number":
        for bound in ("min", "max"):
            if bound in field and field[bound] is not None:
                if not isinstance(field[bound], (int, float)) or isinstance(
                    field[bound], bool
                ):
                    raise DynamicUIError(f"number field {bound} must be numeric")
                out[bound] = field[bound]
    if kind == "toggle":
        out["default"] = bool(field.get("default", False))
    elif "default" in field and field["default"] is not None:
        default = field["default"]
        if kind == "number" and not isinstance(default, (int, float)):
            raise DynamicUIError("number field default must be numeric")
        if kind in ("text", "select") and not isinstance(default, str):
            raise DynamicUIError(f"{kind} field default must be a string")
        if kind == "select" and default not in out["options"]:
            raise DynamicUIError("select default must be one of the options")
        out["default"] = default
    return out


def form(
    fields: list[dict[str, Any]],
    submit_label: str,
    submit_action: dict[str, Any],
    title: str | None = None,
) -> dict[str, Any]:
    """An input form whose submit routes the collected values back as an intent."""
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        raise DynamicUIError(f"form needs 1–{MAX_FIELDS} fields")
    element: dict[str, Any] = {
        "type": "form",
        "fields": [_validate_field(f) for f in fields],
        "submit": {
            "label": _require_str(submit_label, "submit label", MAX_LABEL_LENGTH),
            "action": _validate_action(submit_action),
        },
    }
    if title is not None:
        element["title"] = _require_str(title, "form title", MAX_TITLE_LENGTH)
    return element


def progress(
    value: float | None = None, label: str | None = None, indeterminate: bool = False
) -> dict[str, Any]:
    """A progress indicator. Pass indeterminate=True when no value is known."""
    element: dict[str, Any] = {"type": "progress"}
    if indeterminate:
        element["indeterminate"] = True
    elif value is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DynamicUIError("progress value must be numeric")
        element["value"] = max(0.0, min(1.0, float(value)))
    else:
        element["indeterminate"] = True
    if label is not None:
        element["label"] = _require_str(label, "progress label", MAX_LABEL_LENGTH)
    return element


def validate_payload(payload: Any) -> dict[str, Any]:
    """Validate an arbitrary dict as a dynamic-UI envelope.

    Returns a normalized copy. Raises :class:`DynamicUIError` on any
    protocol violation. Unknown element *types* are rejected here too —
    the graceful-plain-text fallback is a client rendering rule, but the
    agent must never emit what the client cannot render natively.
    """
    if not isinstance(payload, dict):
        raise DynamicUIError("payload must be a dict")
    if payload.get("kind") != "dynamic-ui":
        raise DynamicUIError("payload kind must be 'dynamic-ui'")
    if payload.get("version") != PROTOCOL_VERSION:
        raise DynamicUIError(f"unsupported protocol version {payload.get('version')!r}")
    elements = payload.get("elements")
    if not isinstance(elements, list) or not 1 <= len(elements) <= MAX_ELEMENTS:
        raise DynamicUIError(f"elements must be a list of 1–{MAX_ELEMENTS} elements")
    normalized: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            raise DynamicUIError("each element must be a dict")
        etype = el.get("type")
        if etype not in ELEMENT_TYPES:
            raise DynamicUIError(
                f"unknown element type {etype!r}; allowed: {ELEMENT_TYPES}"
            )
        normalized.append(_rebuild_element(etype, el))
    return {"kind": "dynamic-ui", "version": PROTOCOL_VERSION, "elements": normalized}


def _rebuild_element(etype: str, el: dict[str, Any]) -> dict[str, Any]:
    """Re-run an element dict through its builder for full field validation."""
    if etype == "text":
        return text(el.get("text"), el.get("tone", "body"))
    if etype == "buttons":
        return buttons(el.get("buttons"))
    if etype == "card":
        return card(el.get("title"), el.get("body"), el.get("actions"))
    if etype == "form":
        submit = el.get("submit") or {}
        return form(
            el.get("fields"), submit.get("label"), submit.get("action"), el.get("title")
        )
    if etype == "progress":
        return progress(
            el.get("value"), el.get("label"), bool(el.get("indeterminate", False))
        )
    raise DynamicUIError(f"unknown element type {etype!r}")  # unreachable


def envelope(*elements: dict[str, Any]) -> dict[str, Any]:
    """Build and validate a complete dynamic-UI envelope from elements."""
    return validate_payload(
        {"kind": "dynamic-ui", "version": PROTOCOL_VERSION, "elements": list(elements)}
    )
