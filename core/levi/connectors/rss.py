"""RSS/Atom sense connector — LEVI's ear on syndicated feeds.

``poll(url=..., state={}, max_items=25, timeout=15)`` fetches one feed and
emits one event per *new* item::

    {"kind": "item", "id": ..., "title": ..., "link": ...,
     "published": ..., "summary": ...}

Both RSS 2.0 (``channel/item``) and Atom (``feed/entry``) are understood,
parsed with stdlib ``xml.etree`` only — no feedparser, no requests, no
paid APIs. Fits the DemandPulse sense path: syndicated signal sources
polled on a schedule, turned into plain events, never published back.

Laws
----
- observe-only: performs a single HTTP GET; never posts, subscribes,
  pings back, or writes anywhere outside the read.
- honest baseline: the first poll (empty state) emits one ``baseline``
  event naming the feed title and item count, and banks every item as
  seen. A watched feed is never assumed, and nothing is emitted twice.
- edge-only: a feed with no new items emits nothing; each new item
  emits exactly one ``item`` event, newest-first ordering preserved.
- identity is stable: ``guid`` (RSS) / ``id`` (Atom), falling back to
  ``link``, then ``title``. The same item under two titles still
  dedupes.

Deny-closed paths
-----------------
- ``url`` must be a string with an ``http`` or ``https`` scheme —
  ``file:``, ``ftp:``, and scheme-relative URLs are refused.
- ``1 <= max_items <= 100``, ``1 <= timeout <= 120``; otherwise refused.
- ``state`` must be a dict; a ``seen`` key, when present, must be a
  list of strings — anything else is refused, never guessed.
- HTTP errors, timeouts, empty bodies, and malformed XML are all
  refused as ``ConnectorError``: a poll never half-runs.

Interop note
------------
Builtins self-register on ``levi.connectors`` import; this module
registers itself on its own import so it stays usable without touching
the shared package ``__init__``::

    from levi.connectors import rss  # noqa: F401 — registers "rss"
    from levi.connectors import registry
    events, state = registry.poll("rss", url="https://example/feed.xml",
                                  state={})

``MANIFEST_ENTRY`` documents the interop-manifest merge for the
``integrations`` capability block; merging it is mechanical.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_CONNECTOR_ID = "rss"
_MAX_SEEN = 500
_SUMMARY_CHARS = 240
_USER_AGENT = "LEVI-rss/1.0 (+local-first sense connector; stdlib-only)"

MANIFEST_ENTRY = {
    "connectors-rss": {
        "provides": ["connectors.rss.poll"],
        "requires": [],
        "description": "RSS/Atom sense connector — stdlib feed polling",
    }
}


def _text(element: Optional[ET.Element]) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def _child_text(parent: ET.Element, *names: str) -> str:
    for name in names:
        found = parent.find(name)
        text = _text(found)
        if text:
            return text
    return ""


def _child_inner_text(parent: ET.Element, *names: str) -> str:
    """Inner text of a child, including text nested in child elements."""
    for name in names:
        found = parent.find(name)
        if found is not None:
            text = " ".join("".join(found.itertext()).split())
            if text:
                return text
    return ""


def _strip_markup(raw: str) -> str:
    """Collapse embedded HTML to plain text without a parser."""
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(no_tags.split())[:_SUMMARY_CHARS]


def _atom_ns(tag: str) -> str:
    return f"{{http://www.w3.org/2005/Atom}}{tag}"


def _parse_rss(root: ET.Element) -> Tuple[str, List[Dict[str, str]]]:
    channel = root.find("channel")
    if channel is None:
        raise ConnectorError("rss: RSS document has no channel element")
    title = _child_text(channel, "title")
    items: List[Dict[str, str]] = []
    for item in channel.findall("item"):
        guid = _child_text(item, "guid")
        link = _child_text(item, "link")
        title_text = _child_text(item, "title")
        identity = guid or link or title_text
        if not identity:
            continue
        items.append(
            {
                "id": identity,
                "title": title_text,
                "link": link,
                "published": _child_text(item, "pubDate", "dc:date"),
                "summary": _strip_markup(_child_inner_text(item, "description")),
            }
        )
    return title, items


def _parse_atom(root: ET.Element) -> Tuple[str, List[Dict[str, str]]]:
    title = _text(root.find(_atom_ns("title")))
    items: List[Dict[str, str]] = []
    for entry in root.findall(_atom_ns("entry")):
        entry_id = _text(entry.find(_atom_ns("id")))
        link_el = entry.find(_atom_ns("link"))
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or "").strip()
        title_text = _text(entry.find(_atom_ns("title")))
        identity = entry_id or link or title_text
        if not identity:
            continue
        summary = _strip_markup(
            _child_inner_text(entry, _atom_ns("summary"), _atom_ns("content"))
        )
        items.append(
            {
                "id": identity,
                "title": title_text,
                "link": link,
                "published": _text(entry.find(_atom_ns("updated")))
                or _text(entry.find(_atom_ns("published"))),
                "summary": summary,
            }
        )
    return title, items


def _parse_feed(body: bytes) -> Tuple[str, List[Dict[str, str]]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ConnectorError(f"rss: malformed XML: {exc}") from exc
    tag = root.tag
    if tag == "rss":
        return _parse_rss(root)
    if tag == _atom_ns("feed") or tag == "feed":
        return _parse_atom(root)
    raise ConnectorError(f"rss: unsupported feed root <{tag}>")


def _guard_url(url: Any) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ConnectorError("rss: 'url' must be a non-empty string")
    scheme = urllib.parse.urlsplit(url.strip()).scheme.lower()
    if scheme not in ("http", "https"):
        raise ConnectorError("rss: 'url' must be http(s); refused: " + scheme)
    return url.strip()


def _guard_int(name: str, value: Any, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConnectorError(f"rss: '{name}' must be a number")
    number = int(value)
    if not low <= number <= high:
        raise ConnectorError(f"rss: '{name}' must be {low}..{high}")
    return number


def _guard_state(state: Any) -> List[str]:
    if not isinstance(state, dict):
        raise ConnectorError("rss: 'state' must be a dict")
    seen = state.get("seen", [])
    if not isinstance(seen, list) or any(not isinstance(item, str) for item in seen):
        raise ConnectorError("rss: state['seen'] must be a list of strings")
    return seen


def _fetch(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise ConnectorError(f"rss: HTTP {status} for {url}")
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ConnectorError(f"rss: HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise ConnectorError(f"rss: fetch failed for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ConnectorError(f"rss: fetch timed out for {url}") from exc


def poll(
    url: Any,
    state: Any = None,
    max_items: Any = 25,
    timeout: Any = 15,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll one feed; returns (events, new_state)."""
    clean_url = _guard_url(url)
    seen = _guard_state({} if state is None else state)
    limit = _guard_int("max_items", max_items, 1, 100)
    seconds = _guard_int("timeout", timeout, 1, 120)

    body = _fetch(clean_url, seconds)
    if not body.strip():
        raise ConnectorError("rss: empty response body")
    feed_title, items = _parse_feed(body)

    seen_set = set(seen)
    events: List[Dict[str, Any]] = []
    new_ids: List[str] = []
    for item in items[:limit]:
        if item["id"] in seen_set:
            continue
        seen_set.add(item["id"])
        new_ids.append(item["id"])
        events.append({"kind": "item", **item})

    baseline = not seen
    if baseline:
        events = [
            {
                "kind": "baseline",
                "title": feed_title,
                "item_count": len(items),
                "url": clean_url,
            }
        ]
    new_state = {"seen": ([*new_ids, *seen])[:_MAX_SEEN]}
    return events, new_state


registry.register(
    Connector(
        id=_CONNECTOR_ID,
        name="RSS/Atom sense",
        description=(
            "Polls one RSS 2.0 or Atom feed (stdlib XML only) and emits "
            "one event per new item. Observe-only."
        ),
        inputs=("url", "state", "max_items", "timeout"),
        poll=poll,
    )
)
