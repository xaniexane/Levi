# Seat-wiring patch spec — Operator contract into `agent/loop.py` + `agent/chat.py`

**For the coordinator to apply AFTER sibling worker E lands.**
Worker G did NOT edit these files (conflict avoidance). Everything
below is a precise before/after spec with file:line anchors, verified
against the working tree at commit time.

Goal: every provider sits behind the Operator contract
(`levi.operator`), so any operator — native, si, ai, or Xi nano-bit —
is interchangeable in the loop/chat seats by config. The
`ChatProviderAdapter.chat()` shim keeps all downstream code working
unchanged: it accepts `ChatMessage` lists and returns `ChatResponse`.

Config surface (for later wiring into CLI flags / env):

```python
OPERATOR_CONFIG = {
    "seats": {          # seat_id -> operator name (overrides DEFAULT_SEAT_MAP)
        # "chat": "nano-bit",
        # "loop": "levi-brain",
    },
    "tiers": {"nano_bit": "nano-bit", "full": "levi-brain"},
    "escalation": {"enabled": True},   # resolve_for_task: trivial -> nano-bit
    "twins": {"mode": "off"},          # PENDING Chauncey's call; structural only
}
```

Relevant helpers (all in `levi.operator`):
- `as_operator(obj)` — Operator passes through; ChatProvider gets
  wrapped in `ChatProviderAdapter`; anything else raises.
- `resolve_for_seat(seat_id, config)` — seat -> operator name.
- `resolve_for_task(seat_id, messages, tools, context, config)` —
  stakes-based routing: trivial turns -> `nano-bit`, high-stakes ->
  past nano-bit to the full tier.
- `default_registry()` — registry with builtins registered.

---

## Patch 1 — `core/levi/agent/loop.py`

### 1a. Import (loop.py:36)

BEFORE:
```python
from levi.agent.providers import ChatMessage, ChatProvider, select_provider
```

AFTER:
```python
from levi.agent.providers import ChatMessage, ChatProvider, select_provider
from levi.operator.adapters import as_operator  # Operator contract: every provider sits behind it
```

### 1b. Provider resolution in `run_subtask` (loop.py:252-255)

BEFORE:
```python
    if isinstance(provider, ChatProvider):
        prov = provider
    else:
        prov = select_provider(provider)
```

AFTER:
```python
    if isinstance(provider, ChatProvider):
        prov = provider
    else:
        prov = select_provider(provider)
    prov = as_operator(prov)  # Operator contract: interchangeable operators behind one interface
```

Why this is safe:
- `prov` is used at loop.py:274 only for `getattr(prov, "name", ...)` —
  `Operator.name` exists on the contract, and `ChatProviderAdapter`
  copies the wrapped provider's name, so `provider_name` is unchanged
  (`"local"` stays `"local"`, etc.).
- `prov` is used at loop.py:324 as `prov.chat(messages, tool_schemas)` —
  the adapter's `chat()` shim accepts `ChatMessage` lists and returns
  `ChatResponse`, so the loop body is untouched.
- The `isinstance(provider, ChatProvider)` type-check at loop.py:242
  still works: callers may additionally pass an `Operator` instance
  (extend the check to `(ChatProvider, Operator)` when the Operator
  import is wanted — optional, not required).

### 1c. Optional: stakes-based routing in `run_subtask`

After 1b lands, trivial turns can route to the nano-bit tier by
resolving through `resolve_for_task` instead of using the passed
provider directly. Suggested follow-up (coordinator's call, needs a
config source for the loop):

```python
from levi.operator import default_registry, resolve_for_task
from levi.operator.contract import OperatorMessage as OpMsg
...
    # after prov resolution:
    registry = default_registry()
    routed = resolve_for_task(
        "loop",
        [OpMsg(role="user", content=task)],
        tool_schemas,
        {"stakes": None},   # or explicit per-call stakes
        OPERATOR_CONFIG,
    )
    prov = as_operator(registry.resolve(routed))
```

This is OPTIONAL for the first landing — 1a+1b alone put the loop
behind the contract. The escalation default (`trivial -> nano-bit`)
only activates when the coordinator wires `resolve_for_task`.

---

## Patch 2 — `core/levi/agent/chat.py`

### 2a. Import (chat.py:41)

BEFORE:
```python
from levi.agent.providers import ChatMessage, ChatProvider, select_provider
```

AFTER:
```python
from levi.agent.providers import ChatMessage, ChatProvider, select_provider
from levi.operator.adapters import as_operator  # Operator contract: every provider sits behind it
```

### 2b. Provider resolution in `ChatSession.__init__` (chat.py:244-248)

