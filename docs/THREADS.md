# THREADS — Bridging-Ranked Discussion Trees

**Remix delta.** Reddit's engagement-optimized sorting is its revenue: it
structurally cannot ship an honest ranker, because the low-effort fluff
that drives time-on-site is what the sorter is *for*. LEVI inverts this:
thread ranking blends transparent quality signals with the bridging score
from `levi.bridging`'s clean-room math (cross-camp consensus, not raw
popularity). Every weight is user-editable, every score is explainable,
and identities are portable signed artifacts instead of platform accounts.

## Data model

`Discussion{id, title, community_id?, created_at}` (the `community_id` is
an opaque string matching `levi.communities` ids by convention — the
packages stay import-decoupled) holding a forest of
`Comment{id, discussion_id, parent_id?, author_id, text, created_at,
up[], down[]}`.

## Ranking

```
quality(c)  = 0.5·voteness + 0.3·substance + 0.2·depthness
bridging(c) = min-max normalized β from levi.bridging over the
              voter×comment matrix (up=+1, down=−1)
score(c)    = w_quality·quality(c) + w_bridging·bridging(c)
```

- `voteness`: net votes through a saturating curve → [0,1].
- `substance`: length saturating at 280 chars — a documented heuristic.
- `depthness`: `0.9^depth` — replies sink slightly unless they earn it
  back through votes/bridging.
- `bridging`: comments winning votes from voters who normally disagree
  rank above factional applause. Comments with fewer than 3 distinct
  voters score 0.5 (neutral — not enough evidence).

A comment with *fewer* raw up-votes but cross-camp support outranks a
factional pile-on when the bridging weight dominates — the inversion of
Reddit's sorter, demonstrated in `tests/test_threads.py`.

## CLI

```
python -m levi.threads new --title "Topic" [--id d1] [--community haven]
python -m levi.threads reply d1 --author ada --text "..." [--to <comment-id>]
python -m levi.threads vote d1 --comment <id> --voter bob --value up|down
python -m levi.threads tree d1 [--limit 50]
python -m levi.threads explain d1 <comment-id>   # every score component
python -m levi.threads rank-weight bridging 0.8
python -m levi.threads profile-new ada --name "Ada" [--bio ...]
python -m levi.threads profile-export ada --out ada.profile.json
python -m levi.threads profile-verify --in ada.profile.json
```

## Portable identity — honest scope

Profiles export as `{format, profile, signature}` with HMAC-SHA256 over
canonical JSON, keyed by `~/.levi/threads/identity.key` (owner-only
0o600). The signature proves the artifact was produced by whoever holds
the key — authorship continuity across exports and machines. It is NOT a
global identity system, NOT proof of personhood, and verification
requires the key (shared out-of-band). We say this plainly because
giants sell "verified identity" while meaning "platform account".

## Honest gaps

- Bridging needs real voter diversity; a discussion with 3 voters from
  one friend group gets neutral bridging scores by design.
- `substance` rewards length, not insight — documented, not hidden.
- No federation yet: threads are local files. The export format for
  whole discussions is future work (the profile artifact format is the
  v1 portability surface).
