# Honest Search — clean-room ranking over a local index

**Remix delta.** Google auctions ads against the *person*, not the query:
personalization, engagement history, and ad load are load-bearing for its
business, so it cannot ship neutrality. LEVI inverts it. A polite crawler
fills a **local** inverted index on your machine; ranking is clean-room
math over that corpus — tf-idf text match plus a PageRank-style link
graph — with a genuine unpersonalized mode. No account, no tracking, no
ads, no A/B ranking experiments. The index lives at
`~/.levi/honestsearch/index.json` and exports as plain JSON: your corpus,
your data, no lock-in.

## The math (all of it, checkable by hand)

**PageRank.** For indexed pages V with damping d = 0.85:

```
PR(v) = (1-d)/|V| + d * ( Σ_{u→v} PR(u)/outdeg(u) + dangling/|V| )
```

Dangling pages (no outlinks) redistribute their rank evenly. Solved by
power iteration to 1e-9 tolerance (max 200 rounds). Only links between
*indexed* documents count — the graph is your corpus, not the web.

**Text score.** For query terms t in document d:

```
text(d) = Σ_t  tf(t,d) · idf(t)
tf(t,d) = 1 + ln(count(t,d))
idf(t)  = ln((N+1)/(df(t)+1)) + 1
```

Tokenization: lowercase, alphanumeric runs ≥ 2 chars, minus a small
fixed English stopword list (in `index.py`, inspectable, never tuned per
user). No stemming, no embeddings.

**Combination.** Each signal is normalized to [0,1] by its corpus max,
then combined with the declared weight vector (default text=0.6,
link=0.4):

```
score(d) = w_text · text_norm(d) + w_link · pr_norm(d)
```

Retrieval gate: a document must match at least one query term to be a
candidate at all. Weights rank the candidates — they can never smuggle a
non-matching document into your results, even with `text=0`.

Weights are visible (`weights show`), tunable (`weights set
text=0.8,link=0.2`), validated (non-negative, normalized to sum 1), and
printed with every query.

## Genuine unpersonalized mode

This is structural, not a toggle: `rank.search()` accepts
`(index, query, weights, top_k)` and nothing else. There is no profile,
history, or identity parameter anywhere in the ranking path, so there is
nothing that *can* leak into the order. The test suite proves it two
ways: from the function signature, and by re-running queries against a
store polluted with fake profile data and asserting identical order.

## Explanations

`query --explain` prints, per result, the matched terms and each
signal's weight, normalized score, and contribution — the exact numbers
that produced the order. Nothing is a black box.

## Politeness (reused, not reinvented)

Crawling reuses `levi.research.deepweb.PoliteCrawler`: robots.txt
Disallow honored, per-host rate limiting, LEVI user-agent, public
sources only, no darknet, refusals recorded in the crawl report (never
fabricated). Default scope stays on the seed hosts; `--scope any`
follows outward under the same rules.

## CLI

```bash
python -m levi.honestsearch add notes/*.md
python -m levi.honestsearch crawl https://example.com/docs --max-pages 50
python -m levi.honestsearch query "forgotten hypertext" --explain
python -m levi.honestsearch weights set text=0.8,link=0.2
python -m levi.honestsearch stats
python -m levi.honestsearch export ./my-index.json
```

## Honest gaps

- **No JavaScript rendering.** stdlib has no JS engine; JS-heavy pages
  index only their static HTML. Documented, not hidden.
- **Corpus-relative authority.** PageRank here measures importance
  *within your corpus*, not the web. A 10-page crawl's link scores are
  real math over a tiny graph — useful, not oracular.
- **Freshness is fetch time only.** No crawl-frequency or update
  signals beyond `fetched_at`. Re-crawl to refresh.
- **Single-machine scale.** The index is JSON on disk; it handles
  thousands of pages comfortably, not billions. That is the trade for
  local-first: your index answers to you, not to an ads auction.
- **Text extraction is extractive.** Snippets/titles are the page's own
  words, never a generated summary.
