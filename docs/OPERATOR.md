# The Universal Operator Contract

**One interface, no exceptions.** Every operator — LEVI-native minds,
other synthetic-intelligence operators, artificial-intelligence
operators, and Xi nano-bit operators — is built the same way behind
one contract (`core/levi/operator/`), so any operator is
interchangeable with any other in any seat/role. Swapping operators
is a config change, never a code change.

## The contract

`Operator` (`core/levi/operator/contract.py`) is an ABC with five
things to declare and one thing to implement:

- **Identity** — `name`, `kind`, `version`, `lineage` (origin label),
  `identity_label`. Stdlib only; no torch, no numpy, no network.
- **`capabilities()`** — tools offered, streaming yes/no, memory
  access, context window, tool-use-loop support.
- **`step(messages, tools, context)`** — one turn in, a well-formed
  `OperatorResult` out (text + tool calls + usage + finish reason +
  honest cost). Never raises: failures are results, not exceptions.
- **`stream()`** — chunked output; a default implementation runs
  `step()` for adapters without real streaming.
- **`health()` / `cost()` / `degrade()`** — availability, honest
  unit economics, and a graceful-degradation hook that returns a
  safe result instead of fake work.

`OperatorResult.finish_reason` is one of `stop | tool_calls | error |
degraded | refused`. `result.ok` is False for the last three.

## The kind taxonomy

| kind | What it is |
|---|---|
| `native` | LEVI's own core: deterministic machinery built in this repo (rule-based planner, rules-engine mind, automation flows). Always available; the fallback of last resort. |
| `si` | Synthetic-intelligence operators of the LEVI family: LEVI's own trained brain, LEVI remix weights on LEVI's runner, specialist personas voiced by LEVI's brain. Built here, honest about limits. |
| `ai` | Artificial-intelligence operators: external model APIs consumed as tools (OpenAI-compatible endpoints, Anthropic, local third-party servers) and foreign intelligences on the integrated leash. Labeled references, never sources, never branding. |
| `xi` | **The Xi nano-bit tier** — Chauncey's coined proper name, kept verbatim (`NanoBitOperator` in code, `nano_bit` in config, "nano-bit" in prose): the nano-scale minimal operator tier. Smallest, fastest, cheapest; built for trivial turns at near-zero cost. First-class LEVI operators, just tiny. |

XI is **not** "external intelligence". Foreign intelligences are a
separate concept: operators that wrap outside minds set
`is_foreign = True` and ride the integrated-intelligence leash —
scoped capability declarations only, no shell, no session kills, no
milestone signatures, declared origin, instruction-override screening
on their output. Same interface; tighter leash.

**No-mask law** (enforced by the contract at registration): a
non-native operator may never present as LEVI-native identity.
Violations are refused with `OperatorContractError` — outside
providers are labeled references, never sources, never branding.

## Escalation routing: nano-bit by default, full operators by stakes

Bulk trivial turns default to the nano-bit tier; the router escalates
by need/stakes (`levi.operator.registry`):

- `assess_stakes(messages, tools, context)` → `trivial | normal | high`.
  Explicit `context["stakes"]` wins; high-stakes tools (shell, signing,
  session kills) or high-stakes text (money, production, deletes)
  escalate; short tool-free greetings/thanks/acks stay trivial.
- `resolve_for_task(seat_id, messages, tools, context, config)` →
  operator name: trivial → `nano-bit`, normal → the seat's operator,
  high → past nano-bit to the full tier (never back into nano-bit).
- Routing prefers nano-bit on cost grounds for trivial turns — it is
  the volume tier of the dollar-scale-entry doctrine.

```python
config = {
    "seats": {"chat": "levi-brain"},          # seat -> operator name
    "tiers": {"nano_bit": "nano-bit", "full": "levi-brain"},
    "escalation": {"enabled": True},
    "twins": {"mode": "off"},                 # pending Chauncey's call
}
name = resolve_for_task("chat", messages, tools, {}, config)
```

## Twin-pair seats (structural only)

`TwinPair(primary, verifier, mode)` + `resolve_twin(seat_id, config)`
provide the primary + independent-verifier slots under all three
pending options (`off` / `on_demand` / `always`). The architecture
decision is **pending Chauncey's call**; default mode is `off`, which
changes nothing. **Merge/judge is GATED and not built**: the user
judges hard cases ("inverse" needs his definition of inverse-of-what
first); `OperatorSession.verify_via()` runs the verifier and returns
its independent result for the caller to judge — no automatic merge.

## The registry

`OperatorRegistry` (`core/levi/operator/registry.py`):

