"""First-class filters: priority-ordered, deterministic, self-explaining.

A Filter is data: ``{id, predicates, action, priority}``. Evaluation
is ``disposition(message, filters)``: filters sorted by priority
(stable tiebreak on id — the order is total), the first filter whose
predicates all match wins, and the matched filter id is stamped on
the disposition. Same message + same filter set → same disposition,
always.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

__all__ = ["Filter", "disposition", "DEFAULT_ACTION"]

DEFAULT_ACTION = ("inbox", "default")


@dataclass(frozen=True)
class Filter:
    """A filter: predicates are pure; action is data, not code."""

    id: str
    predicates: Tuple[Dict[str, Any], ...]
    action: str
    priority: int = 100
    note: str = ""


def _field_text(message: Dict[str, Any], field_name: str) -> str:
    value = message.get(field_name, "")
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def predicate_matches(predicate: Dict[str, Any], message: Dict[str, Any]) -> bool:
    """Pure predicate evaluation. Unknown predicate kinds do NOT match."""
    field_name = predicate.get("field", "")
    if "contains" in predicate:
        needle = str(predicate["contains"]).lower()
        return needle in _field_text(message, field_name).lower()
    if "contains_any" in predicate:
        text = _field_text(message, field_name).lower()
        return any(str(n).lower() in text for n in predicate["contains_any"])
    if "is_true" in predicate:
        return bool(message.get(field_name)) is bool(predicate["is_true"])
    if "equals" in predicate:
        return (
            _field_text(message, field_name).lower() == str(predicate["equals"]).lower()
        )
    if "domain_is" in predicate:
        addr = _field_text(message, field_name).lower()
        domain = addr.split("@")[-1] if "@" in addr else ""
        return domain == str(predicate["domain_is"]).lower()
    return False


def disposition(message: Dict[str, Any], filters: List[Filter]) -> Dict[str, str]:
    """Evaluate filters in priority order; stamp the matched filter id.

    Returns ``{"action": ..., "filter_id": ..., "folder": ...}``.
    ``action`` values: ``file:<folder>``, ``flag``, ``reply-draft``,
    ``drop``. Unmatched messages go to ``inbox`` with filter
    id ``default``.
    """
    ordered = sorted(filters, key=lambda f: (f.priority, f.id))
    for filt in ordered:
        if all(predicate_matches(p, message) for p in filt.predicates):
            return {
                "action": filt.action,
                "filter_id": filt.id,
                "folder": _action_folder(filt.action),
            }
    return {
        "action": DEFAULT_ACTION[0],
        "filter_id": DEFAULT_ACTION[1],
        "folder": "inbox",
    }


def _action_folder(action: str) -> str:
    if action.startswith("file:"):
        return action[len("file:") :]
    if action == "drop":
        return "trash"
    return "inbox"
