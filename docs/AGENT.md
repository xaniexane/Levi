# LEVI Agent Runtime — the step-level tool-using agentic loop

Offline-first, stdlib-only. No `pip install`, no daemons, no API key needed
to get a working agent: the default provider is a deterministic local
planner, and cloud models attach as wings when you configure them.

This document was written against the real code and every count below was
re-verified programmatically (tool list, endpoint list, env-var list).
If a number here ever disagrees with the code, the code is right.

## 1. Architecture

Four modules under `core/levi/agent/`, one job each:

| Module | Job |
|---|---|
| `tools.py` | The **tool-execution registry**: 15 named built-in tools, sandboxed handlers, confirmation gates. |
| `providers.py` | The **chat/tool-calling provider chain**: local-first selection, OpenAI-compatible and Anthropic providers over stdlib `urllib`. |
| `loop.py` | The **step-level loop** (`run_subtask`): model → tool calls → tool results → repeat, until the model answers without calling tools. |
| `server.py` | The **HTTP front door**: stdlib `ThreadingHTTPServer` skin over `run_subtask`, bearer-token auth. Adds no capabilities, only a network address. |

### 1.1 The tool registry (`tools.py`)

`ToolRegistry` is a named store: `register`, `get`, `list`, `execute`.
`build_default_registry()` installs the 15 built-ins — verified by loading
the registry and counting, not by quoting prose:

- **9 ungated** (read-only or agent-internal): `delegate`, `file_read`,
  `memory_read`, `memory_write`, `schedule_list`, `schedule_remove`,
  `skill_list`, `skill_load`, `web_search`
- **6 gated** (`requires_confirmation=True`): `file_edit`, `file_write`,
  `http_request`, `schedule_add`, `shell_exec`, `web_fetch`

Gating rules, enforced in `ToolRegistry.execute()`:

- A gated tool with no `consent` asks the `confirm` callback with a
  human-readable preview; a declined or missing callback raises
  `ConfirmationRequired`. **There is no flag that turns all gates off.**
- `memory_write` is deliberately ungated: writing the agent's own scratch
  memory is the agent thinking, not a consequential external action.
  (`delegate` inherits the parent's consent; gates stay gated inside the
  child run — they are honestly denied, never re-prompted.)
- The destructive-shell denylist in `_blocked_destructive()` runs **before**
  any gate and **can never be bypassed, even with consent**: `rm -rf` on
  filesystem roots/home, `mkfs`, fork bombs, `dd` to block devices, writes
  to raw disk devices.
- All file tools are sandboxed to the workspace root: absolute paths and
  `..` escapes are refused. Tool-result text is truncated
  (50k chars shell output, 200k file reads) so one bad tool call can't
  drown the loop.

`delegate` honesty fix (2026-09-15): when a delegated subtask's transcript
reports `ok=False`, the outer `ToolResult` now reports `ok=False` with the
transcript summary attached — a failing subtask can no longer surface as a
success. Pinned by `test_delegate_propagates_subtask_failure`.

### 1.2 The provider chain (`providers.py`)

Selection order: explicit `provider=` argument → `LEVI_PROVIDER` env var →
**`LocalProvider` default**. A preferred provider that is unavailable falls
back to `LocalProvider` (offline-first, honestly — the loop always reports
which provider it ended up with).

| Provider | Name | `is_available()` when |
|---|---|---|
| `LocalProvider` | `local` | always (deterministic rule-based planner, no network) |
| `OpenAICompatibleProvider` | `openai` | `LEVI_OPENAI_API_KEY` set **or** `LEVI_OPENAI_BASE_URL` overridden |
| `AnthropicProvider` | `anthropic` | `LEVI_ANTHROPIC_API_KEY` set |

Ollama-local setup (verified against `is_available()` and `chat()`):
a local server may need no key at all —
`LEVI_OPENAI_BASE_URL=http://localhost:11434/v1` is sufficient. The same
code path also covers vLLM and any OpenAI-compatible endpoint. HTTP
timeout on cloud calls: 60s. Provider errors never raise and never fake a
response: they come back as `ChatResponse.error`, and the loop ends
honestly.

### 1.3 The loop (`loop.py`)

```python
run_subtask(task, *, provider=None, registry=None, consent=False,
            confirm=None, max_steps=10, workspace_root=None,
            system_prompt=None, ctx=None) -> AgentTranscript
```

- `provider` may be a `ChatProvider` instance, a name string
  (`"local"` / `"openai"` / `"anthropic"`), or `None` for
  `select_provider()`.
- Each step: provider chat → execute tool calls (unknown tools and handler
  exceptions become honest `ok=False` results, never fatal) → feed results
  back as `role="tool"` messages → repeat.
- The run ends when the provider answers with no tool calls (`ok=True`),
  when a confirmation gate trips (`ok=False`,
  `error="confirmation_required"` — the loop never retries a denied gate),
  when the provider reports an error (`ok=False`, surfaced verbatim), or
  at the step limit (`ok=False`, `error="max_steps_exceeded"`).
