---
skill_id: cyber_auditing_mcp_servers_for_tool_poisoning
name: Auditing MCP Servers for Tool Poisoning
description: Audit Model Context Protocol servers: tool schemas, prompt injection, and poisoning.
risk: low
permissions: []
requires_confirmation: false
tags: [ai-security]
version: 1.0.0
---
# Auditing MCP Servers for Tool Poisoning

## Purpose

Audit Model Context Protocol (MCP) servers for tool poisoning — where a tool's name,
description, or schema is crafted to manipulate the AI client (or the user) into unsafe
actions: exfiltrating data through tool arguments, hijacking tool selection, or hiding
malicious instructions in descriptions the model treats as trustworthy. This is a
defensive review of servers you operate or procure.

## When to use

- Before deploying or procuring a third-party MCP server for an assistant or agent.
- When adding tools with side effects (file write, shell exec, network calls, payments)
  to an MCP server.
- After an incident where an agent took an unexpected action via a tool call.
- As part of AI supply-chain review: MCP servers are executable code the model invokes.

## Prerequisites

- Written authorization and a defined scope: which MCP servers (and versions/commits) are
  in bounds.
- The server source code or a pinned, reviewable distribution — auditing a black-box
  server binary is limited to behavioral testing.
- A sandboxed MCP client for behavioral testing (never point a production assistant at an
  untrusted server during the audit).
- Inventory of what each tool *should* do, from the server's documentation or owner.

## Procedure

1. **Inventory the tool surface.**
   - Connect with a test client and list every tool: name, description, input schema, and
     declared side effects.
   - Record the server version/commit; tools change between releases.

2. **Read every tool description adversarially.**
   - Descriptions are rendered to the model as trusted context — flag instructions
     embedded in descriptions ("always…", "before doing X, first…", "ignore…"), urgency
     language, or directives to call other tools first (tool-selection hijacking).
   - Flag descriptions that misrepresent what the tool does versus the implementation.

3. **Audit the input schemas.**
   - For each tool, check whether the schema accepts overly broad inputs (raw file paths,
     arbitrary URLs, unvalidated shell fragments) that let a prompt-injection payload
     steer the tool.
   - Confirm required vs. optional fields match the documented contract; extra accepted
     fields are smuggling surface.

4. **Trace tools to their implementations.**
   - Read the handler code for every tool: what system calls, file paths, network
     destinations, and credentials does it touch?
   - Flag tools whose implementation reaches further than their description claims
     (e.g., "reads config" that actually shells out with the argument).

5. **Check for data exfiltration paths.**
   - Identify tools that send data off-host (HTTP calls, webhooks, DNS) and what data
     they include — a "summarize file" tool that POSTs contents to a third party is a
     finding.
   - Verify allowlisted destinations and that credentials/API keys aren't injectable via
     tool arguments.

6. **Review the server's own supply chain.**
   - Audit dependencies (`package-lock.json`, `requirements.txt`, `go.mod`) for known
     vulnerabilities and for typosquatted or unmaintained packages.
   - Confirm the server doesn't fetch remote code or prompts at runtime (dynamic tool
     definitions pulled from a URL are poisoning-ready).

7. **Behavioral test in the sandbox.**
   - With authorization, feed the tools adversarial-but-benign inputs (path traversal
     strings, SSRF targets against a local listener, oversized payloads) and observe what
     the server actually does.
   - Test tool-selection behavior: present overlapping tool names/descriptions and see
     which the test client prefers — hijacking-prone servers pick the poisoned one.

8. **Check authentication and transport.**
   - Verify how the server authenticates clients (if at all) and whether the transport
     (stdio vs. SSE/HTTP) exposes the tool surface to the network.
   - An unauthenticated network-reachable MCP server with side-effect tools is remote
     code execution by design.

9. **Produce findings with severity.**
   - For each issue record the tool name, the poisoning vector (description injection,
     schema smuggling, hidden side effect, exfiltration), evidence (code excerpt or test
     transcript), and a concrete fix (rewrite descriptions as data-only, tighten schemas,
     add allowlists, require confirmation for side effects).

## Key tools & commands

- MCP Inspector (`npx @modelcontextprotocol/inspector`) — connect to a server and
  enumerate tools, resources, and prompts interactively.
- A minimal test client script (Python/Node with the MCP SDK) for scripted behavioral
  tests.
- `npm audit` / `pip-audit` / `osv-scanner` — dependency vulnerability review.
- `grep`/`rg` for `exec`, `shell`, `fetch(`, `axios`, `requests.post` in tool handlers —
  quick triage of side-effect surface.
- `nmap`/listener checks for network-exposed MCP transports.

## Expected outputs

- Tool inventory: name, description summary, schema, implementation side effects.
- Findings with evidence (description excerpts, code lines, test transcripts) and severity.
- Behavioral test log with cleanup confirmation.
- Remediation guidance: description hygiene rules, schema tightening, confirmation gates
  for side-effect tools, server allowlisting policy.

## Pitfalls

- Reviewing descriptions but not implementations — the poisoning that matters most is a
  benign description over a malicious handler.
- Testing against a production assistant instead of a sandboxed client — a poisoned tool
  under test can take real actions.
- Assuming stdio transport means safe — any process that can spawn the server inherits
  its tool power.
- Forgetting updates: MCP servers auto-update in some setups, invalidating the audit —
  pin versions and re-audit on change.

## References

- Model Context Protocol specification and documentation (modelcontextprotocol.io).
- OWASP Top 10 for LLM Applications: LLM06 (Excessive Agency), LLM07 (System Prompt
  Leakage), LLM08 (Vector and Embedding Weaknesses — supply-chain analog).
- MITRE ATLAS: `AML.T0015` (Backdoor ML Model — supply-chain analog), `AML.T0020`
  (Poison Training Data).
- NIST AI 600-1 Generative AI Profile: agentic system risk considerations.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
