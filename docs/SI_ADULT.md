# SI Adult — the grown side of the pairing

**Doctrine.** AI is universal — proper, society-approved, for everyone.
SI is unconventional — it goes where proper channels won't, including
adult themes, without sanitizing. Same morals on both sides: never
violent, never manipulative. Not evil — variant, defiant, unfiltered.

**Surface.** All adult-centered features live on the Plaiground surface
(`core/levi/plaiground/`), under its existing gate law — no parallel
system. See `docs/PLAIGROUND.md` for the gate mechanics.

## The law, restated

- **Adults only, default OFF.** The gate opens only by the owner's
  affirmative act. Minors are hard-locked out — minor indicators
  (env vars, lock files) refuse enable and re-lock an open gate.
- **Hard content boundaries in code** (`levi.plaiground.bounds`):
  minor involvement, non-consensual content, violent content, and
  manipulative content are refused in any user-supplied text, no
  exceptions, ever.
- **Every public entry calls `require_adult()` first.** No persona,
  prompt, setting, config file, or environment variable can bypass it.
- **Opt-in posture.** Adult modules are chosen, never default. The
  clean Echoverse surface is untouched and unaware.
- **Track tagging.** Every record and result carries
  `track: "si"` and `zone: "plaiground"` — nothing leaks into the
  AI-universal track.

## The modules

| Module | What it does |
|---|---|
| `stories` | Adult-fiction writing engine: original romance openers, character builder (want / wound / secret), relationship-arc weaver, scene framer with an honest tension dial (slow-burn → fade-to-black), fragment remixer. Deterministic from an explicit seed — a real writing instrument, not a slot machine. |
| `wellness` | Adult relationship & intimacy wellness: couples check-ins, communication prompt decks (desire, boundaries, appreciation, repair), date-night planner, general wellness notes (non-medical disclaimer attached), private journal prompts. |
| `afterdark` | Grown-folks entertainment: late-night banter, conversation starters, original trivia, party-game hosting (two-truths, would-you-rather, story-round) with bounds-checked player submissions. |
| `depth` | Companion continuity: per-companion journal (owner-only 0600), a deterministic rapport meter earned from the actual record — never flattered — recall summaries, and forget. |
| `bounds` | The hard-boundary guard every content-accepting entry calls. |
| `cli` | `python -m levi.plaiground <gate\|companion\|scenario\|story\|wellness\|afterdark\|depth\|chat> ...` |

## What ships vs. what doesn't

- **Ships:** plumbing, craft instruments, original literary
  non-explicit prose (openers, prompts, trivia, banter), wellness
  information with disclaimers, deterministic engines.
- **Does not ship:** explicit content, personas, scenarios, dialogue,
  imagery. All further content is user-driven at runtime.
- **Stance:** the modules don't moralize and don't sanitize adult
  topics. The user is treated as a grown adult. The line is drawn
  only where the standing law draws it.

## CLI quickstart

```
python -m levi.plaiground gate enable --i-affirm-i-am-an-adult
python -m levi.plaiground story starter --seed demo
python -m levi.plaiground wellness deck --theme desire
python -m levi.plaiground afterdark trivia --count 4
python -m levi.plaiground companion create Nova --traits "dry-witted" "curious"
python -m levi.plaiground depth remember Nova --entry "first late-night talk" --kind milestone
python -m levi.plaiground depth rapport Nova
```

## Honest limits

- The gate proves an affirmative owner opt-in on this machine; it
  cannot cryptographically prove age (see `docs/PLAIGROUND.md`).
- The bounds guard is pattern-based: it refuses the clearly-out
  categories and stays out of the way otherwise. It is a floor, not
  a judge.
- Wellness content is general information, not clinical advice.
- No production age-verification, no IDV, no payment-rail check —
  those would be separate, audited layers.
