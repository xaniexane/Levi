# Plaiground — the adult-SI surface

**Spelling is law: "Plaiground", not "playground".** The clean, default,
minor-friendly side is the **Echoverse**. There is no third zone, and the
two are never merged: Plaiground is *powered by* Echoverse branching
underneath (taken / not-taken / wild, in `core/levi/organs/echo.py`),
but it is a separate surface with its own law.

## The gate law

The age gate is the core deliverable. It is adult-only and **default
OFF**. Minors are hard-locked out, enforced in code at every entry point:
companion creator, simulator, chat, and photo hooks. **No persona
definition, prompt, setting, config file, or environment variable can
bypass the gate.**

### The one lawful path

1. The owner performs an affirmative, non-default act: call
   `levi.plaiground.gate.enable_adult_mode(CONFIRMATION_PHRASE)` —
   or the equivalent `python -m levi.plaiground.gate enable
   --i-affirm-i-am-an-adult` — with the exact confirmation phrase.
2. No minor indicator may be present. Minor indicators are:
   - environment variables `LEVI_MINOR`, `LEVI_MINOR_MODE`,
     `PLAIGROUND_MINOR` set to a truthy value, or
   - a lock file (`.minor-lock` / `minor.lock`) in `~/.levi/` or
     `~/.levi/plaiground/`.
   
   If any is present, enable **refuses** — and a minor indicator
   appearing later re-locks an already-enabled gate, because
   `verify_adult()` checks indicators on every call.
3. Enable writes an owner-only record at
   `~/.levi/plaiground/gate.json` with mode `0600`. `verify_adult()`
   re-checks on every call: file exists, mode is exactly `0600`,
   file uid equals the process uid, and the record has the exact
   shape `enable_adult_mode` wrote (`enabled: true`,
   `affirmed: "explicit-owner-opt-in"`, matching `owner_uid`).

### What cannot open the gate

- Environment variables (any of them — tests prove `PLAIGROUND_ENABLED=1`
  and friends do nothing).
- Hand-written or edited config records (wrong shape, wrong permissions,
  or wrong affirmation marker all fail closed).
- Direct function calls with clever arguments (`require_adult()` runs
  before any other work in every public function).
- `python -m levi.plaiground.gate enable` without the affirmative flag.

### Bypass proofs

`tests/test_plaiground_gate.py` exists to prove the bypasses fail: gate
off by default, env-var tricks, config edits, corrupt/permissive
records, wrong confirmation phrases, minor indicators present at enable
time, and minor indicators appearing after enable. All tests are
hermetic (tmp home, never the real `~/.levi`).

## The plumbing

| Module | What it does |
|---|---|
| `levi.plaiground.gate` | The gate: `enable_adult_mode`, `disable_adult_mode`, `verify_adult`, `require_adult`, `status`. |
| `levi.plaiground.companions` | Companion creator: define a persona (name, traits, boundaries), stored per-owner as 0600 JSON under `~/.levi/plaiground/companions/`. Neutral defaults; no shipped persona content. |
| `levi.plaiground.simulator` | Scenario runner. Takes a user-provided scenario + companion and runs it through `levi.organs.echo.run_echo` — the clean Echoverse engine — rendering taken/not-taken/wild branches as companion scenario beats. `echo.py` is imported, never modified. |
| `levi.plaiground.chat` | `ChatSession`: a tailored chat loop over a companion. Replies are deterministic (traits + tone + history + one Echoverse beat per turn). Tones are whitelisted to non-explicit options (`warm`, `playful`, `witty`, `calm`, `curious`, `poetic`, `grounded`); nothing else is accepted and no explicit presets ship. |
| `levi.plaiground.photos` | Photo-generation capability contract only. `PhotoBackend` is the interface a future backend would implement; the only wired backend is `procedural`, which wraps the in-repo offline generator `levi.media.local` (deterministic generative art — gradients, glow, geometry — honest scope: procedural art, NOT photorealistic synthesis, NOT likenesses). No external/cloud image backend is wired here, on purpose. `request_photo` returns metadata (`PhotoResult`), never raw bytes, and checks the gate before touching any backend. |
| `levi.plaiground.bounds` | Hard content boundaries in code: refuses minor involvement, non-consensual content, violent content, and manipulative content in any user-supplied text. Every new content-accepting entry point calls `check_bounds` after the gate check. |
| `levi.plaiground.stories` | Adult-fiction writing engine: original romance openers, character builder (want/wound/secret), relationship-arc weaver, scene framer with an honest tension dial (slow-burn → fade-to-black), fragment remixer. Deterministic from an explicit seed. |
| `levi.plaiground.wellness` | Adult relationship & intimacy wellness: couples check-ins, communication prompt decks (desire, boundaries, appreciation, repair), date-night planner, general wellness notes with a non-medical disclaimer, private journal prompts. |
| `levi.plaiground.afterdark` | Grown-folks entertainment: late-night banter, conversation starters, original trivia, party-game hosting (two-truths, would-you-rather, story-round) with bounds-checked player submissions. |
| `levi.plaiground.depth` | Companion continuity: per-companion journal (owner-only 0600), a deterministic rapport meter earned from the actual record, recall summaries, and forget. |
| `levi.plaiground.cli` | Unified command tree: `python -m levi.plaiground <gate|companion|scenario|story|wellness|afterdark|depth|chat> ...` (top-level `levi plaiground` hook staged for `cli/main.py`). |

No explicit content lives in code, tests, docstrings, or docs. All
content is user-driven at runtime. Companion defaults are neutral;
tone parameters ship no explicit presets. The SI stance on this
surface is variant, defiant, unfiltered — grown users treated like
grown users — with the same morals as every LEVI track: adults only,
lawful and consensual, never violent, never manipulative.

## What's intentionally NOT built

- **No real age verification.** A local-only gate cannot prove a human's
  age the way a government-ID or payment-instrument check could. What it
  does guarantee: the surface is unreachable by accident, by default,
  by configuration, by prompt trickery, or by any accepted input — only
  a deliberate, owner-recorded act opens it, and any minor indicator
  slams it shut again. If a deployment needs stronger verification
  (IDV, payment rail, parental-control attestation), that must be built
  as a separate, audited layer — see the honest gap below.
- **No photorealistic image generation.** No weights, no cloud image
  APIs, no likeness synthesis. The stub contract exists so a future
  backend can be registered without changing the gate; registration
  itself is gate-checked and never weakens enforcement.
- **No content library.** Plaiground ships zero personas, zero
  scenarios, zero dialogue, zero imagery. The plumbing reflects and
  branches user-supplied content only.
- **No merging with the Echoverse.** The clean surface stays clean:
  `levi.organs.echo` has no knowledge of Plaiground, and the simulator
  uses it strictly as an engine.

## Honest gap

Local-only verification has a ceiling: this gate proves an affirmative,
owner-authenticated opt-in on this machine, with minor indicators
hard-locking it. It cannot cryptographically prove the operator's age,
and a determined adult with shell access to the owner's account could
always run the enable command themselves — that is inherent to any
local gate without external identity proof. For deployments where that
ceiling matters (shared devices, family machines), the minor-indicator
mechanism (env var + lock file) is the intended hook for parental
control or MDM tooling to force the gate closed — but the external
attestation layer itself is not built here.
