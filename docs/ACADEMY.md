# LEVI Boot Camp — 30-Day 24/7 Training Program

> **Product name: LEVI Boot Camp.** The CLI keeps the short name
> (`levi academy …`) but every user-facing surface — lessons, status,
> journal, docs — says **LEVI Boot Camp**. It is training boot camp:
> structured, high-tempo, honest about failure, and the standard does not move.

## The idea in one paragraph

Mass knowledge overload, **but retained**. Each session teaches in dense
layers — core concepts → extensions → edge cases → cross-links to other
tracks — at firehose pace but structured, never a dump. Retention is the
important half: every concept taught enters a registry with a spaced
review schedule; reviews are retrieval drills, never re-reading; sparring
interleaves concepts across tracks; weekly assessments and the graduation
crucible sample the *weakest* concepts first; forgetting is logged honestly
and re-queued. **Completion without retention is failure** — `levi academy
status` reports per-track retention (review drill hit rate), not just
sessions completed.

## Program shape

- **30 days × 4 blocks/day = 120 planned sessions**, around the clock:
  - Block 1 → **Track A — Defensive Security Analyst** (detection, analysis,
    hardening; strictly defensive-only, no offensive instruction ever)
  - Block 2 → **Track B — Platform Intelligence** (public-source research on
    the competitive landscape; every teardown ends adopt / adapt /
    deliberately-do-differently)
  - Block 3 → **Track C — LEVI Domain Mastery** (operate LEVI's real modules
    in hermetic, offline-safe drills)
  - Block 4 → **Synthesis / Sparring** (cross-track practicals; inherits the
    strictest boundary of every track involved)
- Intended cadence: **00:00, 06:00, 12:00, 18:00 America/Chicago**
  (see `core/levi/academy/schedule.json`). The worker runs the next
  uncompleted session in the 1–120 sequence, so missed blocks are caught up,
  never skipped.
- Weekly phases: **Days 1–7 Foundations · 8–14 Intermediate Methods ·
  15–21 Advanced Application · 22–30 Mastery + Synthesis**.
- Session 120 (Day 30, Block 4) is **graduation — the final crucible**.

By graduation the analyst track covers the full defensive craft, the
platform track covers the competitive landscape, and the domain track covers
every LEVI module deeply. "Best" here means strong structured foundations
and operational competence — not a claim of human-senior judgment.

## Battle rhythm (every session)

