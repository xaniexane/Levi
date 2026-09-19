# LEVI Observability — the decision-trace corpus

Every bloodstream turn round-trips into an **append-only decision-trace
corpus**: one JSON object per line, rotated daily, queryable from the CLI.
This is the organism's memory of its own decisions — which stages ran,
what each decided, what tools fired, which risk ceilings applied, and how
each turn ended.

## Layout

```
~/.levi/observability/
    traces-2026-09-16.jsonl
    traces-2026-09-17.jsonl
    ...
```

* Directory is created owner-only (`0o700`); each day-file is created
  `0o600`. Traces are LEVI's private diary, not a shared log.
* Rotation is by date (UTC): `traces-YYYY-MM-DD.jsonl`. No pruning is
  done — the corpus is the training/evolution substrate, keep it.

## Schema (`core/levi/observability/schema.py`)

One `TurnTrace` per turn:

| field | meaning |
|---|---|
| `turn_id` | the bloodstream trace id (joins to `~/.levi/traces/`) |
| `ts` | UTC ISO-8601 timestamp |
| `session_id` / `route` / `persona_id` / `provider` | turn context |
| `stages[]` | every stage traversed: `stage`, `decision`, `duration_ms`, `risk_ceiling`, `detail` (redacted) |
| `tool_calls[]` | `name`, `params_hash` (SHA-256 over the **redacted** params), `params` (redacted), `arg_names` |
| `risk_ceiling` | effective (strictest) risk for the turn |
| `outcome` | `success` \| `denied` \| `failed` \| `awaiting_permission` |
| `reason` | human-readable why (e.g. denial / failure cause) |
| `raw_outcome` | bloodstream outcome verbatim (`replied`, `denied`, `governed`, …) |
| `text_excerpt` | first 200 chars of the user text |
| `receipt_id` / `error` / `composted` | policy receipt, failure summary, REIM compost flag |
| `duration_ms` | whole-turn wall clock |
| `schema_version` | `1` |

Stage `duration_ms` is `null` when the pipeline didn't measure that stage
— honest absence, never an invented number.

## Emission (`core/levi/observability/hook.py`)

`emit_turn_trace(result, text, ...)` is the **single additive call site**,
invoked at the end of `levi.bloodstream.turn._finish` — the choke point
every turn exits through. It:

1. builds a `TurnTrace` via `from_bloodstream` (duck-typed; the
   observability package never imports the bloodstream package),
2. appends it to the `TraceStore`.

It **never raises** into the pipeline and never changes what the turn
does. If the observer breaks, the organism keeps breathing.

Stage timings come from lightweight additive instrumentation in
`turn.py` (`@_timed_stage` on the stage functions, plus the policy gate,
memory, and trace sections). Per-stage risk ceilings are read out of the
stage detail dicts the pipeline already records (`effective_risk`,
`risk`).

## Secret safety (`core/levi/observability/redact.py`)

Structural, not aspirational:

* Values under secret-named keys (`password`, `token`, `api_key`, …) are
  replaced with `***REDACTED***`.
* Values *shaped* like secrets (long opaque blobs, `sk-…`/`xox…` tokens,
  `Bearer …` headers) are replaced even under innocent key names.
* `params_hash` hashes the **redacted** canonical form — a hash of a raw
  secret would still be brute-forceable, so raw params are never hashed.

Raw secret values never reach the corpus. Stage detail dicts are redacted
the same way.

## Query surface

### Entrypoint (available now)

```bash
python -m levi.observability recent [--limit 20]
python -m levi.observability show <turn_id>
python -m levi.observability filter [--outcome denied|failed|success|awaiting_permission] \
    [--min-risk 3] [--route model] [--limit 50]
python -m levi.observability stats
```

Add `--json` for full records, `--home DIR` to point at another LEVI
home (tests use this).

### Python API

```python
from levi.observability import TraceStore

store = TraceStore()  # ~/.levi/observability
store.recent(limit=20)
store.get("ab12cd34ef56")
store.filter(outcome="denied", min_risk=3)
store.stats()
```

### CLI integration (`levi observe` — pending)

`core/levi/cli/main.py` is owned by a sibling crew's in-flight work, so
the top-level `levi observe` command is **not wired yet**. When that file
is free, add one delimited region (following the existing region
convention, e.g. `# === OBS-REGION-BEGIN ===`):

```python
# === OBS-REGION-BEGIN: observability query surface ===
try:
    from levi.observability import __main__ as _obs

    obs_p = sub.add_parser("observe", help="Query the decision-trace corpus")
    obs_sub = obs_p.add_subparsers(dest="observe_cmd", required=True)
    # ... mirror _obs.build_parser() subcommands, or delegate:
    # args.func = lambda a: _obs.main([...])
except Exception:
    pass  # observe degrades: CLI boots without the corpus
# === OBS-REGION-END ===
```

and a dispatch branch mapping `args.command == "observe"` to the
entrypoint's `main()`. The entrypoint is the contract; the wiring is
mechanical.

## Relation to `levi.bloodstream.trace`

The bloodstream's own `TraceWriter` (`~/.levi/traces/YYYY-MM-DD.jsonl`)
is the pipeline's internal flight recorder — raw stage records for the
turn itself. The observability corpus is the **queryable, schema'd,
secret-safe** layer on top: normalized outcomes, timings, tool-call
fingerprints, and a real query API. Both are written per turn; they join
on `turn_id` / `trace_id`.

## Tests

`tests/test_observability.py` — hermetic (tmp HOME, synthetic fixtures):

* full turn round-trips into the corpus and is queryable (get / recent /
  filter / CLI)
* denied turns record the risk ceiling (`risk=3`, policy stage ceiling)
* secret-shaped param values never persist; hashes are redacted-shape-stable
* store rotation, `0o700` dir / `0o600` files, corrupt-line resilience
* the hook never raises, even against an unwritable base dir
