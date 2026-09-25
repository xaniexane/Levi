"""Hacker News reader connector — credentialless, read-only, stdlib-only.

The official Hacker News API (Firebase, keyless) is recorded as a
*reference* (provider name, never LEVI identity). No credential exists
for it by design; ``credential()`` returns the ``"public"`` sentinel so
the registry's credential gate never fires for reads.

Operations (all read-only; no confirmation gate can ever trigger):
* ``top`` — current top story ids (``limit`` optional, 1..50, default 10);
* ``new`` — newest story ids (``limit`` optional, 1..50, default 10);
* ``item`` — one item by id (``id`` required, positive int): story or
  comment with title/url/score/author/time/descendants.

Honesty: a fetch failure (DNS, HTTP error, unparseable JSON) is a
``ConnectorAPIError`` → ``status="api_error"``, ``ok=False``. Limits
and ids are validated before anything is sent; bad input is
``invalid_params``, never a guessed request.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .registry import (
    Capability,
    Connector,
    ConnectorAPIError,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_API_BASE = "https://hacker-news.firebaseio.com/v0"
_USER_AGENT = "LEVI-hn/1.0 (local-first reader; +https://levi.local)"
_FETCH_TIMEOUT_SEC = 20
_MAX_BODY_BYTES = 2_000_000  # 2 MB — story id lists are tiny


def _limit(params: dict[str, Any]) -> int:
    raw = params.get("limit", 10)
    if raw is None:
        raw = 10
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        raise InvalidParams("limit must be an integer — nothing was sent.") from None
    if not 1 <= limit <= 50:
        raise InvalidParams("limit must be 1..50 — nothing was sent.")
    return limit


def _item_id(params: dict[str, Any]) -> int:
    try:
        item_id = int(params.get("id"))
    except (TypeError, ValueError):
        raise InvalidParams("id must be an integer — nothing was sent.") from None
    if item_id <= 0:
        raise InvalidParams("id must be a positive integer — nothing was sent.")
    return item_id


def _download_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SEC) as resp:
            body = resp.read(_MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ConnectorAPIError(
            f"the Hacker News server answered HTTP {exc.code} — nothing fetched."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorAPIError(
            f"could not reach the Hacker News server ({type(exc).__name__}) — "
            "nothing fetched."
        ) from None
    if len(body) > _MAX_BODY_BYTES:
        raise ConnectorAPIError("Hacker News response too large — nothing parsed.")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ConnectorAPIError(
            "Hacker News response was not parseable JSON — nothing returned."
        ) from exc


def _story_ids(feed: str, limit: int) -> List[int]:
    payload = _download_json(f"{_API_BASE}/{feed}.json")
    if not isinstance(payload, list) or not all(isinstance(i, int) for i in payload):
        raise ConnectorAPIError(
            f"Hacker News {feed} feed had an unexpected shape — nothing returned."
        )
    return payload[:limit]


def _normalize_item(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict) or "id" not in payload:
        raise ConnectorAPIError(
            "Hacker News item had an unexpected shape — nothing returned."
        )
    ts = payload.get("time")
    return {
        "id": payload.get("id"),
        "type": payload.get("type"),
        "title": payload.get("title"),
        "url": payload.get("url"),
        "text": payload.get("text"),
        "score": payload.get("score"),
        "by": payload.get("by"),
        "time": payload.get("time"),
        "time_iso": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
            if isinstance(ts, (int, float))
            else None
        ),
        "descendants": payload.get("descendants"),
        "kids": payload.get("kids") or [],
    }


class HackerNewsConnector(Connector):
    """Read-only Hacker News reader. No credential, no writes, no confirmation."""

    id = "hn"
    display_name = "Hacker News reader"
    # Keyless public API; the var is accepted but never required —
    # credential() returns "public" when it is unset.
    credential_env_var = "LEVI_HN_TOKEN"
    capabilities = (
        Capability("read.hn.top", "Top story ids from Hacker News"),
        Capability("read.hn.new", "Newest story ids from Hacker News"),
        Capability("read.hn.item", "One Hacker News item (story or comment)"),
    )
    operations = (
        Operation(
            "top",
            "Top story ids (params: limit=10)",
            params=("limit",),
        ),
        Operation(
            "new",
            "Newest story ids (params: limit=10)",
            params=("limit",),
        ),
        Operation(
            "item",
            "One item by id (params: id)",
            params=("id",),
        ),
    )
    references = ("hacker-news",)

    def credential(self) -> str | None:
        # Credentialless by design: keyless public API. Returns the env value
        # when present (harmless), else the "public" sentinel so execute()'s
        # credential gate never fires for reads.
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if operation == "top":
            return {
                "feed": "top",
                "ids": _story_ids("topstories", _limit(params)),
                "fetched_at": fetched_at,
            }
        if operation == "new":
            return {
                "feed": "new",
                "ids": _story_ids("newstories", _limit(params)),
                "fetched_at": fetched_at,
            }
        payload = _download_json(f"{_API_BASE}/item/{_item_id(params)}.json")
        item = _normalize_item(payload)
        item["fetched_at"] = fetched_at
        return item


register_connector(HackerNewsConnector)
