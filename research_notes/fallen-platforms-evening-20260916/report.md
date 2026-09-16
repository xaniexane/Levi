# Fallen platforms — evening hunt 2026-09-16

Theme: (d) fallen platforms — the good ideas the winners left behind.
Ground-rule: does not re-cover the earlier fallen-platforms hunt
(fallen-platforms-hunt-20260916), which already archived Google
Reader's shared shelf, Vine's loop, Digg's bury, and MySpace's handmade
page; nor Google Reader subscriptions (feedreader module) or Orkut-style
communities (communities module). Tonight: Delicious, Path, Friendster,
FriendFeed.

## 1. Delicious: folksonomy, the web's shared memory — USEFUL PATTERN

**What/when:** del.icio.us, founded late 2003 by Joshua Schachter. Social
bookmarking: save URLs under free-form tags; anyone's tagged collection
was publicly browsable. The tags formed a folksonomy — bottom-up
organization with no editors and no algorithm.

**Mechanism:** Tagging was both filing AND publishing. A bookmark carried
its tags into a shared pool, so "everyone's bookmarks" was a live,
human-curated index of the web, ranked by real use rather than PageRank.
At peak (~2008): ~5.3M users, ~180M bookmarked URLs. AVOS added "Stacks"
(curated link lists) in 2011.

**Why it died:** Yahoo bought it Dec 2005 (~$15–30M) and let it linger —
the classic Yahoo acquisition-kill (same playbook as Flickr). Dec 2010
Yahoo announced it would sell the service as "not in the portfolio";
sold to AVOS (YouTube founders Chad Hurley, Steve Chen) mid-2011, then
Science Inc. (2014), Delicious Media (2016), then Pinboard's Maciej
Ceglowski (June 2017), read-only since June 15 2017. No owner ever gave
it a future; each bought the data and the brand, never the idea.

**Revival recipe:** A local-first link ledger: bookmarks with free-form
tags stored as one JSONL line each under ~/.levi, full-text + tag search
in stdlib, OPML/HTML bookmark-import so nothing is trapped. No social
pool needed — the folksonomy works for one person's archive too, and a
shared pool can be opt-in via community export checksums.

**LEVI application:** A `linkledger` module: save/tag/recall links
offline; tag-co-occurrence suggests related bookmarks (Delicious's
"popular tags" logic, rebuilt locally, honestly labeled as heuristics).
Queued in the build queue as useful-pattern (one build per evening;
circles won tonight).

**Skepticism:** Folksonomy's golden age benefited from a web small
enough to index by hand; on today's web it is a personal tool first.
Delicious's decline was also genuinely partly taste — tagging felt like
work once feeds did curation for you.

- https://techcrunch.com/2011/04/27/yahoo-sells-delicious-to-youtube-founders/
- https://siliconangle.com/2017/06/01/web-2-0-era-social-bookmarking-darling-delicious-close-14-years/

## 2. Path: the cap is the product — LOAD-BEARING

**What/when:** Path, founded 2010 by ex-Facebook PM Dave Morin with
Napster's Dustin Mierau and Shawn Fanning. A "personal network" (their
term, not "social network") that limited you to 50 friends — later 150,
then 500 — explicitly citing Robin Dunbar's work on human social
capacity. Peak ~10–15M users; raised ~$70M at up to ~$500M valuation;
Google reportedly offered $100M when it was months old.

**Mechanism:** The friend cap was the product. With a bounded audience
you share the story of your life, not a performance. No follower
counts to grow, no public metrics to game — intimacy was enforced by
architecture, not promised by policy. It also pioneered sticker-style
emojis (later "borrowed" by Facebook) and moment-by-moment lifelogging
that felt like a diary, not a feed.

**Why it died:** Network effects beat intimacy: "most of my friends
weren't on Path." The 2012 FTC $800K settlement (uploading users' full
iPhone address books without consent) poisoned the privacy brand that
was the entire value proposition. Sold to Kakao (2015) for its
Indonesian user base; shut down Oct 18 2018, pulled from stores Oct 1.
Facebook absorbed its design ideas; the cap died with the app because a
cap is the one feature a growth-driven giant cannot copy — it would
shrink their addressable audience by definition.

**Revival recipe:** Dunbar layers as a local data structure: inner (5),
close (15), friends (50), tribe (150) — hard caps enforced at add-time,
deny-closed. Members are local ids, no accounts, no servers. Sharing is
circle-scoped: a journal entry, a photo, a growth milestone goes to
exactly one circle and the receipt records the circle, never a public
feed. No counts are ever published; an owner-only audit shows cap
headroom honestly.

