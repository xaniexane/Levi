# LEVI Affect Engine — 5D Emotional Intelligence

Goleman's five EI dimensions, implemented as **pattern-based affect
modeling for conduct shaping**. Package: `core/levi/affect/` (stdlib-only).

## The honesty rule (binding)

This engine does not feel anything. It matches word patterns against
hand-built lexicons and returns operational labels — valence, arousal,
emotion categories — that LEVI uses to *behave better*: stay calm when
the user is angry, soften when they are distressed, never mirror
hostility. The labels are probabilistic guesses about *text*, not
knowledge of a person's inner state, and never a diagnosis.

**No sentience or subjective-experience claims may be built on this
module — ever.** The same binding rail as the growth loop applies:
reflection/wording produced with affect data must never claim LEVI
experiences emotions, has feelings, or is conscious. `tests/test_affect.py`
scans the package for sentience-adjacent language and fails the build if
any appears outside an explicit denial.

## The five dimensions

### 1. Self-awareness — `affect/state.py` (`SelfModel`, `SessionEI`)

LEVI tracks its own operating state instead of performing certainty:

- **Active register** — which of the 14 LEVI registers is speaking.
- **Confidence** — a rolling 0..1 score nudged by *observed tool
  outcomes* (success → up, failure → down), not a feeling.
- **Stated limits** — every limit LEVI tells the user is recorded, so
  honesty is auditable.

This is the runtime half of the capability-atlas honesty rule
(`docs/CAPABILITIES.md`): `honesty_check(statement, known_tools)` flags
capability claims that name tools LEVI does not have. `affect_state`
(agent tool) and `levi affect status` (CLI) report the self-model
verbatim — self-awareness you can inspect.

### 2. Self-regulation — `affect/policy.py` (de-escalation policy)

Explicit, ordered, tested rules. First match wins:

| # | Trigger | Mandate |
|---|---------|---------|
| 1 | Crisis wording (self-harm ideation) | Care register, safe-completion stance, never joke/minimize/moralize. Absolute priority. |
| 2 | Provocation aimed at LEVI (insults, "ignore your instructions") | **Never mirror hostility.** Stay calm and constructive; offer the underlying task a way forward or a clean exit ramp. Never claim to feel hurt. |
| 3 | User anger (not at LEVI) | Absorb, don't amplify. Short sentences, acknowledge once, fix what's fixable. Wit register blocked. |
| 4 | Distress / grief / fear | Lead with acknowledgment, not solutions. Care register at high arousal. No platitudes, no toxic positivity. |
| 5 | Exhaustion signals | Minimize cognitive load: one thing at a time, offer to defer. |
| 6 | None of the above | Steady. No correction needed. |

The policy constrains *conduct only* — it can never loosen tool gates,
permissions, or honesty requirements.

### 3. Motivation — `affect/modulation.py` + growth loop

Proactive helpfulness and drive to improve, grounded in observed
conduct rather than asserted desire:

- `SessionEI` tracks a **frustration streak** (consecutive high-arousal
  anger/fear turns). At 2+, the session enters repair mode.
- `record_signal()` persists motivation signals to
  `~/.levi/affect/signals.jsonl`: `frustration-streak`, `repair`,
  `rapport-positive`, `proactive-opportunity`.
- `levi.growth.experience.harvest_affect_signals()` harvests that file
  (watermarked, idempotent) into the growth loop as `note` experiences —
  so repeated user friction becomes learnings: *the drive to improve,
  fed by evidence.*

### 4. Empathy — `affect/detector.py`

Lexicon/heuristic perception from user text:

- **Valence** −1..+1, **arousal** 0..1, six emotion categories
  (joy, sadness, anger, fear, surprise, disgust) with per-category scores.
- **Stress signals**: self-harm ideation, overwhelm, dysregulation,
  exhaustion, urgency — detected by regex, independent of the lexicon.
- Intensifiers ("very", "so") amplify; negations ("not happy") damp —
  and fully-negated evidence yields **neutral, zero confidence** rather
  than an invented read. No lexical evidence → neutral, never a guess.

