# Coverage survey: mailtriage → sovmail (C12)

Read-only survey of `core/levi/mailtriage/` (triage.py, store.py,
replies.py, `__init__.py`) before building. Every existing capability
is mapped to **kept** (used as-is via import), **extended** (sovmail
adds the Eudora contract on top), or **superseded** (replaced, with a
reason). Nothing in mailtriage was modified.

## mailtriage/store.py — MailStore, normalize_message

- `MailStore(path)`: read-only maildir/mbox reader → **KEPT**.
  sovmail calls `MailStore.iter_messages()` for intake and reuses the
  normalized record dict (`id, from, to, subject, date, list_unsub,
  body, labels`) as its message shape. No rewrite — the reader is
  already correct.
- `normalize_message(key, msg)` → **KEPT** as the intake normalizer
  (bridge.py).
- `default_maildir_candidates()` → **KEPT** by reference; sovmail's
  archive is sovmail's own truth, it does not re-scan the user's
  maildir on its own.

## mailtriage/triage.py — TriageEngine

- Bundles (`receipts / newsletters / people / notifications / other`
  via user-editable `rules.json`) → **EXTENDED**. mailtriage bundles
  are one fixed pipeline; sovmail's `Filter` layer makes filters
  first-class *data* (priority-ordered, any action, matched-filter
  stamping). `TriageEngine.bundle()` is still callable from
  bridge.py as the baseline bundle predicate (`bundle_is`), so
  existing rule files keep working.
- Snooze ledger (`snooze_until`, `snooze_until_reply`, `wake_due`) →
  **KEPT**. sovmail's `disposition()` returns a folder/action, not a
  timer; snooze stays mailtriage's job. No overlap, no rewrite.
- `BUNDLE_ORDER`, `DEFAULT_RULES` → **KEPT** untouched.

## mailtriage/replies.py — ReplyEngine

- Template smart replies (`DEFAULT_TEMPLATES`, keyword matching,
  `{sender}/{subject}/{first_name}` placeholders, drafts in
  `drafts.json`, approval marks but never sends) → **EXTENDED** into
  `Stationery`. Why not kept as-is: the Eudora contract needs *named
  stationery with explicit slots* and a hard drafts-only guarantee at
  the type level. sovmail's Stationery composes DRAFTS ONLY — there
  is no send path in the module, and every draft carries its
  `template_id` + slot fillings. mailtriage's ReplyEngine remains
  the template-draft engine for mailtriage itself; sovmail does not
  call it, because its semantics (rule-matched suggestions) differ
  from stationery's (named templates with slots). Kept alive, not
  superseded.

## mailtriage/__init__.py / __main__.py — SHELF, CLI

- `SHELF` manifest, CLI (`inbox/bundles/snooze/draft/approve`) →
  **KEPT**. sovmail ships its own `__main__` demo; it does not
  re-implement the mailtriage CLI.

## What sovmail adds (the Eudora contract — all new)

| Eudora contract item | sovmail module | mailtriage had it? |
|---|---|---|
| Filters as data, priority-ordered, matched-filter stamping | `filters.py` (`disposition`) | No (fixed bundle pipeline) |
| Stationery: named templates, slots, drafts never sent | `stationery.py` | Partial (rule-matched reply templates → extended) |
| Plain-text mbox archive, one file per folder | `archive.py` | No (read-only view of *user's* mail) |
| Client-side naive Bayes, offline retrain | `bayes.py` | No |
| Deterministic scam-link analysis (display-vs-href, punycode, credential patterns) | `scamlinks.py` | No |
| Instant local search; index derived from archive, rebuildable | `search.py` (+ `archive.py`) | No |
| Intake bridge reusing mailtriage's reader | `bridge.py` | — |

Superseded: nothing. mailtriage's full test suite passes unmodified
(T7, verified in `tests/test_phase3_sovmail.py` via subprocess).