**LEVI application:** `core/levi/circles/` — Dunbar-bounded trust
circles built tonight: add/remove/move with hard caps, circle-scoped
share receipts, JSON store under ~/.levi (0700/0600), CLI
`python -m levi.circles`. This is what Path refused to compromise on
until growth pressure made it — LEVI has no growth pressure, so the cap
can stay sacred. Built in this wave.

**Skepticism:** Path's own history is a warning: they lifted the cap
themselves (50 → 150 → 500) chasing growth. A cap only works if some
authority — here, the local keeper, not a board — refuses to move it.

- https://techcrunch.com/2018/09/17/rip-path/
- https://www.engadget.com/2018-09-17-path-private-social-network-stickers-dead.html

## 3. Friendster: testimonials, the honest social proof — USEFUL PATTERN

**What/when:** Friendster, launched March 2002/2003 by Jonathan Abrams —
the first modern social network. 3M users in its first three months;
Google reportedly offered $30M. Abrams took VC money instead; the
boards chased features while pages took 40 seconds to load. Sold to
Malaysia's MOL Global Dec 2009 (~$39.5M); suspended 2015, ceased 2018.
(Per Wikipedia it relaunched April 2026 — noted, not verified here.)

**Mechanism:** Testimonials. Friends wrote short public testimonials on
your profile — named, attributable social proof. Unlike follower
counts, a testimonial costs the writer something (their name, their
reputation) and says something specific. It was the honest version of
what MySpace's Top 8 and every "verified" badge later industrialized:
trust attested by people, not asserted by metrics. Fakesters (fake
"Homer Simpson" profiles amassing friend collections) were the same
disease the metric-obsessed web still has — testimonials were the
antibody.

**Why it died:** The canonical cautionary tale: technology neglected
(slow pages, six CEOs in six years), features nobody asked for instead
of fixing the site, and arbitrary moderation purges. The giants kept
the social graph and threw away the attestation layer — because
followers scale and testimonials don't.

**Revival recipe:** Attestation as a first-class local primitive: a
vouch is a signed, named statement ("A vouches for B's claim") with
provenance and revocation, stored locally. LEVI's growth journal,
liberation ledger, and circles can all carry vouches instead of counts.

**LEVI application:** Queue a `vouch` primitive (useful-pattern): named,
revocable attestations over local artifacts; complements circles'
bounded trust with explicit endorsement. Not built tonight — one build
per evening; the design needs the charters treatment first.

**Skepticism:** Testimonials were gameable (reciprocal fluff) and the
Friendster testimonial culture had as much social theater as honesty.
The mechanic is the find, not the platform's virtue.

- http://en.wikipedia.org/wiki/Friendster
- https://www.fastcompany.com/59447/cautionary-tale

## 4. FriendFeed: the lifestream Facebook had to buy — INSPIRATIONAL

**What/when:** FriendFeed, founded Oct 2007 by ex-Googlers Bret Taylor,
Paul Buchheit, Jim Norris, Sanjeev Singh (Gmail/Maps veterans).
Real-time aggregation of everything you did online — tweets, Flickr
photos, blog posts, Last.fm tracks — into one shared lifestream with
threaded comments and likes. Facebook acquired it Aug 2009 (~$50M;
Taylor became CTO); service starved of development, shut down April 9,
2015.

**Mechanism:** You owned the aggregation of your own traces. Every
service you used fed one open stream, and the stream — not the walled
garden — was the social object: friends commented on your Flickr photo
or your tweet from inside the lifestream. Its core even became the
Facebook feed's real-time machinery after the acquisition. Open by
design: it worked across rivals' services, which is exactly what made
it a threat.

**Why it died:** Facebook bought the threat and the talent, then let
the product wither; Twitter choked its firehose access for good
measure. The lifestream idea was absorbed into the walled garden as a
feature (the News Feed) minus the openness. Giants sell you the feed;
they will never sell you the aggregator, because the aggregator makes
leaving costless.

**Revival recipe:** A personal lifestream is a local aggregation
problem now: LEVI already harvests chat sessions, automation runs,
journal entries, and growth cycles — the lifestream is just the honest
chronological view over data LEVI already owns. No APIs to buy, no
firehose to beg for.

**LEVI application:** Queue for the recap/journal wave (inspirational):
a `lifestream` view — one chronological river over LEVI's own local
sources (growth journal, automation runs, share receipts, circles),
rendered as markdown. The anti-Facebook: your life, aggregated by you,
on your machine.

**Skepticism:** FriendFeed was beloved by tech insiders and confusing
to everyone else (~1M monthly uniques at acquisition). The lifestream
as consumer product may simply not want to exist; as a personal,
local-first view over your own data, it wants to.

- https://venturebeat.com/social/facebook-to-acquire-friendfeed
- http://siliconangle.com/2015/03/10/rip-facebook-is-closing-friendfeed-april-9/
