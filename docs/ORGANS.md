# Organs — the four branching organs

LEVI's organism model names four branching organs: **echoverse**, **mandella**,
**reim**, and **riem**. They explore possibility space, choose under pressure,
compost failure, and grow a genome from the compost — all deterministic,
hash-seeded, stdlib-only, local-first, and defensive in posture.

## The four organs

| Organ | Entry point | Job |
|---|---|---|
| `echoverse` | `levi.organs.echo:run_echo` | Branch exploration: taken / not-taken / wild parallel paths for a seed |
| `mandella` | `levi.organs.mandella:run_mandella` | Stake selection under domain pressure; the unchosen options linger as named phantoms |
| `reim` | `levi.organs.reim:compost_failure` | Compost failure: extracts lesson, inverse map, compost class, reusability |
| `riem` | `levi.organs.riem:promote` | Compost → genome: emits genome *proposals* for eligible compost records |

All organs are pure functions: same input → same output, no writes, no
network, no side effects. They are dispatched deny-closed through
`levi/organs/registry.py` (`run_organ` raises `ValueError` on unknown names)
and are runnable via `python -m levi.organs`.

## The Echoverse naming note

There is **no** `levi/organs/echoverse.py`, and there must not be one. The
branch-exploration organ already exists as `run_echo` in
`levi/organs/echo.py`, whose docstring records the history: a prior lineage's
competing `graph/echoverse.py` was rejected at merge time to avoid two
implementations of the same concept. Reintroducing a separate echoverse.py
would repeat the exact mistake the merge fixed.

The registry therefore maps the organ name `"echoverse"` to the existing
`run_echo` entry point (imported, not reimplemented):

```python
from levi.organs.registry import run_organ

run_organ("echoverse", seed="ship the release", cycles=3)
```

## Contracts

### echoverse — `run_echo(seed: str, cycles: int = 3) -> dict`

- Input: `seed` (string), `cycles` (non-negative int). ValueError otherwise.
- Output: `{"seed", "branches" (3, taken/not-taken/wild with label, summary,
  risk), "insight", "organ": "echo"}`.

### mandella — `run_mandella(domain: str = "build", seed: str = "") -> dict`

- Input: `domain` (one of `crisis | resource | trust | identity | build |
  write | security | product`; unknown domains fall back to `build`),
  `seed` (string). ValueError on non-string inputs.
- Output: `{"organ": "mandella", "domain", "premise", "options" (label, risk,
  note), "recommended", "seed"}`. The not-chosen options are the phantoms.

### reim — `compost_failure(record: dict) -> dict`

Failure input schema (all required; fail-closed `ValueError` on malformed):

| Key | Type | Notes |
|---|---|---|
| `source` | non-empty string | where the failure happened (component, pipeline, organ) |
| `what` | non-empty string | what failed |
| `context` | non-empty string | surrounding circumstances |
| `ts` | non-empty string | timestamp (ISO-8601 recommended) |
| `severity` | string | one of `low` / `medium` / `high` |

Output (compost record):

| Key | Meaning |
|---|---|
| `organ` | `"reim"` |
| `source`, `what`, `context`, `ts`, `severity` | echoed back |
| `compost_class` | `flaky-input` / `wrong-assumption` / `missing-guard` / `resource-exhaustion` / `unknown` (deterministic keyword rules; first matching rule wins, no match → `unknown`) |
| `lesson` | one-line lesson (deterministic per-class phrasing variant) |
| `inverse_map` | what the mirror-image success looks like |
| `reusable` | `True` only when classifiable (not `unknown`) and severity is `medium` or `high` |
| `corroboration` | `1` (fresh compost starts uncorroborated) |
| `fingerprint` | sha256-derived stable id of the failure |
| `provenance` | `{organ: "reim", source, ts}` |

### riem — `promote(compost_records: list[dict]) -> list[dict]`

Takes REIM compost records (all required compost keys, recognized
`compost_class`). Ineligible records are *skipped*, not raised: a record
promotes only when it is `reusable` **and** (`corroboration >= 2` **or**
`severity == "high"`). Unknown `compost_class` values raise `ValueError`
(fail-closed).

Genome proposal schema (data, not writes):

| Key | Meaning |
|---|---|
| `kind` | `procedural-memory` / `checklist-item` / `guard-rule` (fixed mapping from compost class: input/guard/resource failures → `guard-rule`, wrong assumptions → `checklist-item`, unknowns → `procedural-memory`) |
| `content` | the proposed text |
| `confidence` | `high` (severity high + corroboration ≥ 2) / `medium` / `low` |
| `fingerprint` | stable id derived from the source compost fingerprint |
| `provenance` | `{organ: "riem", compost_fingerprint, source, ts, corroboration}` |
| `applied` | always `False` — RIEM never writes; application is a human decision |

## Data formats

Failure records and compost records are plain JSON-serializable dicts. The
same shapes flow through the CLI, e.g.:

```bash
# list organs
python -m levi.organs list

# run echoverse / mandella
python -m levi.organs run echoverse --seed "ship the release"
python -m levi.organs run mandella --domain security --seed "deploy friday"

# compost a failure (record via --kwargs-json)
python -m levi.organs run reim --kwargs-json \
  '{"record": {"source": "ci", "what": "build timed out on test step",
               "context": "runner queue was full during release",
               "ts": "2026-09-15T19:00:00Z", "severity": "high"}}'

# promote compost (records via --kwargs-json); --json for machine-readable output
python -m levi.organs run riem --kwargs-json '{"compost_records": [...]}' --json
```

## Example flow: failure → compost → genome proposal

```python
from levi.organs.registry import run_organ

failure = {
    "source": "deploy-pipeline",
    "what": "deployment failed: config assumed staging URL in production",
    "context": "Friday deploy, no pre-flight check ran",
    "ts": "2026-09-15T19:00:00Z",
    "severity": "high",
}

compost = run_organ("reim", record=failure)
# compost_class == "wrong-assumption", reusable == True,
# lesson: "Turn the broken assumption into an explicit, verified precondition."

# A second, independent failure with the same root cause corroborates it.
failure2 = {
    "source": "oncall-runbook",
    "what": "rollback assumed the old config format and wiped settings",
    "context": "incident at 3am, runbook trusted stale assumption",
    "ts": "2026-09-15T19:30:00Z",
    "severity": "medium",
}
compost2 = run_organ("reim", record=failure2)
compost2["corroboration"] = (
    2  # corroboration is external evidence, counted by the caller
)

proposals = run_organ("riem", compost_records=[compost, compost2])
# -> [{"kind": "checklist-item", "confidence": "high", "applied": False, ...}]
#    (high severity)                                    (corroboration >= 2)
```

The proposal is data: LEVI (or a human) decides whether to adopt it into
procedural memory. REIM/RIEM never auto-apply, never write, and never guess
— every step is deterministic and reproducible from the input record.
