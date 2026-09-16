# LEVI Deep-Web Research

The deep web, for LEVI's purposes, is the **public but unindexed** web:
pages and records no surface search engine reaches. The perpetual hunts
("everyday hunt for food") eat here — forgotten documentation, dead
project sites, historical page versions, datasets nobody linked to.

Module: `core/levi/research/deepweb.py` (stdlib-only — `urllib`, no
third-party packages). CLI: `python -m levi.research.deepweb <command>`.

## Techniques

| Source | How | Notes |
|---|---|---|
| Wayback Machine | CDX API + availability API | Snapshot replay URLs, HTTP-200 captures only |
| Common Crawl | index API (`collinfo.json` picks the newest index) | Capture **metadata** only — WARC payloads are never downloaded |
| Sitemaps | robots.txt `Sitemap:` lines, then conventional probes | Follows sitemap indexes (depth ≤ 3, URLs ≤ 2000) |
| Polite crawling | per-host rate limit (default 2s), `LEVI-deepweb` user-agent | robots.txt `Disallow` honored for our agent + `*` |
| Feeds | `<link rel=alternate>` discovery + conventional paths | RSS 2.0 and Atom item extraction |
| arXiv | API (Atom) | Dedicated 3s-delay crawler per arXiv's politeness ask |
| data.gov | CKAN `package_search` JSON API | Open government datasets |
| SEC EDGAR | `company_tickers.json` + submissions JSON | Public filings, no authentication |

## CLI

```bash
python3 -m levi.research.deepweb survey "forgotten hypertext systems" --domain example.org --save
python3 -m levi.research.deepweb wayback --url 'example.org/docs/*' --limit 20
python3 -m levi.research.deepweb commoncrawl --pattern 'example.org/*' --limit 20
python3 -m levi.research.deepweb sitemap --domain example.org
python3 -m levi.research.deepweb feeds --url https://example.org --items
python3 -m levi.research.deepweb arxiv --query "plan 9"
python3 -m levi.research.deepweb portals --query "climate"
python3 -m levi.research.deepweb boundaries   # print the hard boundaries
```

Global flags: `--json` (machine-readable output), `--home` (override the
home dir for hermetic runs). Surveys can be persisted with `--save` under
`~/.levi/research/deepweb/`.

## API

```python
from levi.research import deepweb as dw

survey = dw.survey_topic("forgotten UIs", seed_domains=["example.org"])
for src in survey.sources:      # each carries url, retrieved_at, method
    print(src.kind, src.url)
for r in survey.refusals:       # honest record of what could not be reached
    print(r["url"], r["reason"])
```

Every `DeepSource` carries provenance: `kind`, `url`, `title`, `summary`
(extractive snippet — never presented as a semantic summary), plus
`retrieved_at`, `method` (how it was found), and `notes`.

## Hunt integration

`core/levi/perpetual/hunt.py` includes the deep-web pass in every hunt
plan's instructions via `DEEPWEB_SURVEY_CMD`:

```
python3 -m levi.research.deepweb survey "<topic>" [--domain <seed-domain>] [--save]
```

Scheduled hunts can run this before writing their reports, so findings
cite archived captures and unindexed sources instead of only surface-web
results. Deliberately a string hook, not an import — the hunt procedure
stays decoupled from the research implementation.

## Hard boundaries (enforced in code)

1. **Polite only** — robots.txt `Disallow` honored, per-host rate limiting,
   `LEVI-deepweb` user-agent. Disallowed URLs are never fetched.
2. **Public only** — no paywall bypass, no credentials, no login flows,
   no CAPTCHA/token solving, no defeating access controls.
3. **No darknet** — `.onion` addresses raise `BoundaryError` outright.
   So do loopback targets and URLs carrying credentials.
4. **No private-data harvesting** — published public records only.
5. **Honest failures** — unreachable sources are recorded in
   `survey.refusals` / `crawler.refusals`, never fabricated.

This is OSINT knowledge-gathering, defensive in spirit: LEVI learns what
the public web already published — nothing more.

## Honest gaps

- Feed discovery only recognizes `<link>` tags with `rel` before `href`;
  real-world tag attribute order varies (best-effort, documented).
- `sec_edgar_search` and the CKAN/arXiv response shapes are best-effort:
  upstream formats change; failures are reported, not papered over.
- Common Crawl returns metadata only — full WARC retrieval is a
  deliberate non-goal (payloads are enormous).
- No JavaScript rendering (stdlib-only): JS-heavy pages yield little text.
- `levi deepweb` is not yet wired into the top-level `levi` CLI parser
  (`core/levi/cli/main.py` is under active work by another worker);
  `python -m levi.research.deepweb` is the stable entry point and the
  module exposes `main(argv)` for one-line dispatch later.
