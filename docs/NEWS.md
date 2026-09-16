# LEVI News — dated current-events recall

LEVI does not have live awareness. What it has is a **dated snapshot**:
`core/levi/knowledge/news/refresh.py` fetches a curated source list and
stores per-day JSONL at `days/YYYY-MM-DD.jsonl`. Records are
`{date, source, title, summary, url}` — headlines + short summaries only,
never full article text. Every consumer stamps dates on its output, so
staleness is visible, never implied fresh.

Corpus state (2026-09-16): 148 records across `2026-09-15.jsonl` (124)
and `2026-09-16.jsonl` (24). Daily corpora are committed alongside the
code so a checkout always ships a dated baseline; a stale checkout is
honestly stale, not silently empty.

## Sources

| id | what | status |
|---|---|---|
| `bbc-world` | BBC World RSS (RSS 2.0) | ok |
| `reuters-world` | Reuters world news RSS | dead — Reuters 401s bot fetches; recorded honestly in `sources.json`, never worked around |
| `ap-mirror` | AP headlines via the feedx.net mirror (third-party; labeled as such) | ok |
| `hackernews` | HN top-stories JSON API (title + score/comments, top ~30) | ok |
| `arxiv-csai` / `arxiv-cscl` | arXiv cs.AI / cs.CL RSS | ok |

Bounded: top ~30 items per source per refresh. Deduped by normalized
URL (tracking params like `?at_medium=RSS` stripped, host lowercased)
**and** by normalized-title hash, within and across days — the same
story syndicated under two URLs is stored once.

A dead source never crashes the pass and never gets fabricated:
`refresh.py` catches per-source failures, skips the source, and writes
`dead (<date>)` / `parse-error (<date>)` into `sources.json`.

## Refresh

```bash
# direct (stdlib-only, no install):
python3 core/levi/knowledge/news/refresh.py [--date=YYYY-MM-DD] [--limit=N]

# via the feedreader CLI:
PYTHONPATH=core python3 -m levi.feedreader news-refresh

# via the main CLI (same corpus):
levi news refresh
```

Polite by design: 10s timeouts, 0.5s delay between requests, LEVI
user-agent, and failure-is-honest per-source accounting.

**Daily schedule:** the `levi-news-refresh-daily` cron runs this every
morning (America/Chicago), owner `goal:levi-offline-brain-and-ux-upgrade`.
It reports per-source status and the new-record count; if the network is
down it reports the failure honestly and writes nothing.

## Search

`core/levi/knowledge/news/search.py` — ranked keyword search, stdlib-only:

- +3 per query token in the **title**, +1 per token in the **summary**
- +4 exact-phrase bonus (the query, minus stopwords, as a substring)
- × recency weight `1/(1+age_days/7)` — a week-old hit scores half a fresh one
- 2-letter tokens (`AI`, `EU`, `US`) count — the old naive substring
  search silently dropped them and returned zero hits for `AI`

```bash
PYTHONPATH=core python3 -m levi.feedreader news-search "quantum" --limit 5
PYTHONPATH=core python3 -m levi.feedreader news-latest --limit 10
```

Empty query or empty corpus → "no matches", never improvised.

## News never enters training weights

News goes stale by design; the native brain trains on stable knowledge
only. This is enforced mechanically, not just documented:

- `core/levi/knowledge/news/guard.py::assert_no_news_records(path)` scans
  any JSONL training corpus and raises `GuardError` (naming the offending
  line) on the first news-shaped record (`{date, source, title, summary,
  url}` — a different shape from training records' `{text: ...}`, so no
  false positives).
- `tests/test_news_pipeline.py::test_guard_holds_on_real_training_corpus`
  runs the guard against the real `core/levi/brain/train/corpus_academy.jsonl`
  on every suite run.

## Integration points (for the other crews — do not duplicate)

- `levi news refresh|latest|search` → `cmd_news` in
  `core/levi/cli/main.py` (~line 2849). Its search is currently a naive
  substring match; `search.search_news(query, days_dir, limit)` is the
  drop-in ranked replacement.
- Agent tools `news_latest` / `news_search` →
  `core/levi/agent/tools.py` (~line 712). Same swap applies.
- The feedreader news subcommands are thin stdlib wrappers, not a
  second corpus — there is exactly one news store: `days/*.jsonl`.
