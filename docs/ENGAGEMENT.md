# Engagement — surveys, campaigns, voting (AI + SI)

The familiarization-phase instrument. Standalone drops introduce
capabilities; users play through surveys, campaigns, and ballots; and
everything circles back full circle into the hub — aggregate learnings
(never individual answers) flow to DemandPulse's store.

## Doctrine (enforced in code)

- **Opt-in always.** Nothing engages until `levi engage opt-in`. Opt out
  anytime; prefs are kept, nothing prompts.
- **Skippable always.** Every question skippable; any survey/ballot
  abortable mid-run. Invalid answers degrade to skips, never hard errors.
- **User-controlled frequency:** `off` / `daily` / `weekly`.
- **Local-first.** Answers live under `~/.levi/engagement/`
  (`LEVI_ENGAGEMENT_DIR` overrides), files mode 600. Nothing leaves the
  machine — ever.
- **Metadata-only analytics.** Composes with the inbox analytics module
  (`engagement.survey`, `engagement.vote`, …) — capability + id, never
  content.
- **No identity in votes.** The vote ledger stores ballot, kind, choice,
  timestamp. There is no voter to leak.

## AI + SI, equally

The engagement layer spans both tracks. Every survey and ballot carries
a track tag — `ai`, `si`, or `both` — and hub signals aggregate per
track. The AI+SI pairing is the product; engagement treats it as one.

## Surveys

`levi engage list` / `take <id>` / `answer <id> --json '{...}'`

Starter set (original, LEVI voice, fun not corporate):

| id | track | what |
|---|---|---|
| `welcome-walk` | both | onboarding familiarization: mission, tone, track pull, check-ins |
| `feature-hunt` | both | treasure hunt through the organs — which doors to open first |
| `vault-guard` | si | security posture quiz — playful, no grades, no shame |
| `si-deep-dive` | si | tune the mind: memory depth, proactivity, Oracle style |
| `agent-crew` | ai | build your crew: agents, leash length, background shifts |

On completion, `EngagementStore` computes per-question tallies (choice
options counted; free text counted as `text-given`, never quoted;
skips counted) and reports them to DemandPulse via `scan_seed` with
the survey's track tag, e.g. `engagement: survey 'agent-crew' [ai] …`.

## Campaigns

`levi engage campaign <id>` / `dismiss <id>`

A campaign is a short card series (feature spotlights, security tips,
drop tours). Dismissable at any card; never re-shown once dismissed or
completed. Starter: `drop-01-tour` — the rolling-drops tour.

## Voting

`levi engage ballots` / `vote <id> [--pick n]` / `propose <verb> <text>`
/ `results` / `proposals`

Ballots (all track-tagged):

| id | track | kind | what |
|---|---|---|---|
| `hall-of-fame` | both | favorites | which feature deserves immortality |
| `agent-draft` | ai | favorites | draft your legion starter |
| `mind-meld` | si | favorites | which SI faculty earns your trust |
| `ship-it` | both | proposals | add / remove / change / integrate |

- **Favorites:** one vote per ballot; recasting replaces (change your
  mind anytime).
- **Proposals:** each distinct proposal becomes **weighted input on the
  request box** (`/requests`): one `[votes]` entry per proposal, status
  stays `open` for triage — **never auto-build**. Repeat votes raise
  the weight, not the request count. `levi engage proposals` ranks them
  by weight with their request ids.
- Results aggregate per track (`ai` / `si` / `both`) back to the hub.
- Proposal votes are public-by-design (they become request entries);
  favorite votes and survey answers are private-by-design.

## Companion chat

`/engage` — list due items · `/engage opt-in|opt-out` ·
`/engage vote <id>` — interactive ballot · `/engage results` — per-track
tallies.

## Files

- `core/levi/engagement/` — `surveys.py`, `campaigns.py`, `voting.py`,
  `prefs.py`, `store.py`, `cli.py`
- `tests/test_engagement.py` — 26 tests, home-scoped, DemandPulse mocked
- CLI: `levi engage …` · chat: `/engage`

## Honest limits

- Single-user tallies: "aggregate" here means counts over one user's
  repeated engagement, not a crowd — the shapes are crowd-ready for
  when the hub serves many.
- The module senses preferences; it does not verify them. A voted
  favorite is a signal, not a proof of use — cross-check with inbox
  analytics before treating votes as demand truth.
- Proposal text enters the request box verbatim (that is its purpose);
  triage accordingly — votes weight, they don't vet.