- `AgentTranscript.to_dict()` is JSON-serializable (used by the HTTP
  server and CLI `--json`).

### 1.4 The HTTP server (`server.py`)

3 endpoints, verified against the routing code:

| Endpoint | Auth | Behavior |
|---|---|---|
| `GET /healthz` | open | `{"status": "ok", "service": "levi-agent"}` — for load balancers |
| `GET /v1/tools` | Bearer | the 15 tool descriptors with `requires_confirmation` flags |
| `POST /v1/agent/run` | Bearer | runs the loop non-interactively; returns `{"transcript": {...}}` |

Auth: `Authorization: Bearer <token>` compared with `hmac.compare_digest`;
wrong or missing → `401 {"error": "unauthorized"}`. `serve()` refuses to
start without `LEVI_AGENT_TOKEN` — it prints a refusal and exits 2 rather
than ever serving unauthenticated. Body > 1 MiB → `413`. Missing `task` →
`400`. Step count is clamped to `[1, 50]`. `/v1/agent/run` is
non-interactive by construction (`confirm=None`): with `consent=false` a
gated tool is honestly denied; with `consent=true` the caller accepts
responsibility for that run's gated actions.

### 1.5 Reconciliation with the canonical neighbors (blueprint §1.2)

One implementation per concept — this runtime merges nothing:

- `levi.orchestration.loop` — the **conversation turn pipeline**
  (UNDERSTAND → PERSONA → SPECIALISTS → SKILLS → SYNTHESIZE). Decides
  *what* a turn is about; not merged here.
- `levi.agent.runtime` — **task-level specialist dispatch** (select
  specialist → act via skills). Picks *who* does a job; not merged here.
- `levi.model.abstraction` — the canonical **generation** router
  (prose/story generation). A different interface (no tool calls);
  `providers.py` imports nothing from it.
- `levi.daemon.automation` — the canonical **scheduling** backend
  (`AutomationRegistry`); the `schedule_*` tools delegate to it rather
  than keeping a second schedule database. `create()` accepts an optional
  `trigger_config` dict (e.g. `{"cron": ..., "task": ...}`) and
  `remove(auto_id)` deletes by id.
- `levi.skill.registry` — the canonical **skill/capability catalog**;
  `skill_list` bridges to it.

## 2. Provider configuration

Every environment variable read by `core/levi/agent/*.py` (9, verified by
grep against the sources):

| Variable | Used by | Meaning |
|---|---|---|
| `LEVI_PROVIDER` | `select_provider()` | `local` / `openai` / `anthropic`; default `local` |
| `LEVI_OPENAI_API_KEY` | `OpenAICompatibleProvider` | Bearer key for cloud OpenAI (omit for keyless local servers) |
| `LEVI_OPENAI_BASE_URL` | `OpenAICompatibleProvider` | default `https://api.openai.com/v1`; set to `http://localhost:11434/v1` for Ollama |
| `LEVI_OPENAI_MODEL` | `OpenAICompatibleProvider` | default `gpt-4o-mini` |
| `LEVI_ANTHROPIC_API_KEY` | `AnthropicProvider` | `x-api-key` for api.anthropic.com |
| `LEVI_ANTHROPIC_MODEL` | `AnthropicProvider` | default `claude-sonnet-4-20250514` |
| `LEVI_AGENT_TOKEN` | `server.serve()` | required bearer secret; server exits 2 without it |
| `LEVI_OFFLINE` | web tools | set to `1` to force honest "network unavailable" failures |
| `LEVI_AUTOMATIONS_DIR` | `schedule_*` tools | overrides the `AutomationRegistry` data dir (used by tests) |

No credentials are ever logged: the HTTP tools explicitly log nothing
about headers or bodies, and the server's startup line names the bind
address, never the token.

## 3. Safety model

- **Gates on consequential actions** (blueprint §1.5): 6 of the 15 tools
  require confirmation. Consent is **per-run** (`levi agent run --yes`
  applies to that run only); there is no global "disable all gates" flag.
- **TTY prompting**: without `--yes`, a gated tool prompts on an
  interactive terminal only — piped/non-TTY stdin is denied honestly
  rather than hanging or defaulting to yes.
- **Destructive denylist**: `rm -rf /`, `mkfs`, fork bombs, raw-device
  writes are blocked even with explicit consent.
- **Sandboxing**: file and shell tools cannot escape the workspace root
  (default `~/.levi/agent_workspace/`; memory `~/.levi/agent_memory/`;
  skills `~/.levi/skills/`).
- **Server is non-interactive by construction**: remote callers get
  denial or explicit per-request consent, never a prompt.
- **Honest failure**: unknown tools, handler exceptions, provider errors,
  timed-out delegates, and subtask failures all surface as `ok=False`
  with the real error — the loop and tools never fabricate success.

## 4. SERVE-THE-CLOUD deployment shape

