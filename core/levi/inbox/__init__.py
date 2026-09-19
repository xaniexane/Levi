"""Inbox — the companion's user-facing telemetry and request box.

Two parts, both local-first and user-owned:

* **analytics** (``levi.inbox.analytics``): usage analytics — which
  capabilities get used, when, how often. Aggregate views only
  (daily/weekly, per-capability counts). Nothing leaves the machine;
  no external telemetry, ever. This is the user reading their own
  patterns, not surveillance.
* **requests** (``levi.inbox.requests``): the feature/request box the
  user can drop into anytime from the companion chat box.

Storage lives under ``~/.levi/inbox/`` (override with
``LEVI_INBOX_DIR``), owner-only (``0o700`` dir, ``0o600`` files).

Stdlib only.
"""

from __future__ import annotations

from levi.inbox.analytics import Analytics, record
from levi.inbox.requests import Request, RequestBox, STATUSES

__all__ = ["Analytics", "record", "Request", "RequestBox", "STATUSES"]
