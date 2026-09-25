# Fleet-Five — Capped Delegation

The fleet pattern, LEVI-native: convene **at most 5 specialists**, each
contributing **exactly one section**, fold everything into **ONE report**,
then disband. No standing army — after the fold there is no fleet state
left behind.

## The pattern

A task that deserves parallel thinking but not a standing crew gets a
*fleet*: a bounded, temporary set of specialists that think in sequence,
each in a fixed role, each producing one section of the final report.
When the last section lands, the scribe folds the report and the fleet
is gone. The only durable output is the report the caller keeps.

```
task
 │
 ▼
summon          validate cap + specs (6th specialist → refused)
 │
 ▼
architect       interfaces, plan, decomposition
implementer     the smallest working slice
critic          weaknesses — what breaks, what kills it
scope_warden    scope freeze — what is IN, what is OUT
scribe          digest — the folded summary you act on
 │
 ▼
fold            ONE report dict; the fleet disbands (no state written)
```

## The roles

| Role | Mandate | Contributes |
|---|---|---|
| `architect` | Interfaces, plan, and decomposition of the task | one section: the shape of the work |
| `implementer` | The smallest working slice that actually works | one section: the minimal construction |
| `critic` | Weaknesses — what breaks, what is wrong, what kills the slice | one section: the attack |
| `scope_warden` | Scope freeze — IN vs OUT and the boundary | one section: the fence |
| `scribe` | Digest — the folded summary the caller acts on | one section: the report you read |

Roles contribute in this fixed order regardless of the order you pass
them in. Partial fleets (fewer than 5) are allowed: the report names
which roles were present and which are missing, honestly.

## The cap and why it is hard

`MAX_SPECIALISTS = 5`. This is structural, not a suggestion:

- **Requesting a 6th specialist raises a clear error** (`FleetError`, a
  `ValueError`). The cap is never silently bent.
- **A task that needs more than 5 is REFUSED with guidance to split it**
  into smaller tasks (one fleet per piece), never silently truncated to
  fit. Passing `task_size="large"` declares a task oversize and triggers
  the refusal.
- **Duplicate roles are rejected**: one specialist, one section.

Why 5? A delegation mechanism that grows without bound becomes a
standing army — persistent agents with persistent state, coordination
overhead, and nobody responsible for the fold. Five is small enough that
one folded report stays readable and one disband is cheap, and large
enough to cover the roles that matter (plan, build, attack, fence,
digest). If 5 is not enough, the task is two tasks — the mechanism
forces that honesty instead of hiding it.

## Honesty rules

- **No fabricated contributions.** Sections come from the caller (the
  real specialists: subagents, operators, fixtures). A spec with no
  `contribution` is rejected — fleet-five folds real work, it never
  invents a specialist's voice.
- **Failures are refusals, not silent edits.** Bad task, bad spec, cap
  breach, oversize task: all surface as clear errors (or `ok=False`
  with a reason through `run_workflow`).
- **The fold leaves no state behind.** Nothing is written to the home
  dir; the report exists only in the result the caller keeps. Re-runs
  never accumulate.

## Usage

As a workflow (registered as `fleet-five`):

```python
from levi.workflows import run_workflow

result = run_workflow(
    "fleet-five",
    task="Design the nightly archive sweep",
    specialists=[
        {"role": "architect", "focus": "warehouse indexing", "contribution": "..."},
        {"role": "implementer", "contribution": "..."},
        {"role": "critic", "contribution": "..."},
        {"role": "scope_warden", "contribution": "..."},
        {"role": "scribe", "contribution": "..."},
    ],
)
report = result["artifacts"]["report"]
print(report["digest"])
```

Direct (raises `FleetError` on violations):

```python
from levi.workflows.fleet_five import run_fleet

report = run_fleet(task, specialists)  # one folded report dict
```

The report dict:

```python
{
    "report": "fleet-five",
    "task": <the task>,
    "fleet_size": 5,
    "sections": [{"index", "role", "mandate", "focus", "content"}, ...],
    "digest": <the scribe's section, verbatim>,
    "roles_present": [...],
    "roles_missing": [...],
    "folded": True,
}
```

## How this differs from `levi.fleet`

`levi.fleet` (supervisor / swarm) is the durable digital-workforce
machinery: plan DAGs, blackboards, ledgers, budgets — for work that
spans many subtasks and needs ongoing coordination. Fleet-five is the
opposite end: one task, at most five voices, one report, zero residue.
Use the swarm when the work outlives the answer; use fleet-five when the
answer is the work.

## Laws observed

stdlib-only, local-first, no free core (dollar-scale entry; "free core forever"
killed 2026-09-17). Additions lens: fleet-five
adds a new bounded-delegation primitive LEVI owns; it rewrites nothing.