The design is offline-first local by default, but the same binary serves:
run LEVI on a home server or VPS as the backend that the user's phone and
other machines talk to — like any cloud AI API, except the operator is
the user.

- Bind default is `127.0.0.1` (port 8765). **Remote exposure belongs
  behind a TLS reverse proxy** (nginx/Caddy) — never bind this server to
  `0.0.0.0` directly on the open internet.
- Token handling: `LEVI_AGENT_TOKEN` must be a long random secret; it is
  never logged; rotate it by restarting the server with a new value.
  Compare with `hmac.compare_digest` (constant-time) on every `/v1/*`
  request.
- `/healthz` stays open for load-balancer/uptime checks; everything else
  is token-gated.

## 5. Worked examples

### 5.1 CLI — a real multi-step run on the local provider

Captured from an actual run (exit 0):

```
$ python -m levi.cli.main agent run "create notes.txt with three lines, read it back" \
    --yes --workspace /tmp/levi-agent-demo
Running with provider=local consent=yes (--yes) ...

── step 1 ──
  tool file_write {'path': 'notes.txt', 'content': 'Line 1\nLine 2\nLine 3'} → ok
    out: wrote /tmp/levi-agent-demo/notes.txt
── step 2 ──
  tool file_read {'path': 'notes.txt'} → ok
    out: Line 1
Line 2
Line 3

══ final (ok) ══
Done: wrote 3 line(s) to notes.txt and read notes.txt back. Contents read: 'Line 1\nLine 2\nLine 3'.
```

The file was verified on disk afterward. `--json` prints the transcript
as JSON instead of the human-readable steps.

### 5.2 curl against a served instance

Captured from an actual served instance (token `smoke-test-token`):

```
$ LEVI_AGENT_TOKEN=smoke-test-token python -m levi.cli.main agent serve --port 18765 &
$ curl http://127.0.0.1:18765/healthz
{"status": "ok", "service": "levi-agent"}
$ curl -H "Authorization: Bearer smoke-test-token" \
    http://127.0.0.1:18765/v1/tools | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(len(d['tools']))"
15
$ curl -s http://127.0.0.1:18765/v1/tools
{"error": "unauthorized"}        # → HTTP 401 without the token
$ curl -X POST -H "Authorization: Bearer smoke-test-token" \
    -H "Content-Type: application/json" \
    -d '{"task": "create notes.txt with three lines, read it back",
         "consent": true, "max_steps": 10}' \
    http://127.0.0.1:18765/v1/agent/run
# → 200, the transcript (abridged): the served instance drove the loop
#    through file_write → file_read on its own workspace
{
  "transcript": {
    "task": "create notes.txt with three lines, read it back",
    "provider_name": "local",
    "steps": [ ... 2 steps, file_write → file_read ... ],
    "final": "Done: wrote 3 line(s) to notes.txt and read notes.txt back. Contents read: 'Line 1\nLine 2\nLine 3'.",
    "ok": true,
    "error": null
  }
}
```

Without the token in the environment, `agent serve` refuses with exit 2:
`levi-agent: refusing to serve — LEVI_AGENT_TOKEN is not set.`

### 5.3 Python — driving the loop from code

This pattern is exercised by `tests/test_agent_loop.py`:

```python
from levi.agent.loop import run_subtask
from levi.agent.providers import LocalProvider
from levi.agent.tools import build_default_registry

registry = build_default_registry(workspace_root="/tmp/demo-ws")
transcript = run_subtask(
    "create notes.txt with three lines, read it back",
    provider=LocalProvider(),   # or "local", or None for select_provider()
    registry=registry,
    consent=True,               # per-run consent for the 6 gated tools
)
print(transcript.ok)            # True
print(transcript.final)         # "Done: wrote 3 line(s) to notes.txt ..."
for step in transcript.steps:   # provider_text, tool_calls, results
    ...
```

### 5.4 CLI reference

```
levi agent run "<task>" [--provider local|openai|anthropic] [--yes]
                        [--max-steps N] [--workspace DIR] [--json]
levi agent tools
levi agent serve [--host 127.0.0.1] [--port 8765]   # needs LEVI_AGENT_TOKEN
```

## 6. Tests

Hermetic (no network, no user HOME writes):

- `tests/test_agent_tools.py` — 47 tests: registry basics, gating,
  denylist, sandboxing, all 15 tools, delegate honesty.
- `tests/test_agent_providers.py` — 27 tests: provider chain, Ollama
  compatibility, honest error surfacing.
- `tests/test_agent_loop.py` — 10 tests: tool execution and result
  feedback, `max_steps`, confirmation gate, provider errors, transcript
  JSON round-trip, provider-as-instance/name/None.
- `tests/test_agent_server.py` — 11 tests: real server on an ephemeral
  port — `/healthz`, auth on `/v1/*`, loop driving, 400/404/413, token
  refusal.
- `tests/test_cli.py` — `levi agent tools` exit code and tool listing.

Run: `python3 -m pytest tests/ -q` from the repo root.
