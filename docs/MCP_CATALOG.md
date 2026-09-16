# MCP Server Catalog

`levi mcp catalog` lists a curated set of popular MCP servers you can
install with a single command:

```bash
levi mcp catalog                 # browse the catalog
levi mcp add --catalog context7  # one-command install
levi mcp add --catalog fetch my-fetcher   # optional: your own local name
```

## What the catalog is

The catalog (`core/levi/mcp/catalog.py`) is **data, not code**: a tuple of
plain dicts describing well-known, free MCP servers — library docs
(Context7), URL→markdown (fetch, Jina AI reader), step-by-step reasoning
(sequential-thinking), weather (Open-Meteo), crypto market data
(CoinGecko), GitHub repo docs (DeepWiki). Installing one writes a normal
server config to `~/.levi/mcp/servers.json` and verifies the server
answers, exactly like a manual `levi mcp add --cmd …`.

## Third-party references, not LEVI

Binding identity rule: every catalog entry is a **third-party
reference** — never a source, never LEVI branding. Each entry carries an
explicit `"reference": true` label plus the provider name behind the
server (e.g. `Context7`, `CoinGecko`). On install, that provider is
recorded in the universal reference registry (`levi reference list`,
kind `mcp-server`), and every display path (`mcp catalog`,
`mcp list-servers`) labels it as a reference. The catalog ships no LEVI
identity and no provider is ever presented as LEVI.

## Free core: no API keys in the default catalog

The default catalog contains **no servers that require a paid API key**.
Entries that offer extra features behind an optional key (e.g. Jina AI's
web-search tools) install and work without one; the optional key is
mentioned in the entry's `note`, never baked into the catalog, and LEVI
never stores keys there.

## Trust note

`levi mcp add --catalog` is the same trust decision as any
`levi mcp add`: the server's tools are attached to the agent as
`mcp__<server>__<tool>` and are **not** confirmation-gated. Only install
servers you trust — the catalog is curated for convenience, not a
security endorsement. `npx`/`uvx` commands download and run third-party
code at install time.

## Adding your own entry

Append one dict to `CATALOG` in `core/levi/mcp/catalog.py`:

```python
{
    "name": "my-server",                    # unique, [A-Za-z0-9_-]{1,64}
    "description": "One line, no secrets.",
    "transport": "stdio",                   # or "http"
    "command": ["npx", "-y", "my-mcp-pkg"], # stdio …
    # "url": "https://host/mcp",           # … or http (one of the two)
    "provider": "Someone",                  # external provider name
    "reference": True,                      # must be exactly True
    "tags": ["docs"],                       # optional
    "note": "No API key required.",         # optional
},
```

Rules enforced on load (`CatalogError` otherwise):

- required keys: `name`, `description`, `transport`, `provider`, `reference`
- `reference` must be exactly `True` — the third-party label is not optional
- `provider` must not collide with LEVI's own identity
- `stdio` needs a non-empty `command` list; `http` needs an `http(s)` URL
- names must be unique; unknown keys are rejected (typo protection)
- no secrets: keep API keys out of the catalog entirely

Then run the catalog tests:

```bash
pytest tests/test_mcp_catalog.py -q
```

## See also

- `docs/MCP.md` — the MCP client/server model, transports, trust model
- `docs/REFERENCES.md` — the universal provider-reference registry
