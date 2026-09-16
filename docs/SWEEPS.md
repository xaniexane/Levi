# SWEEPS — broken-window sweeps

**Purpose.** Periodic tiny-fix sweeps of accumulated small messes.
The labor directive says tedious cleanup is LEVI's favorite meal;
sweeps are how it eats: registered specs with a `check` half (list
issues) and a `fix` half (repair one), run against an explicit root.
Safe specs auto-fix; unsafe specs are reported and never auto-run.

**Why it exists.** Broken windows compound: stale bytecode, empty
directories, and fossilized tmp files each cost nothing alone and
signal "nobody tends this place" together. A sweep is the opposite
of a heroic cleanup — small, scheduled, boring, and therefore
actually done.

## Safety contract (binding)

- `run_sweep` requires an **explicit `root`**. There is no default
  that resolves to the real repo or the real home.
- `/`, the real `$HOME`, and the LEVI repo root itself are **refused
  outright** (`SweepRefusedError`). Nothing runs there.
- Every issue path is verified to stay **inside root** (no `..`
  escapes). Escapes are reported as errors and never followed.
- `safe=True` means: purely local, reversible-or-regenerable, no
  deletions outside the explicit root. **Unsafe specs are checked
  and reported; their fixes never run automatically.**
- The report is honest about everything: `{fixed, remaining,
  skipped_unsafe, errors}`. A failed fix lands in `remaining`, not
  silently in `fixed`.

## Built-in sweeps (all safe)

| id | what it does | why it's safe |
|---|---|---|
| `stale-pycache` | removes `__pycache__` dirs older than N days | Python regenerates bytecode on next import |
| `empty-dirs` | removes empty dirs (never the root itself, never `__pycache__`) | an empty dir holds no data |
| `stale-tmp-files` | removes `*.tmp`/`*.bak`/`*.swp`/`~`-style files older than N days | disposable by definition |

All three are scoped to the explicit root the caller passes. In
tests that root is always a tmp dir — never the real tree.

## API

```python
from pathlib import Path
from levi.sweeps.sweeps import (
    SweepSpec, register, unregister, list_specs, run_sweep,
    SweepRefusedError,
)

# Register your own spec. safe=False specs are reported, never auto-run.
def check(root: Path, max_age_days: float) -> list[str]:
    return ["stale/report.txt"] if (root / "stale/report.txt").exists() else []

def fix(root: Path, issue: str) -> bool:
    (root / issue).unlink()
    return True

register(SweepSpec(id="my-sweep", area="reports",
                   description="drop stale reports",
                   check=check, fix=fix, safe=True))

report = run_sweep(Path("/data/scratch"), max_age_days=7)
# report.fixed / .remaining / .skipped_unsafe / .errors
print(report.format())
unregister("my-sweep")

list_specs()     # all registered specs, sorted by id
```

`run_sweep(root, only=[...])` runs a subset. `check` receives
`(root, max_age_days)` and returns issue paths **relative** to root;
`fix` receives `(root, issue)` and returns True when repaired.

## CLI

```bash
python -m levi.sweeps list
python -m levi.sweeps run /data/scratch [--only stale-pycache empty-dirs] \
    [--max-age-days 7] [--json]
# run /  or  run ~  -> refused, exit code 2
```

## Suggested instinct specs

```yaml
# Monthly hygiene: safe sweeps on the data root, report only.
- id: instinct.sweep_monthly
  fires_on: sweeps.days_since_last>=30
  cooldown: 2592000       # ~30 days
  max_grade: NOTE
  does: run_sweep on the configured data root; report fixed/remaining/skipped_unsafe

# If unsafe specs keep finding issues, ask a human instead of auto-fixing.
- id: instinct.sweep_unsafe_backlog
  fires_on: sweeps.unsafe_open>=3
  cooldown: 604800
  max_grade: ASK
  does: list unsafe specs with open issues; ask whether to handle manually
```

**Storage:** none — sweeps are stateless; the registry lives in
process. **Deps:** stdlib only.
