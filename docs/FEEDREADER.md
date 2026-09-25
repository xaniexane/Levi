# FEEDREADER — The Sovereign Feed Reader

Google killed Reader in 2013 because open RSS cannot be monetized: no ad
surface, no algorithmic feed to sell engagement against. The giants'
refusal is structural — a reader that respects you (no tracking, no
engagement-ordering, subscriptions you own) is a cost center to them.
LEVI Feedreader is the remix: everything runs on your machine.

## What it does

- **Polite polling** — conditional GET with ETag/Last-Modified, so
  unchanged feeds cost nobody anything; per-feed backoff on failures
  (no hammering a dying server).
- **Local store** — subscriptions in `~/.levi/feedreader/feeds.json`,
  items in `items.jsonl`. Yours, forever, in open formats.
- **Chronological order, always** — newest first. No engagement
  algorithm. There is no ad surface to protect, so none exists.
- **Health monitoring** — per-feed fail streaks, average latency, last
  success. Dead feeds are shown as dead, not hidden to juice "active"
  metrics.
- **OPML portability** — import from any reader, export to any reader.
  Your subscriptions are never held hostage.

Feed parsing reuses `levi.research.deepweb.feed_entries` (the deep-web
skill's parser) rather than duplicating XML logic.

## Usage

```bash
python -m levi.feedreader add https://example.com/feed.xml --title "Example"
python -m levi.feedreader poll                 # poll due feeds
python -m levi.feedreader items --unread       # newest unread first
python -m levi.feedreader read https://ex.com/p1
python -m levi.feedreader health               # ok/degraded/down per feed
python -m levi.feedreader opml-export --out subs.opml
python -m levi.feedreader opml-import subs.opml
```

## What the giant refuses

- Reader-side health transparency (they hide feed failures).
- Zero tracking in a reader (their readers are tracking surfaces).
- Subscriptions as a portable file (lock-in is the business model).

## Open gaps

- No full-text extraction of linked articles (deep-web skill does page
  fetch; a future `items --fetch-full` could wire it in).
- No feed discovery from a homepage URL yet (deepweb's
  `discover_feeds` is the natural source — not yet wired).
- PubSubHubbub/WebSub push subscriptions are out of scope for a
  poller; polling is honest and sufficient.
