"""LEVI job organ — run modes. Light / Low-Data / Offline.

Modes gate what the organ is allowed to do, so a cheap phone on a bad
connection (or no connection) still gets a useful, honest organ:

* LIGHT — read-only. Dashboard, lists, scoring review of what's already
  staged. No ingestion, no new drafts, no gates fired.
* LOW_DATA — local work only, minimal writes. Ingest from local files,
  triage, packet drafts. No external enrichment, no verbose logging.
* OFFLINE — hard no-network posture. Same as LOW_DATA plus: workbook
  and local-file imports only, and any action that would need the
  network is refused with a clear reason instead of failing halfway.

FULL (default) is the absence of a mode: everything the organ can do.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


class Mode(str, Enum):
    FULL = "full"
    LIGHT = "light"
    LOW_DATA = "low-data"
    OFFLINE = "offline"


def parse_mode(value: str | None) -> Mode:
    if not value:
        return Mode.FULL
    try:
        return Mode(str(value).lower())
    except ValueError:
        raise ValueError(
            f"unknown mode {value!r}; expected one of "
            + ", ".join(m.value for m in Mode)
        ) from None


def capabilities(mode: Mode) -> Dict[str, bool]:
    """What the organ may do under this mode."""
    if mode is Mode.LIGHT:
        return {
            "read": True,
            "ingest": False,
            "triage": True,  # scoring review of staged rows only
            "draft": False,
            "gates": False,
            "enrich_external": False,
            "write": False,
        }
    if mode in (Mode.LOW_DATA, Mode.OFFLINE):
        return {
            "read": True,
            "ingest": True,  # local files / workbook only
            "triage": True,
            "draft": True,
            "gates": True,
            "enrich_external": False,
            "write": True,
        }
    return {
        "read": True,
        "ingest": True,
        "triage": True,
        "draft": True,
        "gates": True,
        "enrich_external": True,
        "write": True,
    }


def require(mode: Mode, capability: str) -> None:
    """Raise if the mode forbids this capability. Fail closed, say why."""
    if not capabilities(mode).get(capability, False):
        raise PermissionError(
            f"mode {mode.value!r} forbids {capability!r}; "
            "re-run with --mode full (or low-data/offline where allowed)"
        )


def describe(mode: Mode) -> str:
    return {
        Mode.FULL: "full power: everything the organ can do",
        Mode.LIGHT: "light: read-only dashboard and review, no writes",
        Mode.LOW_DATA: "low-data: local work only, no external enrichment",
        Mode.OFFLINE: "offline: hard no-network posture, local files only",
    }[mode]
