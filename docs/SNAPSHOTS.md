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

snap = capture(
    "before-lunch",
    repo_dir="/path/to/repo",
    focus="finish the drift instrument",
    mode="build",
    notes=["tests green, docs remain"],
)
print(resume_brief(resume("before-lunch")))
print(list_snapshots())  # [{"name": ..., "captured_at": ...}]
drop("before-lunch")
```

Or the store class for pinned homes:

```python
from levi.snapshots import SnapshotStore

store = SnapshotStore(home="/tmp/test-home")
store.set_focus(" Teachback tests ")  # persisted; later captures pick it up
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

---

# Stage Snapshots

A different tool from the life-context snapshots above. A **stage**
snapshot captures an artifact tree — a boot camp at a named stage, a
client's system, a project config — so you can diff stages, restore,
fork-and-refine, recreate, and implement.

Immutability by construction: **content-addressed** (the id is the
SHA-256 of the canonical payload — capturing an identical payload
returns the identical snapshot), **hash-chained** (every snapshot MACs
the previous link with the keeper-held key), and **sealed at rest**
(Veil-lineage Encrypt-then-MAC, keeper key at `0600`). Tampering breaks
the seal or the chain, loudly. Originals are never mutated: fork creates
a child, restore writes to a target you name.

```bash
levi snapshot capture my-stage --payload-json '{"a":1}' --stage v1
levi snapshot list
levi snapshot diff <id-a> <id-b>        # added / removed / changed paths
levi snapshot restore <id> ./restored   # snapshot untouched
levi snapshot fork <id> refined-v2 --stage v2   # original untouched
levi snapshot recreate <id> --dest ./rebuilt
levi snapshot implement <id> --recipe report   # report | write
levi snapshot verify                    # whole chain
levi snapshot verify <id>               # one snapshot
```

## Boot camp stages (first client)

The academy's boot camp is the first client. A stage captures the
syllabus, schedule, lessons inventory (small files by content, large
files by hash + size), and module hashes — deterministically.

```bash
levi snapshot stage-capture "week-3-baseline" --note "before curriculum expansion"
levi snapshot stage-list
levi snapshot stage-diff <id-a> <id-b>
levi snapshot stage-restore <id> ./bootcamp-week-3
levi snapshot stage-fork <id> "week-3-refined"
```

## Snapshots as a service (`ops-snapshot`)

A first-class legion service type in the catalog: a client's system /
project / config is captured into versioned, restorable, refinable
artifacts — "we snapshot it; you can roll back, fork, or improve from
any stage."

Rides the standard pipeline (analyze → quote → deliver → paid →
showcase). Quotes ride the founder price advisor (a quote, not a
charge). Money rides the Cybrus gateway only, through the standard paid
stage.

```bash
levi snapshot service-offer levi "Snapshot client CRM config" /path/to/subject \
    --scope "config + docs" --client acme
levi snapshot service-quote <offering-id> --giant-price 299 --strategy volume
levi snapshot service-deliver <offering-id> /path/to/subject "v1-baseline"
```

Delivery emits a **service receipt**: snapshot id, payload hash, chain
verification count, and the exact restore / fork commands. The client
keeps rollback power forever.

## Honest limits

- Sealing is Encrypt-then-MAC with SHA-256 CTR keystream, not AES-GCM.
  It protects records at rest on this machine; it does not stop a
  key-file holder.
- Subject inventories record small text files by content and everything
  else by hash + size. Large binaries are referenced, not embedded.
- Symlinks are recorded, never followed. Unreadable files are recorded
  as unreadable, never invented.
- `implement` only runs caller-supplied recipes (`report`, `write`);
  anything else is the caller's code, not the engine's guess.
- Money is paper-only until a rail is registered: charges fail closed
  through the standard pipeline.
