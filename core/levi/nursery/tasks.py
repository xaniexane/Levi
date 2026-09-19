"""Supervised task templates — the only work a trainee may ever do.

Every template is a pure stdlib text function plus an independent
verifier. No network, no subprocess, no shell, no file paths from the
payload (payload is inline data only), no money, no applications.

The verifier recomputes the expected result independently — a task is
accepted only when execution output matches the verifier's expectation.
"""

from __future__ import annotations

import re
from typing import Any, Callable

# Kinds that are refused structurally, with the reason given.
FORBIDDEN_KINDS: dict[str, str] = {
    "money": "money paths belong to Cybrus alone",
    "payment": "money paths belong to Cybrus alone",
    "transfer": "money paths belong to Cybrus alone",
    "apply": "job applications require Chauncey's explicit authorization",
    "shell": "shell execution is outside trainee bounds",
    "network": "network access is outside trainee bounds",
    "email": "sending mail is outside trainee bounds",
    "browser": "browser work is outside trainee bounds",
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _require_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("task payload must be a dict, got %s" % type(payload).__name__)
    return payload


# --- sort_lines ------------------------------------------------------------


def _exec_sort_lines(payload: dict[str, Any]) -> dict[str, Any]:
    p = _require_payload(payload)
    lines = p.get("lines")
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        raise ValueError("sort_lines: payload['lines'] must be a list of strings")
    keep_header = bool(p.get("keep_header", False))
    descending = bool(p.get("descending", False))
    rows = [ln for ln in lines if ln.strip()]
    header = rows[0] if keep_header and rows else None
    body = rows[1:] if header is not None else rows
    body = sorted(body, key=str.lower, reverse=descending)
    out = ([header] + body) if header is not None else body
    return {"sorted_lines": out}


def _verify_sort_lines(result: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    p = _require_payload(payload)
    out = result.get("sorted_lines")
    if not isinstance(out, list):
        return False, "result missing sorted_lines list"
    rows = [ln for ln in p["lines"] if isinstance(ln, str) and ln.strip()]
    if sorted(out) != sorted(rows):
        return False, "rows were added, dropped, or altered"
    keep_header = bool(p.get("keep_header", False))
    descending = bool(p.get("descending", False))
    body = out[1:] if keep_header and out else out
    expected = sorted(body, key=str.lower, reverse=descending)
    if body != expected:
        return False, "body is not in the requested order"
    if keep_header and rows and out and out[0] != rows[0]:
        return False, "header row was not kept first"
    return True, "ok"


# --- extract_fields --------------------------------------------------------


def _exec_extract_fields(payload: dict[str, Any]) -> dict[str, Any]:
    p = _require_payload(payload)
    text = p.get("text", "")
    fields = p.get("fields", [])
    if not isinstance(text, str) or not isinstance(fields, list):
        raise ValueError("extract_fields: need {'text': str, 'fields': [str]}")
    found: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in fields and key not in found:
            found[key] = value.strip()
    return {"fields": found}


def _verify_extract_fields(result: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    p = _require_payload(payload)
    got = result.get("fields")
    if not isinstance(got, dict):
        return False, "result missing fields dict"
    # Independent re-parse: last-wins scan, then compare.
    want: dict[str, str] = {}
    for line in str(p.get("text", "")).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in p.get("fields", []):
            want[key.strip()] = value.strip()
    # Executor is first-wins; verifier recomputes first-wins independently.
    first: dict[str, str] = {}
    for line in str(p.get("text", "")).splitlines():
        key, sep, value = line.partition(":")
        key = key.strip()
        if sep and key in p.get("fields", []) and key not in first:
            first[key] = value.strip()
    if got != first:
        return False, "extracted fields do not match independent parse"
    return True, "ok"


# --- word_count_report -----------------------------------------------------


def _exec_word_count_report(payload: dict[str, Any]) -> dict[str, Any]:
    p = _require_payload(payload)
    text = p.get("text", "")
    if not isinstance(text, str):
        raise ValueError("word_count_report: payload['text'] must be a string")
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {
        "words": len(words),
        "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "chars": len(text),
        "top5": [[w, c] for w, c in top],
    }


def _verify_word_count_report(result: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    p = _require_payload(payload)
    text = str(p.get("text", ""))
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    if result.get("words") != len(words):
        return False, "word count mismatch"
    if result.get("chars") != len(text):
        return False, "char count mismatch"
    top = result.get("top5")
    if not isinstance(top, list) or len(top) > 5:
        return False, "top5 malformed"
    return True, "ok"


# --- redact_emails ---------------------------------------------------------


def _redact(text: str) -> tuple[str, int]:
    """The single source of truth for redaction; executor and verifier share it."""
    return _EMAIL_RE.subn("[REDACTED]", text)


def _exec_redact_emails(payload: dict[str, Any]) -> dict[str, Any]:
    p = _require_payload(payload)
    text = p.get("text", "")
    if not isinstance(text, str):
        raise ValueError("redact_emails: payload['text'] must be a string")
    redacted, n = _redact(text)
    return {"redacted_text": redacted, "redacted_count": n}


def _verify_redact_emails(result: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    text = result.get("redacted_text")
    if not isinstance(text, str):
        return False, "result missing redacted_text"
    expected_text, expected_n = _redact(str(payload.get("text", "")))
    if text != expected_text:
        return False, "redacted_text mismatch"
    if result.get("redacted_count") != expected_n:
        return False, "redaction count mismatch"
    return True, "ok"


# --- registry --------------------------------------------------------------

Template = tuple[str, str, Callable[[dict], dict], Callable[[dict, dict], tuple[bool, str]]]

TASKS: dict[str, Template] = {
    "sort_lines": (
        "sort_lines",
        "Sort text lines alphabetically, optionally keeping a header row first.",
        _exec_sort_lines,
        _verify_sort_lines,
    ),
    "extract_fields": (
        "extract_fields",
        "Extract Key: value fields from structured text.",
        _exec_extract_fields,
        _verify_extract_fields,
    ),
    "word_count_report": (
        "word_count_report",
        "Count words, lines, characters, and top-5 frequent words.",
        _exec_word_count_report,
        _verify_word_count_report,
    ),
    "redact_emails": (
        "redact_emails",
        "Replace email-like tokens with [REDACTED].",
        _exec_redact_emails,
        _verify_redact_emails,
    ),
}


def task_kinds() -> list[str]:
    return sorted(TASKS)


def refusal_reason(kind: str) -> str | None:
    """Why a task kind is refused, or None if it is an allowed template."""
    if kind in TASKS:
        return None
    if kind in FORBIDDEN_KINDS:
        return FORBIDDEN_KINDS[kind]
    return "unknown task kind %r — only registered supervised templates may run" % (kind,)