- `register(name, operator)` — validates the contract on the way in
  (no-mask, foreign scope). Violations raise `OperatorContractError`.
- `resolve(name_or_config)` — name, `{"operator": name}`, or
  `{"seat": ..., "seats": {...}}`; unknown names fall back to `local`.
- `resolve_for_seat(seat_id, config)` — seat → operator name, sane
  defaults in `DEFAULT_SEAT_MAP`.
- `open_session(session_id, name_or_config)` / `swap(session_id,
  new_name)` — conversation state lives in the **session**, so a
  mid-session operator exchange preserves the full message history.
- `scoped_step(operator, messages, tools, context)` — enforces the
  foreign-operator leash at runtime: out-of-scope offered tools are
  refused before the operator runs; out-of-scope emitted tool calls
  are blocked.
- `default_registry()` — builtins: `local`, `levi-brain`,
  `levi-local`, `openai`, `anthropic` (when available), the council
  minds (`rules-engine`, `native-brain`, `specialists`), and the
  reference `nano-bit` (always registered — the bulk tier must never
  be missing).

## Adapters (wrap, never rewrite)

`core/levi/operator/adapters.py`:

- `ChatProviderAdapter` — wraps any `ChatProvider`; the `chat()`
  compatibility shim lets `agent/loop.py` and `agent/chat.py` sit
  behind the contract with a one-line change (see
  `core/levi/operator/SEAT_WIRING_NOTES.md`).
- `NanoBitOperator` — the reference Xi nano-bit operator:
  deterministic trivial-turn handler, metered at $0.000001/turn,
  refuses non-trivial work with an escalation hint.
- `MindAdapter` — council minds (`generate` path).
- `DynastyOperatorAdapter` — wave agents, wrap-only (the dynasty
  package is never edited); foreign integrated agents ride as
  `kind="ai"`, `is_foreign=True`.
- `AutomationRunnerAdapter` — the flows engine, dry-run by default
  (the automation package is never edited).

## Registering a new operator

```python
from levi.operator import Operator, OperatorCapabilities, OperatorHealth, OperatorResult
from levi.operator.registry import default_registry

class MyOperator(Operator):
    name = "my-op"
    kind = "si"                      # native | si | ai | xi
    lineage = "levi:my-op"           # origin, honestly labeled

    def capabilities(self):
        return OperatorCapabilities(tools=("recall",), context_window=4096,
                                    tool_use_loop=True)

    def health(self):
        return OperatorHealth(ok=True, note="ready")

    def step(self, messages, tools, context):
        ...  # never raise; return OperatorResult(...)
        return OperatorResult(text="...", operator=self.name, kind=self.kind)

registry = default_registry()
registry.register("my-op", MyOperator())   # validated: no-mask, scope
session = registry.open_session("s1", "my-op")
```

Rules for the new operator: pick the honest kind; never claim
LEVI-native identity unless `kind == "native"`; set
`is_foreign = True` and declare scoped tools if it wraps an outside
mind; meter `cost()` honestly (nano-bit tier: near-zero, metered).

## The interchangeability guarantee

Any seat accepts any operator by name/config. The guarantee is
structural, not a promise about quality:

1. Same `step()` shape in, same `OperatorResult` shape out — a
   nano-bit refusal and a full-operator answer are both well-formed.
2. Conversation state lives in `OperatorSession`, not the operator —
   `swap()` exchanges the mind mid-session without losing history.
3. Registration refuses contract violators loudly; runtime refuses
   out-of-scope foreign behavior loudly. Nothing fails silently.

## Honest limits

- The contract guarantees **shape**, not **capability**: a nano-bit
  operator will refuse real work, and a stub will report
  unavailability. Interchangeable means swappable, not equivalent.
- `assess_stakes` is heuristic (patterns + tool names + explicit
  context). Adversarial or ambiguous phrasing can misroute; explicit
  `context["stakes"]` overrides it — use it for consequential calls.
- Twin-pair merge/judge is **not built** (GATED on Chauncey's call).
  `verify_via` returns the verifier's independent opinion; the caller
  (ultimately the user on hard cases) judges.
- Cost metering is per-operator honest reporting, not a billing
  system: `cost_usd` on results is what the operator declares.
- Foreign-operator output screening blocks known
  instruction-override patterns and caps length; it is a leash, not
  a proof of safety.
- The seat-wiring into `agent/loop.py` + `agent/chat.py` is specified
  in `SEAT_WIRING_NOTES.md` and lands after the sibling worker's
  in-flight edits — until then, those call sites use providers
  directly.
