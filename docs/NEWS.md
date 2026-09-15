# LEVI News — dated current-events recall

LEVI does not have live awareness. What it has is a **dated snapshot**:
`core/levi/knowledge/news/refresh.py` fetches a curated source list and
stores per-day JSONL at `days/YYYY-MM-DD.jsonl`. The agent reads it with
`news_latest` / `news_search` — and every output carries dates, so staleness
is visible, never implied fresh.

## Sources

| id | what |
|---|---|
| `bbc-world` | BBC World RSS |
| `reuters-world` | Reuters world news RSS (often 401s from bots — recorded honestly in `sources.json`) |
| `ap-mirror` | AP headlines via the feedx.net mirror (third-party; labeled as such) |
| `hackernews` | HN top stories API (title + score/comments, top ~30) |
| `arxiv-csai` / `arxiv-cscl` | arXiv cs.AI / cs.CL recent papers RSS |

Bounded: top ~30 items per source per refresh. Deduped by URL within and
across days. A dead source never crashes the pass — `sources.json` records
per-source status (`ok` / `dead` / `empty` / `parse-error` with the date).

## Refresh cadence

Recommended: **daily** via LEVI's scheduler or cron:

```bash
cd ~/workspace/levi && PYTHONPATH=$PWD/core python3 -m levi.cli.main news refresh
# or directly:
python3 core/levi/knowledge/news/refresh.py
```

The agent-facing rule is simple: **cite the dates**. `news_latest` prints
"newest ingested date is …" up front; `news_search` stamps every hit.
If the newest date is a week old, the agent says the news is a week old.

## Explicit limits

- Headlines + short summaries only — no full article text.
- No live browsing, no paywall bypass, no login.
- If nothing was ingested, the tools say so instead of improvising.
- News is **never** baked into training weights (see docs/BRAIN_TRAINING.md):
  it goes stale; weights are for stable knowledge. Dated recall stays in
  JSONL, read at runtime.
