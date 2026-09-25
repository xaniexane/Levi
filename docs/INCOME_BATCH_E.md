# INCOME batch E — automation services (slots 81–92)

Twelve original, from-scratch, stdlib-only local automation services.
Every generator automates a real local task against a user-supplied
`params["target"]` path. Defaults are preview/dry-run; real runs write
undo/restore manifests and never delete without one. No network, no paid
APIs, no third-party code, zero operating cost.

Pricing follows the founder doctrine: entry $1–5, ~30–60% below the
giants. `run()` returns `WorkReport.quoted_amount_usd` as pricing advice
only — income is recorded solely by Chauncey via
`engine.record_income(..., basis="confirmed")`.

| Slot | Generator | Entry | What it does | What it earns |
|------|-----------|-------|--------------|---------------|
| 81 | file-sort-bot | $3.00 | Sorts a messy dir into category folders (images/documents/audio/video/archives/code/misc) | move manifest — undo by reversing moves |
| 82 | log-rotator | $2.50 | Rotates oversized logs, archives aged-out logs by size/age policy (`.gz`) | compressed archives + restore manifest |
| 83 | daily-digest-assembler | $3.00 | Assembles a dated morning digest from local notes dirs + log tails | `digest-YYYY-MM-DD.md` |
| 84 | reminder-nudger | $2.00 | Reads a `YYYY-MM-DD | text` reminders file; reports overdue / due / upcoming | `nudge-YYYY-MM-DD.md` |
| 85 | backup-runner | $4.00 | Local backup with per-file sha256 manifest + verification pass | backup tree + integrity manifest |
| 86 | photo-organizer | $3.50 | Organizes images into dated folders (filename date pattern, mtime fallback) | undoable move manifest |
| 87 | duplicate-finder | $4.00 | Finds duplicates by sha256 (size-preindexed); reports reclaimable bytes | `duplicates.json` — report-only, never deletes |
| 88 | bulk-renamer | $2.50 | Rule-based bulk rename (prefix/suffix/replace/case/regex), preview in dry-run | undoable rename manifest |
| 89 | folder-watch-reporter | $2.00 | Reports added/removed/modified since last run (JSON state file) | `changes.json` |
| 90 | task-health-checker | $3.00 | Verifies scheduled outputs exist + are fresh (timestamp policy), reports gaps | `health.json` |
| 91 | archive-packer | $2.50 | Packs aging files into dated `.tar.gz` archives | manifest; originals removed only after archive verifies (restore = extract) |
| 92 | inbox-sweeper | $3.00 | Sweeps a local text/maildir inbox into triaged folders by regex rules | undoable sweep manifest |

## Safety rules (binding)

- `dry_run=True` writes nothing outside the run log — it reports the plan only.
- Destructive moves default to preview; real runs write undo/restore manifests first.
- Nothing is ever deleted without a manifest: log-rotator and archive-packer
  keep compressed originals; duplicate-finder only reports.
- Default `target` is a tmp sandbox dir; a real user path is only used when
  explicitly passed in `params`.

## Honest limits

- photo-organizer does not parse EXIF (stdlib-only) — it dates from filename
  patterns with file-mtime fallback.
- duplicate-finder is report-only by design; deletion stays with the owner.
- folder-watch-reporter compares mtime+size, not hashes (fast, coarse).
- reminder-nudger accepts only `YYYY-MM-DD | text` (or `:`) line format.
- None of these move money. Money paths go through the Cybrus MoneyGateway
  only, and only Chauncey records income with `basis="confirmed"`.

## Run / test

```bash
python3 -m pytest tests/test_income_automation.py -q   # 17 tests
```
