# Survivability Catalog

One question, answered for every capability LEVI offers: **what keeps it alive
when the network dies?**

`core/levi/survivability/` holds a machine-readable catalog of LEVI's fallbacks
and degraded modes. Each entry names the capability, the primary path, the
fallback path, what the user loses in degraded mode (in plain language), and
whether it survives fully offline.

## Usage

```bash
# from the repo root, with PYTHONPATH=core
python -m levi.survivability list
python -m levi.survivability list --format json
python -m levi.survivability check        # verify every fallback is present
```

Or from Python:

```python
from levi.survivability import catalog, check_all, get

for entry in catalog():
    print(entry["id"], entry["offline_ok"])

for result in check_all():
    print(result["id"], "OK" if result["ok"] else "MISSING: " + result["detail"])

print(get("finance-broker")["degraded_mode"])
```

## Entry schema

| field | meaning |
|---|---|
| `id` | stable machine name |
| `capability` | what the user experiences |
| `primary_path` | how it normally works (online/optimal) |
| `fallback_path` | what takes over when the primary is unavailable |
| `degraded_mode` | what the user loses, in plain language |
| `offline_ok` | `True` if the capability survives with zero network |
| `verify` | how `check` confirms the fallback exists: `{"kind": "import", "target": "levi.x"}` or `{"kind": "path", "target": "core/levi/..."}` |

Entries are plain dicts — stdlib, serializable, no magic. Add new ones to
`ENTRIES` in `core/levi/survivability/catalog.py`.

## Seeded entries (12)

- **agent-provider-chain** — chat/tasks. Primary: best LEVI-family weight
  (`levi-brain`/`levi-local`). Fallback: deterministic rule-based planner.
  Degraded: canned pattern-matching answers. Offline: yes.
- **local-model-runner** — GGUF inference via llama-server. Fallback: rules
  engine, no model process. Offline: yes.
- **native-brain-weights** — LEVI's own trained weights. Fallback: rules-only
  provider mode. Offline: yes.
- **finance-broker** — paper trading on `SimulatedBroker`. Live transport is
  deliberately unwired, so there is nothing to fall back *from*. Paper-only by
  design. Offline: yes.
- **news-ingestion** — RSS refresh (BBC/Reuters/AP/HN/arXiv). Fallback: cached
  dated corpus. Degraded: stale corpus, no refresh. Offline: yes.
- **courses-knowledge** — local awesome-courses catalog. Fully local already.
  Offline: yes.
- **growth-loop** — harvest → reflect → consolidate. Fallback: rule-based
  offline reflection. Degraded: conservative heuristic learnings only.
  Offline: yes.
- **skills-registry** — frontmatter-based registration, needs only markdown on
  disk. Offline: yes.
- **cyber-playbooks** — 823 defensive playbooks on disk. Offline: yes.
- **control-plane** — local approvals ledger. Fallback: manual deny/approve via
  CLI. Offline: yes.
- **king-orchestration** — cross-organ orchestration. Fallback: direct CLI per
  subsystem. Offline: yes.
- **eula-linter** — rule-based terms scanning, zero dependencies. Offline: yes.

## The `check` command

`check` is the honest part: it doesn't just *claim* a fallback exists, it
imports the module or stats the path. Exit code is 0 only when every fallback
is present; failures name the missing piece. Run it in CI and after any
refactor that moves modules around — a renamed file that silently breaks a
fallback is exactly what this catches.

## Design notes

- The catalog is a **map**, not a mechanism — it documents and verifies, it
  doesn't implement failover. The failover logic lives in each subsystem.
- `offline_ok` is a claim verified by `check`, not a vibe. If an entry can't
  prove its fallback exists, it fails the check until fixed.
- When adding a capability to LEVI, add a survivability entry with it: primary,
  fallback, degraded mode, and a `verify` spec. No entry, no ship.
