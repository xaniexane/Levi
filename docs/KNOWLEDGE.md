# Knowledge base — `core/levi/knowledge/`

LEVI's local, queryable knowledge: a capability atlas, a defensive
security domain catalog, the ingested course corpus, and a dated daily
news corpus. All read locally; only `news-refresh` touches the network.

## Purpose

Give LEVI a grounded reference shelf it can cite — what it can do
(atlas), how to defend systems (security catalog), what it has studied
(courses), and what's happening (news) — without pretending the web is
in its weights.

## Key APIs

- `capabilities/atlas.json` — capability domains LEVI claims.
- `security/catalog.json` + `catalog.py` — 81 validated defensive
  security domains (`load_catalog()`, `.get(id)`, `.ids()`,
  `attack_relevant()`). Defensive blue-team content only
  (detection/analysis/hardening); attack-relevant entries carry an
  explicit `attack_profile` flag.
- `courses/` — ingested course corpus (see `docs/COURSES.md`).
- `news/refresh.py` — daily refresh from BBC/Reuters/AP/Hacker
  News/arXiv into `news/days/YYYY-MM-DD.jsonl`; `refresh(day, limit)`,
  CLI `main(argv)`. News is deliberately **kept out of training
  weights** — dated recall, not model memory.

## CLI usage

```bash
python -m levi.knowledge atlas --limit 20
python -m levi.knowledge security --domain android-security
python -m levi.knowledge news --limit 5
python -m levi.knowledge news-refresh --date 2026-09-15   # network
levi news refresh                                        # same, via CLI
```

## Honest limits

- The atlas is a claim of capability, not proof — verify against
  `docs/CAPABILITIES.md` and the tests.
- News refresh degrades honestly: on network failure it reports what
  happened and keeps yesterday's cache; it never fabricates items.
- The security catalog is defensive reference material; it is not a
  substitute for a real analyst and carries no exploit how-tos.
