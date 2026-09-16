# Goal-Directed Recommender — visible math, no engagement mining

**Remix delta.** TikTok, YouTube, and Spotify maximize time-on-device;
opacity is load-bearing — if you could see the weights you could see the
manipulation. LEVI inverts it: recommendations are pure, inspectable
math over a local item corpus. The inputs are **user-stated goals**
("learn X", "catch up on Y") plus **explicit ratings** — never inferred
engagement, watch time, clicks, or scroll behavior. The weight vector is
visible and tunable, every recommendation ships its signal
contributions, and diversity/serendipity is a knob you turn, not a
growth hack. No network, no profile, no ads auction.

## The model (all of it)

Items carry explicit topic maps, e.g. `{"python": 1.0, "asyncio": 0.6}`.
Goals carry the same. Similarity is cosine over those maps:

```
cosine(a, b) = dot(a,b) / (|a| * |b|)
```

Signals per item (each in [0,1]):

| signal    | meaning |
|-----------|---------|
| `goal`    | max cosine to your active goals (a goal's kind-filter applies first) |
| `content` | cosine to the centroid of items *you rated 4+* — 0 until you rate |
| `quality` | mean of *your explicit ratings* / 5 — 0 until rated |
| `recency` | `0.5 ** (age_days / half_life_days)`, half-life 90d default |

```
total(i) = Σ_s  w_s · signal_s(i)
```

Default weights: goal=0.45, content=0.25, quality=0.20, recency=0.10 —
a starting position, not a secret. `weights show` / `weights set
goal=0.6,content=0.4,quality=0,recency=0`.

**Diversity (MMR).** After scoring, items are picked greedily:

```
pick = argmax  λ·total(i) − (1−λ)·max_picked cosine(i, p)
```

`--diverse 1.0` (default) is pure relevance; lower λ trades relevance
for topical spread — serendipity on a dial.

## Explanations

`recommend --explain` prints, per item, each signal's weight, raw
signal value, and contribution — the exact numbers behind the order —
plus honest notes when a signal is zero *and why* ("no liked items yet
— content signal is 0; rate items 4+ to enable it"). A zero is reported,
never silently backfilled.

## CLI

```bash
python -m levi.recommender add-item --title "Asyncio deep dive" --kind course \
    --topics "python:1.0,asyncio:0.9,concurrency:0.6"
python -m levi.recommender add-goal --title "Learn async Python" \
    --topics "python:1.0,asyncio:1.0" --kind-filter "course,book"
python -m levi.recommender rate asyncio-deep-dive 5
python -m levi.recommender recommend --explain
python -m levi.recommender recommend --diverse 0.6 --top 5
python -m levi.recommender weights set goal=0.6,content=0.4,quality=0,recency=0
python -m levi.recommender export ./my-taste.json
```

Data lives at `~/.levi/recommender/` as plain JSON and exports the same
way: your corpus, your goals, your ratings — no lock-in.

## Honest gaps

- **No collaborative signal.** "People like you liked…" doesn't exist
  here — there are no other people in the loop, and LEVI won't invent
  them. Taste is yours alone.
- **Topics are hand-declared.** No embeddings, no auto-tagging; item
  topics are what the curator (you) says they are. Garbage topics in,
  garbage recommendations out — visibly.
- **Cold start is honest, not papered over.** With no goals and no
  ratings, only recency scores — and the explanations say exactly that.
- **Single-user.** The store is one user's taste; multi-user is a
  deliberate non-goal (that road leads back to engagement mining).
