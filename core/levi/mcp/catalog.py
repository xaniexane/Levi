"""Curated MCP server catalog — one-command installs of popular servers.

The catalog is DATA, not code: a tuple of plain dicts at the bottom of
this module, so extending it is a matter of appending one dict. Every
entry is validated on load by :func:`load_catalog`.

Binding identity rule (Chauncey, 2026-09-15): every catalog entry is a
**third-party reference**, never a source and never LEVI. Each entry
carries an explicit ``"reference": True`` label plus the ``provider``
name behind the server; ``levi mcp add --catalog`` records that provider
in the universal reference registry (``levi.plugins.references``) and
every display path labels it as a reference.

Free-core rule: the default catalog contains NO servers that require a
paid API key. Entries that offer extra features behind an optional key
say so in their ``note`` and install fine without one.

Entry shape (all keys are plain JSON-style values)::

    {
        "name": "context7",                       # unique; [A-Za-z0-9_-]{1,64}
        "description": "Up-to-date library docs…",# one line, no secrets
        "transport": "stdio",                     # "stdio" | "http"
        "command": ["npx", "-y", "@upstash/context7-mcp"],  # stdio only
        # "url": "https://…",                    # http only (alternative)
        "provider": "Context7",                   # external provider name
        "reference": True,                        # explicit third-party label
        "tags": ["docs"],                         # optional
        "note": "…",                              # optional, e.g. optional-key note
    }

stdlib-only.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_REQUIRED_KEYS = ("name", "description", "transport", "provider", "reference")
_OPTIONAL_KEYS = ("command", "url", "tags", "note")
_TRANSPORTS = ("stdio", "http")


class CatalogError(Exception):
    """A catalog entry was malformed, duplicated, or unknown."""


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise CatalogError(msg)


def _validate_entry(entry: Any, index: int) -> dict:
    what = f"catalog entry #{index}"
    _check(
        isinstance(entry, dict), f"{what}: must be a dict, got {type(entry).__name__}"
    )
    keys = set(entry)
    missing = [k for k in _REQUIRED_KEYS if k not in keys]
    _check(not missing, f"{what}: missing required keys: {missing}")
    unknown = sorted(keys - set(_REQUIRED_KEYS) - set(_OPTIONAL_KEYS))
    _check(
        not unknown,
        f"{what}: unknown keys {unknown} "
        f"(allowed: {sorted(set(_REQUIRED_KEYS) | set(_OPTIONAL_KEYS))})",
    )

    name = entry["name"]
    _check(
        isinstance(name, str) and _NAME_RE.match(name),
        f"{what}: invalid name {name!r}: use 1-64 chars of [A-Za-z0-9_-]",
    )

    desc = entry["description"]
    _check(
        isinstance(desc, str) and desc.strip() and "\n" not in desc.strip(),
        f"{what} ({name}): description must be a non-empty single line",
    )

    transport = entry["transport"]
    _check(
        transport in _TRANSPORTS,
        f"{what} ({name}): transport must be one of {_TRANSPORTS}, got {transport!r}",
    )
    if transport == "stdio":
        _check("command" in entry, f"{what} ({name}): stdio needs a 'command' list")
        _check("url" not in entry, f"{what} ({name}): stdio must not have a 'url'")
        command = entry["command"]
        _check(
            isinstance(command, (list, tuple))
            and not isinstance(command, str)
            and len(command) > 0
            and all(isinstance(c, str) and c.strip() for c in command),
            f"{what} ({name}): command must be a non-empty list of non-empty strings",
        )
    else:  # http
        _check("url" in entry, f"{what} ({name}): http needs a 'url'")
        _check("command" not in entry, f"{what} ({name}): http must not have 'command'")
        url = entry["url"]
        parsed = urllib.parse.urlparse(url) if isinstance(url, str) else None
        _check(
            parsed is not None
            and parsed.scheme in ("http", "https")
            and bool(parsed.netloc),
            f"{what} ({name}): url must look like http(s)://host[:port][/path], "
            f"got {url!r}",
        )

    # The explicit third-party label: must be present and exactly True.
    _check(
        entry["reference"] is True,
        f"{what} ({name}): 'reference' must be exactly True — "
        "catalog entries are third-party references, never LEVI",
    )

    provider = entry["provider"]
    _check(
        isinstance(provider, str) and provider.strip() and len(provider) <= 120,
        f"{what} ({name}): provider must be a non-empty name (≤120 chars)",
    )
    from levi.plugins import references as _refs

    try:
        _refs.assert_not_levi_identity(provider, what="catalog provider")
    except _refs.ReferenceError as exc:
        raise CatalogError(f"{what} ({name}): {exc}") from None

    tags = entry.get("tags", [])
    _check(
        isinstance(tags, list) and all(isinstance(t, str) and t.strip() for t in tags),
        f"{what} ({name}): tags must be a list of non-empty strings",
    )
    note = entry.get("note", "")
    _check(
        isinstance(note, str),
        f"{what} ({name}): note must be a string, got {type(note).__name__}",
    )
    return dict(entry)


def load_catalog() -> list[dict]:
    """Return the validated catalog as a list of entry dicts.

    Raises :class:`CatalogError` when any entry is malformed or a name is
    duplicated. Entries are returned in catalog order.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for i, raw in enumerate(CATALOG):
        entry = _validate_entry(raw, i)
        if entry["name"] in seen:
            raise CatalogError(f"duplicate catalog entry name {entry['name']!r}")
        seen.add(entry["name"])
        out.append(entry)
    return out


