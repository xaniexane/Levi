"""arXiv paper search connector — credentialless, read-only, stdlib-only.

The arXiv export API is keyless and public; arXiv is recorded as a
*reference* (provider name, never LEVI identity). No credential exists
for it by design; ``credential()`` returns the ``"public"`` sentinel so
the registry's credential gate never fires for reads.

Operations (all read-only; no confirmation gate can ever trigger):
* ``search`` — paper search (``query`` required, 1..300 chars;
  ``max_results`` optional, 1..50, default 10; ``sort`` in
  submitted/relevance/lastUpdatedDate, default relevance; ``order`` in
  descending/ascending, default descending);
* ``lookup`` — one paper by arXiv id (``arxiv_id`` required, e.g.
  ``"2401.12345"`` or ``"hep-th/9901001"``).

Politeness: arXiv asks clients to space requests ~3 s apart. ``perform()``
enforces that between real calls (skipped when a fake ``_download`` is in
place, so tests never sleep).

Honesty: a fetch failure (DNS, HTTP error, unparseable Atom) is a
``ConnectorAPIError`` → ``status="api_error"``, ``ok=False``. Params are
validated before anything is sent; bad input is ``invalid_params``,
never a guessed request. Stdlib-only (urllib + xml.etree).
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
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

_API_BASE = "https://export.arxiv.org/api/query"
_USER_AGENT = "LEVI-arxiv/1.0 (local-first reader; +https://levi.local)"
_FETCH_TIMEOUT_SEC = 30
_MAX_BODY_BYTES = 5_000_000  # 5 MB — search pages are small
_THROTTLE_SEC = 3.0  # arXiv asks clients to space requests ~3 s apart

_LAST_CALL_AT: float = 0.0

_ARXIV_ID_RE = re.compile(r"^[a-z\-]+/\d{7}$|^\d{4}\.\d{4,5}(v\d+)?$", re.IGNORECASE)
_SORTS = ("submitted", "relevance", "lastUpdatedDate")
_ORDERS = ("descending", "ascending")
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def _polite_wait() -> None:
    """Space real arXiv calls ~3 s apart. Tests monkeypatch ``_download``,
    so this never sleeps under test."""
    global _LAST_CALL_AT
    now = time.monotonic()
    gap = now - _LAST_CALL_AT
    if _LAST_CALL_AT and gap < _THROTTLE_SEC:
        time.sleep(_THROTTLE_SEC - gap)
    _LAST_CALL_AT = time.monotonic()


def _validate_search(params: dict[str, Any]) -> tuple[str, int, str, str]:
    query = str(params.get("query") or "").strip()
    if not query or len(query) > 300:
        raise InvalidParams(
            "query is required and must be 1-300 characters — nothing was sent."
        )
    raw_max = params.get("max_results", 10)
    if raw_max is None:
        raw_max = 10
    try:
        max_results = int(raw_max)
    except (TypeError, ValueError):
        raise InvalidParams(
            "max_results must be an integer — nothing was sent."
        ) from None
    if not 1 <= max_results <= 50:
        raise InvalidParams("max_results must be 1..50 — nothing was sent.")
    sort = str(params.get("sort") or "relevance")
    if sort not in _SORTS:
        raise InvalidParams(
            f"sort must be one of {', '.join(_SORTS)} — nothing was sent."
        )
    order = str(params.get("order") or "descending")
    if order not in _ORDERS:
        raise InvalidParams(
            f"order must be one of {', '.join(_ORDERS)} — nothing was sent."
        )
    return query, max_results, sort, order


def _validate_lookup(params: dict[str, Any]) -> str:
    arxiv_id = str(params.get("arxiv_id") or "").strip()
    if not _ARXIV_ID_RE.match(arxiv_id):
        raise InvalidParams(
            f"arxiv_id {arxiv_id!r} is not an arXiv id "
            '(e.g. "2401.12345") — nothing was sent.'
        )
    return arxiv_id


def _download(url: str) -> bytes:
    _polite_wait()
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SEC) as resp:
            body = resp.read(_MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ConnectorAPIError(
            f"the arXiv server answered HTTP {exc.code} — nothing fetched."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorAPIError(
            f"could not reach the arXiv server ({type(exc).__name__}) — "
            "nothing fetched."
        ) from None
    if len(body) > _MAX_BODY_BYTES:
        raise ConnectorAPIError("arXiv response too large — nothing parsed.")
    return body


def _text(entry: ET.Element, path: str) -> str | None:
    node = entry.find(path, _ATOM_NS)
    if node is None or node.text is None:
        return None
    text = " ".join(node.text.split())
    return text or None


def _parse_feed(body: bytes) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ConnectorAPIError(
            "arXiv response was not parseable Atom — nothing returned."
        ) from exc
    papers: List[Dict[str, Any]] = []
    for entry in root.findall("a:entry", _ATOM_NS):
        authors = [_text(a, "a:name") for a in entry.findall("a:author", _ATOM_NS)]
        papers.append(
            {
                "id": _text(entry, "a:id"),
                "title": _text(entry, "a:title"),
                "authors": [a for a in authors if a],
                "summary": _text(entry, "a:summary"),
                "published": _text(entry, "a:published"),
                "updated": _text(entry, "a:updated"),
                "categories": [
                    c.get("term")
                    for c in entry.findall("a:category", _ATOM_NS)
                    if c.get("term")
                ],
            }
        )
    return papers


class ArxivConnector(Connector):
    """Read-only arXiv search. No credential, no writes, no confirmation."""

    id = "arxiv"
    display_name = "arXiv paper search"
    # Keyless public API; the var is accepted but never required —
    # credential() returns "public" when it is unset.
    credential_env_var = "LEVI_ARXIV_TOKEN"
    capabilities = (
        Capability("read.arxiv.search", "Search arXiv papers by query"),
        Capability("read.arxiv.lookup", "Fetch one arXiv paper by id"),
    )
    operations = (
        Operation(
            "search",
            "Search papers (params: query, max_results=10, sort, order)",
            params=("query", "max_results", "sort", "order"),
        ),
        Operation(
            "lookup",
            "One paper by arXiv id (params: arxiv_id)",
            params=("arxiv_id",),
        ),
    )
    references = ("arxiv",)

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
        if operation == "search":
            query, max_results, sort, order = _validate_search(params)
            url = (
                _API_BASE
                + "?"
                + urllib.parse.urlencode(
                    {
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": max_results,
                        "sortBy": sort,
                        "sortOrder": order,
                    }
                )
            )
            papers = _parse_feed(_download(url))
            return {
                "query": query,
                "count": len(papers),
                "papers": papers,
                "fetched_at": fetched_at,
            }
        arxiv_id = _validate_lookup(params)
        url = _API_BASE + "?" + urllib.parse.urlencode({"id_list": arxiv_id})
        papers = _parse_feed(_download(url))
        if not papers:
            raise ConnectorAPIError(
                f"arXiv returned no paper for id {arxiv_id!r} — nothing returned."
            )
        paper = papers[0]
        paper["fetched_at"] = fetched_at
        return paper


register_connector(ArxivConnector)
