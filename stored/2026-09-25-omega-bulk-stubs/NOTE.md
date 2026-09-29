# Why these files are stored (not deleted)

Date moved: 2026-09-25
Provenance: commit `328c554e` ("Omega bulk import: 10,000 catalog stubs as
omega-bulk pack"), Agent-Glyph 📦, Factory Genesis era.

## What was here
- `omega_bulk_skills.py` — data-driven registry pack loader (stdlib only).
- `omega_bulk_data.jsonl` — 10,000 selected Omega archive entries (JSONL).
- `test_omega_bulk_skills.py` — 6 proof tests for the pack (were green).

## Why moved out of the live tree
Chauncey rejected registry stubs outright ("no stubs", 2026-09-25 ~00:30 CDT).
He wants a real database of skills instead of stub registrations inflating the
registry count. The live registry was returned to its 1,233 real skills, and
the stub pack was unregistered (registry.py wiring reverted).

## What replaces it
The SQLite skills library at `core/levi/skill/skilldb.py` (Agent-Glyph 🗄️,
same day): the 10,000 selected entries live on there as `status='candidate'`
with `priority=1`, and the full 258,355-entry Omega archive is seeded as
refinement candidates. Nothing of the selection work was lost — the exact
10,000 triaged ids are recoverable from `omega_bulk_data.jsonl` in this
directory (the `id` field of each line).

## Integrity
- Parked source zip untouched: `~/workspace/parked/reference-zips/omega-complete.zip`
  (md5 `680855ca2f4e08951cddfb45d7816390`, verified before and after).
- Selection rule (from the 📦 worker's module docstring, preserved in
  `omega_bulk_skills.py`): 250 stride-sampled representatives of the 25,000
  identical SI micro-op instruction block + 9,750 largest-remainder
  proportional across 5 description families, preferring longer instructions.

Nothing was deleted. This directory is the record.