def catalog_names() -> list[str]:
    """Return the catalog entry names in catalog order."""
    return [e["name"] for e in load_catalog()]


def get_entry(name: str) -> dict:
    """Return the validated catalog entry for ``name``.

    Raises :class:`CatalogError` with the available names when unknown.
    """
    key = (name or "").strip()
    for entry in load_catalog():
        if entry["name"] == key:
            return entry
    raise CatalogError(
        f"unknown catalog entry {name!r}. Available: {', '.join(catalog_names())}"
    )


def install_spec(entry: dict) -> dict:
    """Build ``client.add_server`` kwargs from a validated catalog entry.

    Returns ``{"transport", "command"|"url", "reference"}`` — the provider
    goes in as the reference label, never as LEVI identity.
    """
    spec: dict[str, Any] = {
        "transport": entry["transport"],
        "reference": entry["provider"],
    }
    if entry["transport"] == "stdio":
        spec["command"] = list(entry["command"])
    else:
        spec["url"] = entry["url"]
    return spec


def describe_target(entry: dict) -> str:
    """Human-readable transport target, e.g. ``npx -y pkg`` or the URL."""
    if entry["transport"] == "stdio":
        return " ".join(entry["command"])
    return str(entry["url"])


# ---------------------------------------------------------------------------
# The catalog — DATA, not code. Append a dict to add a server.
# ---------------------------------------------------------------------------

CATALOG: tuple[dict, ...] = (
    {
        "name": "context7",
        "description": "Up-to-date documentation for any library or framework.",
        "transport": "stdio",
        "command": ["npx", "-y", "@upstash/context7-mcp"],
        "provider": "Context7",
        "reference": True,
        "tags": ["docs", "research"],
    },
    {
        "name": "fetch",
        "description": "Fetch a web page and convert it to LLM-friendly markdown.",
        "transport": "stdio",
        "command": ["uvx", "mcp-server-fetch"],
        "provider": "Model Context Protocol",
        "reference": True,
        "tags": ["web", "research"],
    },
    {
        "name": "sequential-thinking",
        "description": "Structured step-by-step reasoning traces for hard problems.",
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
        "provider": "Model Context Protocol",
        "reference": True,
        "tags": ["reasoning"],
    },
    {
        "name": "jina-ai-reader",
        "description": "Read any URL as clean markdown via the Jina AI reader.",
        "transport": "stdio",
        "command": ["npx", "-y", "jina-mcp-tools"],
        "provider": "Jina AI",
        "reference": True,
        "tags": ["web", "research"],
        "note": (
            "Reader works with no key. An optional free Jina AI API key "
            "unlocks the web-search tools (not required, not in the catalog)."
        ),
    },
    {
        "name": "open-meteo",
        "description": "Current weather and forecasts from the free Open-Meteo API.",
        "transport": "stdio",
        "command": ["npx", "-y", "open-meteo-mcp-lite"],
        "provider": "Open-Meteo",
        "reference": True,
        "tags": ["weather", "data"],
        "note": "No API key required.",
    },
    {
        "name": "coingecko",
        "description": "Crypto prices, market caps, trends, and history (free tier).",
        "transport": "stdio",
        "command": ["npx", "-y", "coingecko-mcp-server"],
        "provider": "CoinGecko",
        "reference": True,
        "tags": ["crypto", "data"],
        "note": "No API key required (CoinGecko free tier, rate-limited).",
    },
    {
        "name": "deepwiki",
        "description": "Fetch deepwiki.com pages for any GitHub repo as markdown.",
        "transport": "stdio",
        "command": ["npx", "-y", "mcp-deepwiki"],
        "provider": "DeepWiki",
        "reference": True,
        "tags": ["docs", "research", "github"],
    },
)