BEFORE:
```python
        if isinstance(provider, ChatProvider):
            self.provider = provider
        else:
            self.provider = select_provider(provider)
        self.provider_name = getattr(self.provider, "name", None) or "?"
```

AFTER:
```python
        if isinstance(provider, ChatProvider):
            self.provider = provider
        else:
            self.provider = select_provider(provider)
        self.provider = as_operator(self.provider)  # Operator contract
        self.provider_name = getattr(self.provider, "name", None) or "?"
```

Why this is safe:
- chat.py:248 `provider_name` — unchanged (`Operator.name` exists).
- chat.py:271 `elif self.provider_name == "levi-local":` — unchanged
  (adapter copies the wrapped name).
- chat.py:327 `provider=self.provider` (passed into `run_subtask`) —
  now an `Operator`; with Patch 1's extended type-check (or
  `as_operator` passthrough) the loop accepts it. **Ordering note:**
  apply Patch 1 before or with Patch 2, or `run_subtask` will reject
  the Operator at its loop.py:242 type-check.
- chat.py:460 `if self.provider_name == "local":` — unchanged.
- chat.py:494 `self.provider.chat([ChatMessage(...)], [])` — the
  adapter's `chat()` shim handles this unchanged.

### 2c. Optional: seat-configured chat operator

`ChatSession(provider=...)` accepts a provider-name string today.
To select by seat config instead:

```python
from levi.operator import default_registry, resolve_for_seat
...
        # replace select_provider(provider) branch with:
        name = resolve_for_seat("chat", OPERATOR_CONFIG) if provider in (None, "auto") else provider
        self.provider = as_operator(default_registry().resolve(name))
```

Coordinator's call — not required for the contract landing.

---

## Verification after applying

```bash
cd ~/workspace/levi
python3 -m pytest tests/test_operator_contract.py tests/test_agent_loop.py tests/test_agent_chat.py -q
```

Expected: the operator contract suite stays green; loop/chat suites
behave identically (provider names, ChatResponse shapes unchanged).

## What is deliberately NOT wired here

- `bot/services.py`, `growth/cycle.py` — sibling worker E's files;
  same one-line `as_operator` pattern applies when the coordinator
  is ready.
- Twin-pair seats (`resolve_twin`) — structural support exists in
  `levi.operator.registry`; no call site wires it until Chauncey
  decides the twin architecture (merge/judge is GATED regardless).
- The dynasty integrated-intelligence adapter is untouched and stays
  the separate foreign-mind concept (not XI, not relabeled).

---

## Twin-pair on-demand — one-line integration (ratified 2026-09-18)

Chauncey ratified the hybrid choice: twin mode `"on_demand"` is the
standing default. `levi.operator.twins.run_twin_turn` is the
seat-level orchestrator (Track 1, 2026-09-18). **Do NOT edit
`agent/loop.py` or `agent/chat.py` directly for this** (sibling worker
MM has both files modified) — apply the pattern below to the loop/chat
seats only after their changes land.

One-line call shape:

```python
from levi.operator.twins import run_twin_turn

turn = run_twin_turn(registry, "chat", messages, tools, context, OPERATOR_CONFIG)
# surface: turn.arrival.banner() when turn.arrival is not None
# text: turn.merged_result.text
```

Config surface (add to `OPERATOR_CONFIG`):

```python
OPERATOR_CONFIG["twins"] = {
    "mode": "on_demand",   # ratified default; may also be "always" or "off"
    "seats": {
        "chat": {"primary": "levi-brain", "verifier": "rules-engine"},
        "loop": {"primary": "levi-brain", "verifier": "rules-engine"},
    },
}
```

Seat behavior after wiring:

- Trivial/normal stakes -> single operator, NO fork, `turn.arrival is
  None`. Zero behavior change on bulk turns.
- High stakes (`assess_stakes(...) == "high"`) OR
  `context["force_twin"] is True` -> fork. Surface the arrival banner
  VERBATIM: `turn.arrival.banner()` —
  e.g. `Second mind 'rules-engine' joined — high-stakes turn (stakes
  assessed high).`
- `turn.needs_user_judge` False (VERIFIED) -> `turn.merged_result.text`
  is the reply (primary text + verifier concurrence).
- `turn.needs_user_judge` True (CHALLENGED) -> show BOTH
  `turn.primary_result.text` and `turn.verifier_result.text` framed as
  "your call"; do NOT auto-merge. When the user picks, feed the growth
  loop:

  ```python
  from levi.operator.twins import record_pick
  record_pick(turn.disagreement_id, winner_name, growth_store)
  ```

Full inverse-twin merge/judge stays GATED (Chauncey has not defined
"inverse") — `levi/operator/twins.py` contains no inverse semantics by
design; only the ratified interim (concur -> auto-merge, challenge ->
user judges).