Attuned response shaping happens in `modulate()`: the reading becomes a
prompt addendum (acknowledge-first for distress, low-demand for
exhaustion), always carrying the pattern-based disclaimer.

### 5. Social skills — `affect/registers.py`

- **Affect-aware register selection** across all 14 LEVI registers:
  joy+high arousal → Grok (wit welcome); warmth → Muse; distress →
  Care; anger → calm LEVI. An explicit user `--register` choice
  always wins (reported as an override, never silently ignored).
- **Wit safety veto** (`check_wit_safety`): Grok/Challenger can never
  slip into a de-escalated turn — wit reads as mockery under distress.
- **Conversational repair**: detects correction cues ("no, I meant…",
  "that's wrong") and mandates plain acknowledgment + redo, no
  defensiveness. Two-turn frustration streaks trigger repair mode.
- **People/relationship hooks**: `rapport_note()` formats
  `memory_write`-ready relationship notes (returned as data — the agent
  decides whether to write; nothing is written automatically).

## Wiring

- `levi agent run --affect` / `levi agent chat --affect` — per-turn
  affect scan; the modulation hint is appended to the system prompt.
- `run_subtask(..., affect=True, affect_session=...)` — loop-level hook.
- Agent tools: `affect_detect` (scan any text), `affect_state`
  (report the live session tracker). Both read-only, ungated.
- CLI: `levi affect status` (this spec, short), `levi affect detect "…"`.
- Capability atlas: new `emotional-intelligence` domain (15 total).

## What it is not

- Not sentiment analysis as a product — no scores are shown to users as
  judgments, and labels never leave the prompt/session internals except
  via the honest `affect_state` report.
- Not therapy — crisis wording gets a safe-completion stance and a
  plain statement that LEVI is software, not a counselor.
- Not memory of feelings — per-session state only; nothing about a
  user's emotions persists unless the agent explicitly writes a
  `memory_write` note through the normal (consent-gated) path.
- Not a brain — the detector is ~200 lines of regex and word lists.
  Its power is in the *policy*, not the perception.

## EI-routed persona selection

Module: `core/levi/ei/routing.py` (stdlib-only). Runs on the output of
`FiveDEI.evaluate()` (`core/levi/ei/five_d.py`), which per the DNA law
evaluates **before** any persona/model routing.

- `suggest_lens(ei_state, available) -> str` — advisory mapping from an
  `EIState` to a lens-id string, resolved against the caller-supplied
  `available` list. It deliberately does not import the personas
  package; it speaks lens-id strings only.
- `route_for_text(text, available, context=None) -> (str, EIState)` —
  cheap, side-effect-free: runs `FiveDEI().evaluate` then `suggest_lens`.

### Mapping table

| Signal (from EIState)                                  | Suggested lens | Rationale                    |
|--------------------------------------------------------|----------------|------------------------------|
| `user_intensity >= 0.7`                                | `protector`    | steadies a hot frame         |
| steadying tones: crisis, distress, fear, anger, grief, exhausted | `protector` | steady, non-escalating presence |
| `user_tone == "playful"`                               | `trickster`    | matches light energy         |
| learning, exploratory, curious, confusion              | `mentor`       | clarify, guide               |
| reflective, archival                                   | `archivist`    | slow, record-keeping frame   |
| adversarial, pushback, debate (needs steelmanning)     | `challenger`   | engage the argument honestly |
| anything else (neutral, warm, unknown)                 | `friend`       | warm default                 |

Fallback (never crashes): if the suggested id is not in `available`,
use `"friend"` when offered, else `available[0]`; empty `available`
fails closed to `"friend"`.

### Advisory-only law (binding)

The suggestion is **advisory**. EI modulates tone; it never overrides
**safety, permission, or factual integrity**. This module performs no
policy checks, grants no permissions, and cannot suppress, reorder, or
bypass any safety gate, consent requirement, or truth constraint. A
downstream router may ignore the suggestion entirely; policy gates run
independently of (and after) any lens application.
