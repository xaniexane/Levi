# LEVI and MCP (Model Context Protocol)

**MCP (Model Context Protocol)** is an open standard (Anthropic, 2024) that
lets AI apps talk to external tools over JSON-RPC: a *client* connects to
a *server* that advertises tools, and calls them by name with JSON
arguments. LEVI speaks MCP in **both** directions:

* **Server** (`levi mcp serve`) — any MCP-compatible app can consume LEVI's
  tool registry; LEVI becomes a tool provider for other intelligences.
* **Client** (`levi mcp add …`) — LEVI connects *out* to external MCP
  servers and merges their tools into the agent's own registry, so
  `levi agent run` can use third-party tools.

## LEVI as an MCP server

**Local client (full tools, owner):**

```bash
levi mcp serve --transport stdio
```

Point any MCP client at that command. Example generic client config:

```json
{
  "mcpServers": {
    "levi": {
      "command": "levi",
      "args": ["mcp", "serve", "--transport", "stdio"],
      "env": { "HOME": "/home/you" }
    }
  }
}
```

**Network (restricted tools):**

```bash
levi mcp serve --transport http --port 8899 --token "$LEVI_MCP_TOKEN"
```

Then `POST` JSON-RPC to `http://127.0.0.1:8899/mcp`, or open
`GET /sse` for the session handshake (`event: endpoint` →
`POST /message?sessionId=…`).

```bash
curl -s http://127.0.0.1:8899/mcp \
  -H "Authorization: Bearer $LEVI_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Protocol coverage

MCP 2024-11-05 over JSON-RPC 2.0. Methods: `initialize`,
`notifications/initialized`, `ping`, `tools/list`, `tools/call`,
`resources/list`, `resources/read`. Standard JSON-RPC error codes
(-32700, -32600, -32601, -32602, -32603). stdio uses newline-delimited
JSON-RPC (no Content-Length framing).

**Tools:** all 24 registry tools are mapped 1:1 to MCP shape
`{name, description, inputSchema}` — every built-in already carries a
valid JSON Schema (`type: object, properties, required`); a normalizer
keeps `tools/list` legal if a future tool ships a non-conforming spec.

**Resources (read-only):** `levi://info` (server name, version,
protocol, profile, tool names) and `levi://capabilities` (capability
atlas summary).

## Security model

Enforced server-side by transport — a client can never claim a wider
profile:

| Transport | Registry | Notes |
| --- | --- | --- |
| stdio | full (24 tools) | owner only: the client spawns the process as you |
| HTTP | cloud-safe (12 read-only tools) | reuses `levi.cloud.profile.CLOUD_SAFE_TOOLS`; no shell, no file writes, no memory, no schedule, no delegate, no arbitrary egress |

Confirmation-gated tools (shell_exec, file_write, …) need explicit
consent, and MCP 2024-11-05 has no confirmation flow — so over MCP
they return a tool-level error unless the server was started with
`--consent` (stdio only; never use it on a shared machine).

HTTP binds to 127.0.0.1 by default. `--token` adds Bearer auth (401
without it). Without a token, anyone who can reach the port can call
the restricted tools — keep it on localhost or behind your own TLS.

## Honest limits

* Single-machine, stdlib-only: no TLS natively, no multi-worker, no
  per-client scopes — put a reverse proxy in front for real exposure.
* HTTP rate limiting lives in the cloud API server, not here.
* The SSE stream currently carries no spontaneous server→client
  notifications (keep-alive only); request/response over POST is the
  complete path.
* `tools/call` is synchronous: a long-running tool holds the HTTP
  worker thread until it returns.

---

## LEVI as an MCP client

LEVI can also consume tools from *other* MCP servers — a second LEVI
instance, a local dev-tools server, any third-party MCP server. Added
servers are probed at `add` time and re-contacted on every
`levi agent run` / `levi agent chat` start (unreachable servers are
skipped with a warning, never fatal).

```bash
# Streamable HTTP server
levi mcp add notes --url http://127.0.0.1:8899/mcp

# Local stdio server
levi mcp add files --cmd "npx -y some-mcp-server"

levi mcp list-servers
levi mcp remove files
```

Remote tools appear in the agent registry as
`mcp__<server>__<tool>` (e.g. `mcp__notes__search`) and are callable
like any built-in:

```bash
levi agent run "search my notes for the vault passphrase" --yes
```

Configs live in `~/.levi/mcp/servers.json` (owner-only 0o600):
`{transport: http|stdio, url|command, headers?, timeout?}`.

**Trust model:** adding a server is the explicit trust decision —
remote tools are *not* confirmation-gated. Only add servers you trust,
exactly like installing a plugin. Server configs never store secrets
in plain sight beyond what you pass as headers (prefer env-injected
tokens via your own wrapper).

**Transports:** Streamable HTTP (`POST /mcp`, with automatic fallback
to the legacy HTTP+SSE handshake) and stdio (subprocess,
newline-delimited JSON-RPC). Per-call timeout defaults to 30s
(overridable per server).

**Honest limits:** no background reconnect loop (reconnect happens on
each agent start); notifications from servers are ignored; tool calls
are synchronous with a timeout.

## External providers as references (binding)

LEVI's product identity is LEVI-only, and LEVI is sourced from itself.
Provider and model names — KAI-9000, Qwen, LLaMA, Pollinations,
OpenAI-compatible endpoints, anything else — are **references**, never
sources: not registers, not personas, not UI, not docs prose, and never
anything LEVI draws capability from. A reference is a pointer for
comparison or attribution — nothing more.

```bash
levi mcp add kai_9000 --url https://example.com/mcp      # a provider, as a reference
levi mcp list-servers                                    # references, plainly labeled
```

The same rule covers model weights: `levi agent model pull` ships
LEVI-named weights (`levi-0.6b`, `levi-4b`); the upstream base appears
only in the download table as a reference note. Anything the user sees
and talks to is LEVI — registers, voices, the PWA, the CLI.
