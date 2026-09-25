# King — the control plane

King (`core/levi/king/`) is the **single control plane for narrative
operations** (blueprint §4). It is an orchestration layer over the two
real content engines — **not a third content engine**:

| Engine | Module | Job |
|---|---|---|
| Multi-story | `levi.graph.story_fabric.StoryFabric` | Many distinct stories, per-story Direction/Modes |
| Single-manuscript | `levi.lwp.model_engine.LWPModelEngine` | One continuous manuscript: REIM forks, RIEM deny→ghost, ROM/Wyrd-Rupture, gold path |

Both engines are imported with try/except optional-imports. If either
is absent, King degrades gracefully: engine-backed methods return a
plain-language "unavailable" message instead of raising, and the
non-engine surfaces (`status`, `social` from ledger fallback, `d5`)
keep working.

## What King layers on top

- **Continuity ledger** (`ledger.py`) — entities, causal edges, and a
  D2→D5 rank derived from **word count + bank count** (not word count
  alone). This is the **one place** word-count/rank totals accrue,
  regardless of which engine produced the words. Both engines keep
  their own internal counters (their tests depend on them); the ledger
  is an aggregate on top, not a replacement. Every King method that
  drives either engine harvests into this same ledger.
- **Its own Wyrd-ROM** (`rom.py`) — rupture-lock for multi-engine
  sessions. See "The Wyrd-ROM division" below; do not collapse the two.
- **Social packs** (`social.py`) — caption + hashtags per platform,
  sanitized of markdown; content generation only, never the network.
- **Visual checkpoints** (`visual.py`) — Pollinations-style URL strings
  only; never the HTTP request.
- **Review queue** (`review.py`) — persisted HITL surface for
  deny/approve, plus the mandatory approval step before any post.

## The ten commands

`levi king <action>` (default action: `status`).

