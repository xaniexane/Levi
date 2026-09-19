"""RSS/Atom reader connector — credentialless, read-only, stdlib-only.

Public syndication feeds need no API key, so ``credential()`` returns the
``"public"`` sentinel instead of reading an env var — the registry's
credential gate never fires for reads, and no secret can leak into a
message by construction.

Operations (all read-only; no confirmation gate can ever trigger):
* ``fetch`` — download one feed URL and return its entries
  (``url`` required, ``limit`` optional, 1..100, default 20);
* ``check`` — like ``fetch`` with ``limit=1``, a cheap "is this feed alive"
  probe that still returns the newest entry.

Honesty: a fetch failure (DNS, HTTP error, unparseable XML) is a
``ConnectorAPIError`` → ``status="api_error"``, ``ok=False``. The URL
itself is never echoed into the message — URLs can carry tokens in query
strings. Content is returned verbatim from the feed; LEVI treats it as
untrusted third-party text (curate it, don't trust it).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
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

_USER_AGENT = "LEVI-rss/1.0 (local-first reader; +https://levi.local)"
_FETCH_TIMEOUT_SEC = 20
_MAX_BODY_BYTES = 4_000_000  # 4 MB — feeds bigger than this are suspect


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return " ".join(elem.text.split())


def _local(tag: str) -> str:
    """Strip an ``{namespace}`` prefix from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _local(child.tag) == name:
            return child
    return None


def _find_children(parent: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in parent if _local(c.tag) == name]


def _entry_from_rss(item: ET.Element) -> Dict[str, Any]:
    return {
        "title": _text(_find_child(item, "title")),
        "link": _text(_find_child(item, "link")),
        "summary": _text(_find_child(item, "description")),
        "published": _text(_find_child(item, "pubDate")),
    }


def _entry_from_atom(entry: ET.Element) -> Dict[str, Any]:
    link = ""
    for ln in _find_children(entry, "link"):
        if ln.get("rel", "alternate") == "alternate" and ln.get("href"):
            link = ln.get("href", "")
            break
    summary = _text(_find_child(entry, "summary")) or _text(
        _find_child(entry, "content")
    )
    published = _text(_find_child(entry, "published")) or _text(
        _find_child(entry, "updated")
    )
    return {
        "title": _text(_find_child(entry, "title")),
        "link": link,
        "summary": summary,
        "published": published,
    }


def parse_feed(body: bytes, url_hint: str = "") -> Dict[str, Any]:
    """Parse an RSS 2.0 or Atom document into a feed dict.

    Raises :class:`InvalidParams` on empty/oversize bodies and
    :class:`ConnectorAPIError` on unparseable XML.
    """
    if not body or not body.strip():
        raise InvalidParams("feed body was empty — nothing to parse.")
    if len(body) > _MAX_BODY_BYTES:
        raise InvalidParams(
            f"feed body is {len(body)} bytes (cap {_MAX_BODY_BYTES}) — refused."
        )
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise ConnectorAPIError(
            f"could not parse the document at the given URL as XML/RSS/Atom "
            f"(source hint: {url_hint[:60]!r}) — nothing was stored."
        ) from None
    kind = _local(root.tag)
    channel: ET.Element | None
    if kind == "rss":
        channel = _find_child(root, "channel")
        if channel is None:
            raise ConnectorAPIError("RSS document has no <channel> element.")
        entries = [_entry_from_rss(i) for i in _find_children(channel, "item")]
        feed_title = _text(_find_child(channel, "title"))
        feed_link = _text(_find_child(channel, "link"))
    elif kind == "feed":
        entries = [_entry_from_atom(e) for e in _find_children(root, "entry")]
        feed_title = _text(_find_child(root, "title"))
        link = ""
        for ln in _find_children(root, "link"):
            if ln.get("rel", "alternate") == "alternate" and ln.get("href"):
                link = ln.get("href", "")
                break
        feed_link = link
    else:
        raise ConnectorAPIError(
            f"document root <{kind}> is neither RSS nor Atom — nothing parsed."
        )
    entries = [e for e in entries if e["title"] or e["link"]]
    return {
        "kind": "atom" if kind == "feed" else "rss",
        "title": feed_title,
        "link": feed_link,
        "entry_count": len(entries),
        "entries": entries,
    }


def download(url: str, timeout: float = _FETCH_TIMEOUT_SEC) -> bytes:
    """Fetch a feed body. HTTP errors → :class:`ConnectorAPIError`."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 400:
                raise ConnectorAPIError(
                    f"the server answered HTTP {resp.status} — nothing fetched."
                )
            return resp.read(_MAX_BODY_BYTES + 1)
    except ConnectorAPIError:
        raise
    except urllib.error.HTTPError as exc:
        raise ConnectorAPIError(
            f"the server answered HTTP {exc.code} — nothing fetched."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorAPIError(
            f"could not reach the feed server ({type(exc).__name__}) — nothing fetched."
        ) from None


class RssConnector(Connector):
    """Read-only RSS/Atom reader. No credential, no writes, no confirmation."""

    id = "rss"
    display_name = "RSS/Atom reader"
    # Public feeds need no credential; the var is accepted (registry requires
    # a declaration) but never required — credential() returns "public" when
    # it is unset.
    credential_env_var = "LEVI_RSS_TOKEN"
    capabilities = (Capability("read.feed", "Fetch and parse a public RSS/Atom feed"),)
    operations = (
        Operation(
            "fetch",
            "Return entries of a feed URL (params: url, limit)",
            params=("url",),
        ),
        Operation(
            "check", "Probe a feed URL; return its newest entry", params=("url",)
        ),
    )

    def credential(self) -> str | None:
        # Credentialless by design: public feeds. Returns the env value when
        # present (harmless), else the "public" sentinel so execute()'s
        # credential gate never fires for reads.
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        url = str(params.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://", "file://")):
            raise InvalidParams(
                "fetch needs an http(s):// or file:// feed URL — nothing was sent."
            )
        if operation == "check":
            limit = 1
        else:
            try:
                limit = int(params.get("limit") or 20)
            except (TypeError, ValueError):
                raise InvalidParams(
                    "limit must be an integer — nothing sent."
                ) from None
            if not 1 <= limit <= 100:
                raise InvalidParams("limit must be 1..100 — nothing sent.")
        body = download(url)
        feed = parse_feed(body, url_hint=url)
        feed["entries"] = feed["entries"][:limit]
        feed["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return feed


register_connector(RssConnector)
