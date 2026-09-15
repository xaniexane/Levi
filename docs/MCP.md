# LEVI as an MCP Server

**MCP (Model Context Protocol)** is an open standard (Anthropic, 2024) that
lets AI apps talk to external tools over JSON-RPC: a *client* (Claude
Desktop, an editor, another agent) connects to a *server* that advertises
tools, and calls them by name with JSON arguments. LEVI ships an MCP
server so any MCP-compatible app can consume LEVI's tool registry —
LEVI becomes a tool provider for other intelligences, not just a
standalone agent.

## Quickstart

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
