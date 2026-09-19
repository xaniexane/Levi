# Income Batch A — Micro-Tools (slots 1–12)

Twelve original, from-scratch, stdlib-only micro-tools. Zero operating
cost, no network calls, no third-party code. Each generator does real
work on caller-supplied params:

- **dry run**: computes and reports what *would* be produced; writes nothing.
- **real run**: writes artifacts under
  `<levi_home>/.levi/income/work/<generator-id>/` and returns a WorkReport.

Pricing doctrine: no free core, entry $1–5 (~30–60% below giant-tool
equivalents). Quotes are pricing *advice* — income is recorded only by
Chauncey via `engine.record_income(basis="confirmed")`. The 70/30 split
applies at record time; money moves only through the Cybrus gateway.

## The twelve

| # | id | What it does | What it produces | Entry |
|---|----|--------------|------------------|-------|
| 1 | text-deduper | Removes duplicate lines/paragraphs (case/whitespace options), counts them | `deduped.txt`, `report.txt` | $3.00 |
| 2 | csv-columnizer | Sniffs delimiter, normalizes headers to slugs, dedupes, safe quoting | `cleaned.csv`, `report.txt` | $2.50 |
| 3 | filename-normalizer | Batch-renames to a slug convention, resolves collisions, writes undo manifest | `undo_manifest.json`, `rename_plan.txt` | $2.00 |
| 4 | json-prettifier-validator | Validates JSON, pinpoints errors (line/column + pointer), pretty-prints | `pretty.json` / `error_report.txt` | $2.00 |
| 5 | markdown-toc-builder | Builds/updates a TOC (GitHub-style anchors, inserts at `<!-- TOC -->`) | `with_toc.md` | $2.00 |
| 6 | whitespace-surgeon | Tab expansion, trailing-whitespace strip, blank-run collapse, per-file report | cleaned files, `report.txt` | $3.50 |
| 7 | regex-batch-replacer | Multi-pattern find/replace, preview with match counts/samples before applying | `preview.txt`, `replaced.txt` | $4.00 |
| 8 | excerpt-extractor | Extractive key excerpts via word-frequency + position sentence scoring | `excerpts.txt`, `scores.txt` | $3.00 |
| 9 | unit-converter-pro | 10 engineering dimensions + temperature (incl. aliases), batch mode | `conversions.txt`, `conversions.json` | $2.50 |
| 10 | passphrase-forge | Diceware-style passphrases from an original 128-word list via `secrets` (CSPRNG); 0600 output | `passphrases.txt` | $2.00 |
| 11 | diff-summarizer | Parses unified diffs into plain-language per-file summaries (+/- counts, touched symbols) | `summary.txt` | $3.00 |
| 12 | license-header-stamper | Stamps license headers by file type (hash/slash/block/html/docstring), shebang-safe, idempotent (marker check) | stamped files, `report.txt` | $2.50 |

## How to run

```python
from levi.income import engine
engine.discover()
engine.run_generator("csv-columnizer", dry_run=True,
                     params={"csv_text": "..."})
```

## Tests

`tests/test_income_microtools.py` — 18 tests: registry presence (slots
1–12, unique ids, kind `micro-tool`), run smoke per generator (dry + real),
dry-run safety (no deliverables written), price bounds 1.0–5.0, and
per-generator logic checks (delimiter sniffing, collision resolution,
error pinpointing, shebang safety, CSPRNG wordlist membership, etc.).

## Honest limits

- Tools operate on **caller-supplied params** (text/files passed in); they
  don't scan the host filesystem on their own.
- `filename-normalizer` produces a rename plan + undo manifest — it does
  not rename real files (preview-first safety).
- `passphrase-forge` entropy (~45 bits at 6 words) is honest but modest;
  it's a convenience tool, not a high-security KDF replacement.
- `diff-summarizer` handles unified diffs only; exotic formats raise a
  clear error rather than guessing.
