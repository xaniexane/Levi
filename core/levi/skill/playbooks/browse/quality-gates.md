---
skill_id: browse.quality_gates
name: Quality Gates
description: Law to guard to prove — the mandatory gates every browse-layer commit passes: tests, lint, and commit discipline.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, quality, law-guard-prove, tests, lint]
version: 1.0.0
---

# Quality Gates

Every build declares its laws up front (the eight-laws playbook),
ships the guard (the machine check), and the commit gate requires the
proof to pass. "Proof" here means what it says below — never claim
"formally proven" when the proof is a test.

## Mandatory gates, every commit

1. **Laws declared.** The commit message or the module docstring names
   which of the eight laws the change serves — plus laws 9–11 for
   agent/credential work (`browse.agent_laws`). A change serving none
   is suspect.
2. **Tests, and they pass.** New behavior ships with tests in the
   builder's owned test file. `pytest` on the owned files is green —
   real counts in the receipt ("23 passed"), never "tests pass."
3. **Ruff clean.** `ruff check` and `ruff format --check` clean on
   every touched file. Scope the commands to exact files, never
   directories — directory-wide runs "fix" siblings' files.
4. **No-remote-fetch lint.** `scripts/check_no_remote_fetch.py` passes
   on the tree. Committed code pulls nothing from a remote host at
   runtime.
5. **Manifest-diff guard.** `browse/manifest_guard.py` passes: no
   capability contract narrowed without a recorded ruling.
6. **Honest-claims read.** The diff contains no blanket "secure",
   "private", or "anonymous". Per-mechanism graded claims only (see
   the honest-claims playbook).
7. **Commit discipline.** Hardened temp-index route: fixed
   `GIT_INDEX_FILE` path, `read-tree`, `TIP_BEFORE` capture, stage
   exact owned paths only, verify the staged set, re-check the tip,
   commit, unset, remove the temp index. `Agent-Glyph:` trailer on
   every commit; trailer verified after. Never push. Never amend a
   sibling's HEAD. Never touch the shared index.

## The receipt

Every builder's final report states: files touched, test command and
counts, ruff result, lint/guard results, commit hash, glyph. The
receipt is the proof artifact — without it, the work is a rumor.

## What "prove" scales to

- A pure function: a property-style test over the invariant (e.g.
  "every undeclared capability raises the denial, for N generated
  declarations").
- The pipeline: an end-to-end order test (fetch → parse → grade →
  shield → hooks) plus the fail-fast and isolate-one-plugin cases.
- A gate script: a fixture that must fail the gate (narrowing without
  a ruling fails `manifest_guard`; a remote import fails the
  no-remote-fetch lint). A guard with no failing fixture is unproven.
