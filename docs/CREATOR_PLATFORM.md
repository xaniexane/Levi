# Creator Platform — dating + digital creator services, two tracks

Chauncey's order: the Echoverse is the basic SFW safe route; the creator
platform extends the pattern on two tracks that never merge.

## The two tracks

**SI track** (`core/levi/creator/si/`) — adult dating + digital creator
service platform, OnlyFans/Telegram-style:
- Creator profiles, subscription tiers, sealed messaging, content drops.
- A "skip the games"-style adult dating/classifieds module (listings,
  search, respond).
- Sealed in the Veil lineage (renamed from Void Box 2026-09-17):
  tamper-evident envelopes, keeper-held keys, airtight, encrypted,
  reinforced. SI store dir 0700, records sealed, key file 0600.
- Behind the Plaiground gate law: adult-only, default OFF, minors
  hard-locked out. Every public function calls `require_adult()` first;
  user text passes the Plaiground bounds check.

**AI track** (`core/levi/creator/ai/`) — the same style modules reformed
for society and ethics:
- SFW dating: profiles with interests, interest-based matching, messaging.
- General-audience creator platform: profiles, tiers, drops, messaging.
- Content rules enforced in code (`ai/rules.py`): the universal hard
  boundary floor (no minor involvement, no non-consensual, no violent, no
  manipulative content — gateless here, because the boundaries are
  universal and the gate is not) plus the SFW rule (no sexual or explicit
  content, no harassment).

The tracks never merge: separate stores (`si/` sealed vs `ai/` plain),
separate code paths, no cross-track queries. The AI side never carries
adult content.

## Pricing — two separate schedules

Set through the founder price advisor (`core/levi/advisor/pricing.py`)
against verified competitor numbers. Config lives in
`core/levi/creator/pricing.py` — built by actually calling `advise_price`,
receipts attached to every tier, deterministic.

**Dating-side schedule** (Chauncey's tiers):

| Tier | Price | Period | Advisor band | Giant anchor |
|------|-------|--------|--------------|--------------|
| day_pass | $1.00 | day | $1.00–$5.00 (entry, no giant) | keeper anchor |
| weekly | $5.00 | week | $3.00–$25.00 (standard, no giant) | keeper anchor ($5 in-band) |
| monthly | $12.00 | month | $10.00–$17.49 (flagship, volume) | Tinder Plus $24.99/mo (verified) |

**Creator-service schedule** (its own competitive structure):

| Tier | Price | Period | Advisor band | Giant anchor |
|------|-------|--------|--------------|--------------|
| taste | $1.00 | 3-day sampler | $1.00–$5.00 (entry, no giant) | — |
| monthly | $4.00 | month | $4.00–$6.99 (standard, volume) | OnlyFans median $9.99/mo (verified) |
| patron | $20.00 | month | $20.00–$34.99 (flagship, volume) | OnlyFans top $49.99/mo (verified) |

Tips carry no fixed price; the platform cut applies to all paid flows.

**Platform cut: 12%.** The prevailing standard is OnlyFans' flat 20%
(verified: OnlyFans terms, Fenix International filings). 12% is exactly
40% below the standard — inside the doctrine's 40–70%-below-the-giant
band. Creators keep 88%.

Doctrine honored throughout: no free core (every tier > $0), entry
dollar-scale, volume over margin (low end of each band), never at or
above the giant, competitor numbers verified never invented.

## Money

Every paid flow on both tracks routes through the Cybrus money gateway
only (`core/levi/creator/money.py` → `MoneyGateway`). No real rails
exist, so charges fail closed with `NoRailConfigured`; subscriptions
record as `pending_payment` with the plan id. Money never moves; the
record is honest about that. Authorization must come from the keeper —
a non-keeper authorization refuses before any rail is consulted.

## Threat model (honest)

- **Sealing** (Veil lineage, stdlib): Encrypt-then-MAC — SHA-256 CTR
  keystream + HMAC-SHA256, keys via HKDF from a 0600 keeper key file.
  Tamper-evident at rest; not AES-GCM; does not protect against an
  attacker who already holds the key file or the keeper's memory.
- **Gate**: proves affirmative owner opt-in on this machine, not
  cryptographic age (documented in `docs/PLAIGROUND.md`).
- **Bounds/SFW rules**: pattern-based floors, not judges.
- **No real payment rails**: all money movement is planned, previewed,
  authorized, then blocked — paper only until Chauncey registers a rail.

## CLI

`levi creator si-*` (gated) and `levi creator ai-*` (open), plus
`python -m levi.creator`. See `core/levi/creator/cli.py`.

## Tests

`tests/test_creator_platform.py` — 38 tests: gate-locked SI entries,
bounds refusals, sealing round-trip + tamper-evidence + 0600 key,
money fail-closed (blocked/refused), AI SFW rules without gate, track
isolation, pricing schedule assertions (two separate schedules, every
tier inside its advisor band, cut undercuts the standard).

## Extension — private media, chats, dating privacy, meetup safety

**Private media** (`si/media.py`, `ai/media.py`) — photos and videos as
first-class content drops: per-tier gating (non-cancelled subscription)
and per-subscriber grants, private by default (no tier/grants = creator
only). Payloads sealed at rest on the SI track; metadata-only listings
keep payloads out of list views. Grant/revoke is creator-only.

**Private chats** (`si/chats.py`, `ai/chats.py`) — 1:1 chats and
owner-moderated group chats (add/remove/close/reopen are owner-only;
the owner can't remove themselves; closed chats keep readable history
but stop new messages). Membership enforced on every send and read —
non-members get nothing, not even the member list. Sealed on SI.

**Dating privacy** (`si/privacy.py`) — "post a price, message airtight,
nothing else escapes":
- Public search returns redacted listings (headline/seeking/terms) with
  NO poster identity — no public directory of who posted what.
- Responding carries an explicit disclosure gate: the responder chooses
  whether their identity is revealed to the poster or replaced with a
  pseudonym. Nothing is revealed beyond that choice.
- Responses are readable by the poster (redacted view) or the responder
  only — never third parties, never search.

**Meetup safety** (`safety.py`, both tracks) — opt-in first-meetup
check-ins, off by default:
- The user picks trusted contacts and writes the plan (who/where/when,
  check-in cadence, which contacts escalate, and the exact disclosure
  note revealed on escalation).
- Checking in resets the silence timer; ending the plan closes it when
  the user is comfortable.
- A missed check-in deadline fires escalation once: a sealed record with
  only the pre-authorized disclosure (contacts, who/where/when, missed
  fact, disclosure note). No notification rail exists — the record is the
  handoff, marked `pending` delivery.
- Contacts and plans are owner-only; contacts learn nothing unless an
  escalation fires, and then only what the user authorized.

`tests/test_creator_extension.py` — media gating/grants/revoke,
sealed-at-rest payloads, chat membership + owner moderation, dating
privacy (redacted search, disclosure gate, participant-only reads, leak
attempts fail). `tests/test_creator_safety.py` — contacts owner-only,
plan lifecycle, escalation fires exactly once on missed check-in, no
escalation after check-in or end, SI sealed at rest, AI SFW, track
isolation.
