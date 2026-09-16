# Context Snapshots

**Suspend/resume for life.** One command captures your full working
state so any interruption — sleep, a phone call, a lost terminal — is
resumable later from exactly where you stopped.

## Purpose

Humans lose context when life interrupts. LEVI shouldn't. A snapshot
records everything needed to resume: open commitments, open tracked
items, the git working state of a repo, the tail of the growth journal,
and the current focus/mode. `resume` renders a plain-language brief of
*what was open and what was next*.

This is a LEVI-native addition: no external service, no cloud sync —
local JSON under the LEVI home.

## API

```python
from levi.snapshots import capture, resume, resume_brief, list_snapshots, drop

snap = capture("before-lunch", repo_dir="/path/to/repo",
               focus="finish the drift instrument", mode="build",
               notes=["tests green, docs remain"])
print(resume_brief(resume("before-lunch")))
print(list_snapshots())   # [{"name": ..., "captured_at": ...}]
drop("before-lunch")
```

Or the store class for pinned homes:

```python
from levi.snapshots import SnapshotStore
store = SnapshotStore(home="/tmp/test-home")
store.set_focus(" Teachback tests ")   # persisted; later captures pick it up
store.capture("v1")
```

### What capture() records

| Field | Source | When missing |
|---|---|---|
| `commitments` | `~/.levi/commitments/commitments.json` | `"none"` |
| `tracked_items` | local tracked/goals item files (best effort) | `"none"` |
| `repo` | `git branch --show-current` + `git status --porcelain` summary (top 10 lines) | `"none"` if not a repo |
| `journal_tail` | last 5 entries of `~/.levi/growth/journal.jsonl` | `"none"` |
| `focus` / `mode` / `notes` | caller args (+ persisted focus file) | `null` / `[]` |

Honest contract: missing stores are recorded as `"none"` — never
invented. `resume("unknown")` raises `KeyError`.

Home resolves at call time: `LEVI_HOME` env → `~/.levi`.

## CLI

```
python -m levi.snapshots capture NAME [--repo DIR] [--focus F] [--mode M] [--note ...]
python -m levi.snapshots resume  NAME
python -m levi.snapshots list
python -m levi.snapshots drop    NAME
python -m levi.snapshots focus   [TEXT]   # set / show persisted focus
```

## Suggested instinct specs (for the instincts engine)

- **snapshot-before-long-task**: before any task estimated ≥ 30 minutes,
  capture a snapshot named `pre-<task-slug>`. On failure/interruption,
  the resume brief is the first thing consulted before retrying.
- **snapshot-on-interrupt**: when the daemon is asked to pause or the
  session is about to end, capture `pre-interrupt` automatically.
- **resume-on-start**: when a session opens, check for a snapshot named
  `pre-interrupt` and offer the resume brief instead of asking "what
  were we doing?".

## Tests

`tests/test_snapshots.py` — hermetic (tmp LEVI_HOME, real throwaway git
repo in tmp, no network). Covers: capture/resume round-trip with real
git summary, honest empty states, list/drop, call-time home resolution,
persisted focus pickup.