1. **Brief** — session, track, objectives, the bar (80%).
2. **Teach** — research the topic from public sources (offline fallback to
   LEVI's own materials, honestly reported), then synthesize an *original*
   lesson in LEVI's own words. Dense layers: core concepts → extensions
   (each concept pushed past comfort) → edge cases (where it breaks) →
   cross-links (prior concepts from other tracks, woven in by name).
3. **Review** — spaced-repetition retrieval drills on due concepts (see below).
   On days 7, 14, 21 the review runs in **weekly assessment** mode (more
   concepts, weakest first).
4. **Drill** — the practical exercise. Sparring blocks interleave concepts
   from other tracks: a platform-intel concept drilled inside an analyst
   exercise, on purpose.
5. **Test** — the mastery gate: **≥ 80% on the lesson, ≥ 70% on the drill**.
6. **Debrief** — journal honestly (pass *and* failure), consolidate
   growth-tagged learnings, ingest post-mastery knowledge.

## Mastery gates and remediation

- The bar is **80% mastery / 70% exercise**. Failed mastery is data, not a
  verdict — but the standard does not move.
- A failed gate **does not complete the session**: no progress credit, no
  corpus ingestion, no concept registration, and the track's pass streak
  resets to zero.
- The failure persists as `pending_remedial` (day, block, missed questions,
  missed objectives, attempt count). **The next run executes the remedial
  session before any new syllabus session** — remediation consumes the next
  block, so mastery takes precedence over calendar speed and the program may
  run past 120 wall-clock blocks. That is by design.
- The remedial re-teaches missed concepts **from a different angle**
  (attempt 1: worked example; attempt 2+: misconception confrontation),
  re-drills, and re-tests. A remedial pass completes the original gate and
  the *corrected* lesson is what enters durable memory. A remedial failure
  stays queued — the program never advances past a failed gate.
- Failures and remediations are journaled honestly with growth tags
  (`gate-failed`, `remediation`, `forgetting-logged`).
- Per-track **pass streaks** (current/best) are tracked and shown in status.

## Retention machinery

### Concept registry (`concepts.json`)

Every concept taught — each syllabus objective plus researched key terms —
gets an ID (`AD01B1O1`…), track, day introduced, and a review schedule.
Concepts are registered **only once the gate passes**: the registry holds
taught-to-mastery knowledge, not exposure.

### Spaced repetition

Each concept is re-drilled at expanding intervals: **next block (+1
session), next day (+4), +28, +56 sessions**. Reviews are **retrieval
drills** — the drill poses a question and measures whether durable memory
(the offline corpus + the journal) can reconstruct the concept. Never
re-reading. The first review is open-book (consolidation); later reviews are
closed-book (the concept's own introductory records are excluded — the true
retention test). Each session budgets time for new material **plus** due
reviews (capped per session, weakest and most overdue first).

### Forgetting is expected

A drill score below 60% is **forgetting**: it is logged honestly in the
journal (`forgetting-logged`), the concept's strength drops, and an extra
review is re-queued. Forgetting is data — the system re-teaches, it does not
pretend.

### Interleaving

Sparring blocks deliberately mix concepts across tracks. The drill artifact
must name the interleaved concepts and show them shaping the exercise —
vague cross-references do not count. Lessons also cross-link: each new
lesson explicitly revisits prior cross-track concepts by name, which builds
the elaborative network the retention drills later measure.

### Cumulative assessment

Weekly assessments (days 7/14/21) and the graduation crucible sample from
**all prior concepts, weakest first** — per-concept scores are tracked all
program. The crucible grades **A, B, and C separately** (closed-book
retrieval), names the **weakest track**, and prescribes it as the
**post-graduation drill focus**.

### Retention score

`levi academy status` shows per-track **retention — review drill hit rate**
alongside completion. Completion without retention is failure; the status
screen says so, and the number that matters is the hit rate.

## Dual memory and corpus quality

- **Growth journal** = experiential memory (what was learned, when, what
  failed, what was forgotten and re-queued).
- **Offline corpus** (`core/levi/brain/train/corpus_academy.jsonl`) =
  parametric memory, via the graduation retrain.
- **Corpus quality rule: ingest only post-mastery knowledge.** The runner
  ingests a lesson exclusively on gate pass (or remedial pass) — the
  distilled, corrected, retained version — tagged with its mastery level
  (`mastery_score`, `exercise_score`, `attempts`, `remediated`). The brain
  trains on verified knowledge, not first drafts.
- Graduation merges the base corpus with the academy corpus and retrains
  with the original hyperparameters (600 steps, seed 1337, CPU) into a
  **versioned** checkpoint — the existing weights are never overwritten.
  If torch is unavailable, the worker records an honest skip.

**Honest limitation:** `tiny-gpt` is a proof-of-learning ~3.3M-parameter
character model. It demonstrates that LEVI's own training loop works
end-to-end; it is not a reasoning-capable replacement for larger local
models.

## Track boundaries (non-negotiable)

- **Track A is defensive-only.** Detection, analysis, threat hunting, DFIR,
  monitoring, vulnerability assessment, hardening. Never attack execution
  instructions, payloads, exploit code, brute forcing, or cracking tutorials.
- **Track B** uses public sources only and ends every teardown with
  adopt / adapt / deliberately-do-differently.
- **Track C** proves claims against real LEVI modules in isolated,
  offline-safe drills; advisory-only where money or publishing is involved.
- **Sparring** inherits the strictest boundary of every track involved.

## CLI

- `levi academy status` — day/phase, 120-session progress, per-track bars,
  pass streaks, per-track retention, pending remediation, corpus stats.
- `levi academy session --day N --block M` — run one session explicitly.
- `levi academy` (no args) — run the next uncompleted session, or the queued
  remedial if one is pending.

## Files

- `core/levi/academy/syllabus.json` — the 30-day outline (120 sessions).
- `core/levi/academy/run_session.py` — the session worker (battle rhythm,
  gates, remediation, graduation).
- `core/levi/academy/concepts.py` — concept registry + spaced repetition.
- `core/levi/academy/synthesize.py` — original lesson synthesis (dense layers).
- `core/levi/academy/session_exercises.py` — deterministic exercise runners.
- `core/levi/academy/research.py` — public-source research w/ offline fallback.
- `core/levi/academy/corpus_ingest.py` — post-mastery corpus ingestion.
- `core/levi/academy/retrain.py` — graduation retrain launcher.
- `core/levi/academy/schedule.json` — intended 24/7 cadence spec.
- `~/.levi/academy/` — progress, streaks, concepts registry, lesson artifacts
  (`LEVI_ACADEMY_DIR` overrides; tests use tmp dirs).
