# Provider references — the universal plug-in point

Binding rule (Chauncey, 2026-09-15): provider and model names — KAI-9000,
Qwen, LLaMA, Pollinations, anything else — are **references**, never
sources. A reference is a pointer for comparison or attribution. LEVI is
sourced from itself: references never become LEVI branding, registers,
personas, voices, or claimed origins.

`levi.plugins.references` is the ONE universal plug-in point for this
rule. Every subsystem that touches an external provider records it here:

| Subsystem | How it plugs in |
|---|---|
| MCP client servers | `levi mcp add <name> --url … --reference KAI-9000` |
| Plugin connectors | `references = ("KAI-9000",)` class attribute on the connector |
| Anything else | `levi reference add <provider> --kind model\|media\|plugin\|other` |

## CLI

```bash
levi reference list
# ══ Provider references ══
# ref-kai-9000 — reference: KAI-9000  [mcp-server]
#   (external provider reference — never a LEVI source or identity)
#   via: https://example.com/mcp

levi reference add Pollinations --kind media --detail note="image generation"
levi reference remove ref-pollinations

levi mcp add kai_9000 --url https://example.com/mcp --reference KAI-9000
levi mcp list-servers
#   kai_9000  [http]  https://example.com/mcp  (reference: KAI-9000)
```

`levi mcp remove <name>` unplugs the linked reference record too, so a
stale provider label can never linger after its server is gone.

## Identity guard

`assert_not_levi_identity()` rejects any reference name or id that
collides with LEVI's own registers — case-insensitive, separator-blind,
so `LEVI`, `levi-care`, and `LeviCare` are all refused. Connector
`references` are validated at class-definition time: a connector that
declares a colliding reference fails to import, loudly.

Records live in `~/.levi/references.json` (owner-only `0o600`, atomic
writes), next to `~/.levi/mcp/servers.json`.
