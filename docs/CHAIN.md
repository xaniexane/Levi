# CHAIN — LEVI-native chain composition

Chains compose **compressed engines** into ordered pipelines:

```
model → parser → tool → memory
```

A chain is an ordered list of `Link`s. Each link wraps a plain callable
and declares a `RiskBand`:

| Band | Meaning |
|---|---|
| `SAFE` | Pure compute, no side effects. Runs straight through. |
| `CONSEQUENTIAL` | Can change the world. Walks the full rail **in code**. |

The standing rail for consequential links — enforced by the framework,
not by convention:

```
Plan → Preview → Permission → Execute → Verify → Receipt
```

- **Plan** — what the link intends to do (its `describe`, or fn docstring).
- **Preview** — the input it will see, and whether a world-effect is possible.
- **Permission** — the gate. The link **cannot execute without a recorded
  permission token**. No token → the link is denied, the chain stops
  fail-closed, and the refusal itself is receipted.
- **Execute** — the callable runs; exceptions fail the link, fail-closed.
- **Verify** — an optional `verifier(output)` callable must accept the output.
- **Receipt** — every execution (and every denial) is appended to the
  receipt ledger: `<LEVI_HOME>/chain/receipts.jsonl`, owner-only (0600).

Safe links run the same rail minus the permission gate.

Chains build **on** `levi.automation.flows` — they do not duplicate it.
`ChainError` subclasses `FlowError`, and `flow_link()` embeds a validated
flow as a single chain link (consequential by default, so the flow still
needs a recorded token to run).

## Quick start (runnable)

```python
import os

os.environ["LEVI_HOME"] = "/tmp/levi-chain-demo"  # keep the demo hermetic

from levi.chain import (
    RiskBand,
    build_chain,
    grant,
    link,
    run_chain,
)


# --- compressed engines, each a plain callable ---------------------------
@link(name="model")  # SAFE: pure compute
def model(prompt):
    return f"draft about {prompt}"


@link(name="parser")  # SAFE: pure compute
def parser(draft):
    return {"title": draft.split(" about ")[-1], "body": draft}


@link(
    name="tool",
    risk=RiskBand.CONSEQUENTIAL,
    describe="publish the parsed draft to the local bulletin",
)
def tool(doc):
    # a real world-effect would happen here; the demo just records it
    return {**doc, "published": True}


@link(name="memory")  # SAFE: pure compute
def memory(doc):
    return f"remembered: {doc['title']}"


chain = build_chain([model, parser, tool, memory], id="publish-pipe")

# --- the gate holds without a recorded permission token ------------------
denied = run_chain(chain, "levi")
print(denied.ok)  # False — 'tool' refused, nothing published
print(denied.render())

# --- record a permission token, then run ---------------------------------
token = grant("tool", by="keeper", scope="publish-pipe", note="demo: allow one publish")
receipt = run_chain(chain, "levi", permissions=[token])
print(receipt.ok)  # True
print(receipt.output)  # remembered: levi
print(receipt.render())
```

Run it: `PYTHONPATH=core python3 docs_chain_demo.py` from the repo root
(any file — the snippet above is self-contained).

## Public interface

From `levi.chain`:

- `RiskBand` — `SAFE` / `CONSEQUENTIAL` (a `str` enum; plain `"safe"` /
  `"consequential"` strings coerce).
- `Link(name, fn, risk=RiskBand.SAFE, label="", describe="", verifier=None)` —
  one chain step. `fn(value) -> value`; `verifier(output) -> bool`, optional.
- `link(name=None, risk=..., label="", describe="", verifier=None)` —
  decorator turning a function into a `Link`.
- `PermissionToken(token_id, link_name, granted_by, scope, ts, note="")` —
  a recorded grant. `link_name`/`scope` accept `"*"` wildcards.
- `grant(link_name, *, by="keeper", scope="*", note="", home=None)` —
  mint **and record** a token in the permission ledger; returns the token.
- `build_chain(links, id, name="", description="")` — validate and assemble.
  Deny-closed: duplicate names, non-callables, bad bands, empty lists refused.
- `run_chain(chain, data, *, permissions=(), grantor=None, home=None)` —
  thread the value through the links, in order. Stops fail-closed at the
  first denied/failed link. Returns a `ChainReceipt`.
- `grantor` — optional `Callable[[Link, plan, preview], PermissionToken | None]`;
  asked at runtime during the permission stage. Its grant is recorded on the spot.
- `flow_link(flow, *, name=None, label="", risk=CONSEQUENTIAL, dry_run=True, describe="")` —
  embed a validated flow dict as one link (validated by `build_flow`, run by
  `run_flow`; output is the flow's `FlowReceipt`).
- `Chain`, `ChainReceipt`, `LinkReceipt` — records; `.to_dict()` / `.render()`.
- `ChainError` — subclasses `FlowError`.
- `chain_home(home=None)`, `receipts_path(home=None)`, `permissions_path(home=None)` —
  storage locations (`LEVI_HOME` env or `~/.levi`, explicit `home` wins).
- `read_receipts(home=None, limit=None)`, `read_permissions(home=None)` —
  read the ledgers, oldest first.

`RAIL` / `SAFE_RAIL` expose the stage tuples for tooling.

## Permission resolution order

For each consequential link: explicit `permissions` → `grantor` callback →
on-disk permission ledger. First matching token wins; none means denied.

## Honest limits

- Tokens are **reusable within their scope** (link name and/or chain id, or
  `"*"`). One grant covers repeated runs until you stop granting. Scope
  narrowly (`scope="<chain-id>"`) for one-off jobs.
- `verify` only runs a link-local `verifier` if you supply one; there is no
  global output schema check.
- Chains are linear: for branching graphs, embed `flow_link`s or use
  `levi.automation.flows` directly.
- The receipt ledger is append-only; there is no redaction API — treat
  link outputs as local records, not secrets, or scrub before emitting.