| Command | Backing | Semantics |
|---|---|---|
| `status [--visual]` | ledger | Rank, word/bank totals, entity/edge/harvest counts, ledger fingerprint, engine availability, review depth, session-ROM lock count, last 3 harvests, demo-promotion state. `--visual` adds a deterministic visual-checkpoint URL per rank. |
| `pulse [--story-id ID]` | StoryFabric | Advances one story one beat (`StoryFabric.expand`) and harvests the word delta + new beats as banks into the ledger; registers story/character/beat entities and a causal `advances` edge. Pulses the latest story by default. |
| `manuscript [--scenes N]` | model_engine | Expands N scenes (`LWPModelEngine.expand`) and harvests the word delta + new scenes as banks; registers scene entities and `contains` edges. |
| `social [--platform P] [--title T]` | social.py | Builds a sanitized pack from the freshest source text (engine `last_text` → latest story body → ledger events) and queues it in the review queue as **pending**. Prints the review id. No network. |
| `social-post --id ID [--platform P] --yes` | plugins/registry.py | Posts an **approved** pack through the honest connector contract. Two independent HITL gates: (1) the pack must be `approved` in the review queue; (2) `--yes` is required — without it the command refuses with a clear message and exits 2. The connector (`social-stub` loopback today) enforces confirmation again inside `execute()`; King never bypasses it. |
| `reim [--tracks N] [--seed S]` | model_engine | Pass-through to `reim_forks()`. Registers the fork tracks as entities; harvest records **0 words / 0 banks** (forks are not canon until crowned) so the audit trail stays honest. |
| `deny [ID] [--note N]` | model_engine / review | With an id: denies that pending review item. Without: pass-through to `deny_last()` (RIEM: scene → composted ghost) and logs the decision in the review queue's audit log. |
| `approve [ID] [--note N]` | model_engine / review | With an id: approves that pending review item. Without: pass-through to `approve_last()` and logs the decision. |
| `rupture [--lens L]` | model_engine | Pass-through to `wyrd_rupture()` — the **single-manuscript** ROM lock. Harvests the rupture words + 1 bank. (King's own session ROM is exercised by `d5`; see below.) |
| `d5 [--reset]` | ledger + rom.py | **Documented baseline promotion for demoing rank progression.** Floors the ledger's *derived* rank at D5 as an explicit, timestamped **demo override** — no words or banks are fabricated — and seals the promoted session state with King's own Wyrd-ROM (`rupture_session` over the ledger fingerprint). `--reset` clears the promotion. |

## Documented interpretations (where the blueprint is terse)

1. **`pulse` never auto-creates a story.** Blueprint §1.5 requires an
   explicit confirm step before creating an artifact. With no stories,
   `king pulse` prints guidance (`levi story --create …`) and harvests
   nothing, rather than silently inventing one.
2. **`deny`/`approve` are dual-mode.** The blueprint lists them both as
   manuscript-engine pass-throughs *and* assigns the review queue to
   `deny`/`approve`. Resolution: with an id they decide a review-queue
   item; without an id they pass through to the manuscript engine and
   the decision is audit-logged in the review queue. Both readings are
   honored, in one surface.
3. **`rupture` is the manuscript pass-through; `d5` exercises King's
   own ROM.** The blueprint's CLI list says `rupture` passes through to
   the manuscript engine, so it does. King's session ROM needed a real
   CLI exercise: `d5` is a session-level commitment ("this whole
   King session is now D5-baseline"), which is exactly what the session
   ROM is for — so `d5` seals it.
4. **`d5` is a demo override, not earned rank.** It is recorded with
   `demo: true`, shown as `PROMOTED (demo)` in `status`, and clears
   with `--reset`. Earned progression still comes from words + banks.
5. **Posting needs real platform connectors to leave the loopback.**
   Today every platform maps to `social-stub` (local loopback, no
   network, no credential). Adding a real connector = new module under
   `core/levi/plugins/` + an entry in `PLATFORM_CONNECTORS`; the
   confirmation gate and review-approval gate apply unchanged.

## The Wyrd-ROM division

- `LWPModelEngine.wyrd_rupture()` — locks **prose canon inside one
  continuous manuscript**: ROM lens prose, rate-limited budget (~1 per
  20k words), immutable scene sealed into that manuscript's bible.
  Scope: one engine, one manuscript.
- `king.rom.SessionRom.rupture_session()` — locks **continuity state
  of a King-orchestrated multi-engine session**: a sha256 fingerprint
  of the ledger (entities + causal edges + harvests + totals across
  both engines) at a moment in time, with a reason. Scope: the session.

A rupture inside a King session answers "what did the whole control
plane believe at time T"; a rupture inside one manuscript answers
"this prose is canon for this manuscript." Different commitments,
different consumers — never merged for tidiness.

## The sanitize contract (social.py)

A prior build shipped `#`/`**` from source story text into a real
social caption. The contract is now enforced by assertions on
generated text (`assert_pack_clean`, run on every pack King builds,
and covered by `tests/test_king_social.py`):

1. All markdown structure is stripped from source text: ATX headings,
   `**`/`__`/`*`/`_` emphasis, code spans/fences, images, links
   (`[text](url)` → `text`), blockquotes, horizontal rules.
2. Any `#` surviving step 1 is stripped from the body — a `#` in a
   final caption may only ever be one King generated itself.
3. Hashtags are generated fresh from content keywords (deterministic:
   frequency-ranked, ties alphabetical, stopwords excluded) and
   appended in a trailing block, after sanitization.

Every `#x` in a final caption matches `#[A-Za-z][A-Za-z0-9_]*` and
sits in the trailing hashtag block; `**`, backticks, and heading
lines never appear.

## Posting honesty (plugins contract)

`social-post` routes through `levi.plugins.registry` — the same
`Connector.execute()` every other plugin uses:

- unknown operation / missing credential / unwired transport →
  `ok=False` with a plain-language status; nothing is sent;
- write operations require `confirm=True` (forced at class-definition
  time, no per-feature override) — King passes `confirm=True` only
  when the operator gave `--yes`;
- `ok=True` is returned only after the transport actually ran.

`social-stub` is the loopback used for tests and demos: its
"transport" is an in-memory outbox, its success message states
explicitly that the payload stayed on the machine, and it is
credentialless by design. It must never be mistaken for a real
platform connector — its id and display name say "stub".

## Files

```
core/levi/king/
├── __init__.py    King orchestrator (optional engine imports, harvest,
│                  the ten surfaces as methods)
├── ledger.py      ContinuityLedger: entities, edges, harvests, D2→D5
├── rom.py         SessionRom: King's own multi-engine rupture-lock
├── social.py      Sanitized pack generation (pure, no network)
├── visual.py      Checkpoint URL builders (pure, no HTTP)
├── review.py      ReviewQueue: pending/approved/denied + audit log
└── cli.py         register_king() + cmd_king() (wired into
                   core/levi/cli/main.py inside KING-REGION markers)
core/levi/plugins/social_stub.py   Local loopback connector (test/demo)
```

King state lives under `~/.levi/king/` (`ledger.json`,
`review.json`, `rom.json`), all written atomically with `0o600`
owner-only permissions. The engines keep their own stores
(`~/.levi/stories/`, `~/.levi/lwp_model_state.json`); King only
orchestrates them.
```

```bash
# quick tour (from ~/workspace/levi/core)
python -m levi.cli.main king status
python -m levi.cli.main story --create "A lighthouse keeps the last signal." --genre literary
python -m levi.cli.main king pulse            # harvests into the ledger
python -m levi.cli.main king manuscript       # expands + harvests
python -m levi.cli.main king social --platform x
python -m levi.cli.main king approve <review-id>
python -m levi.cli.main king social-post --id <review-id> --yes   # loopback
python -m levi.cli.main king d5               # demo the D2→D5 progression
```

## Content machine (`content_machine.py`)

Platform-aware social content helpers, ported as a **rewrite** from an
external source concept (see `docs/SOURCE_SYNC_PROTOCOL.md` — no source
text was copied). Content generation only; never the network.

- **Platform specs** — documented limits, fold/truncation points, and
  hashtag budgets for LinkedIn, X, Instagram feed/stories, TikTok, and
  newsletter (`PLATFORM_SPECS`, `platform_spec()`).
- **Hook formulas** — rhetorical patterns (contrarian, curiosity gap,
  specificity, negative, callout, slippery slope, permission) rendered
  from slot values with an honest rationale (`render_hook()`).
  Patterns, not promises: the docstring says what each pattern *is*,
  never that it will perform.
- **Builders** — `build_linkedin_post()`, `build_x_thread()`,
  `build_instagram_post()`, `build_newsletter()`; one entry point
  `format_for_platform()` that builds *and* validates.
- **Validators** — `validate_length()`, `validate_hook()`
  (banned-opener hygiene), `validate_content()`.

Relationship to `social.py`: `social.py` owns the sanitize contract
(markdown → clean caption + generated hashtags). The content machine
owns platform mechanics (limits, structure, hooks). King can call both;
posting still routes through the review queue and the confirmation-
gated plugin connector — the content machine never posts.

Registered skills (category `social`, risk INFO):
`social_content_format`, `social_hook_render`, `social_content_validate`.
