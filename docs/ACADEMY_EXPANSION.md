# Academy Expansion — Methods, Learning Science, Subjects

The full teaching system, folded into the academy build. Composes with the
differentiators — it wires into them, never duplicates them.

## Methods (`core/levi/academy/methods.py`)

Six methods — how the academy teaches, not just what:

- **Spaced repetition.** `next_review(learner_id, skill_id, threshold=0.8)`
  layers on the decay model: `review_in_days = 30 * log2(1/threshold)` —
  reviews land just before forgetting. Unseen or decayed skills are due now.
- **Interleaving.** `interleave(subjects, per_subject=2)` round-robins
  subjects into one mixed session. Blocked chapters are the enemy; the
  learner practices *choosing* the right tool, not just using it.
- **Feynman drills.** `feynman_drill(topic, key_points)` prompts the trainee
  to teach it back; `grade_explanation` scores key-point word coverage
  (≥50% per point, ≥60% overall). Pattern-based floor — not a human examiner.
- **Shadow mode.** `shadow_assignment` → observe a graduate's live work;
  `complete_observation` (notes ≥ 20 chars) unlocks `takeover`, which runs
  the task through the nursery workload router mid-task. Verified pass mints
  a sealed receipt; failure auto-composts.
- **Pressure drills.** `pressure_drill(scenario_id, prompt, time_limit_s,
  expected_keywords)`; `submit_pressure` passes only when correct **and**
  on time. Overtime fails — the clock is part of the test. Misses
  auto-compost into remediation drills.
- **Socratic interrogation.** `interrogate(topic, claims)` generates five
  cross-examination questions per claim (define terms, steelman the opposite,
  what evidence would change your mind, edge case, hidden assumption).
  `grade_cross_examination` scores engagement: keyword coverage plus
  substance. Cross-examines reasoning, not recall.

State under `<LEVI_HOME>/academy/methods/`, owner-only, stdlib only.

## Learning science (`core/levi/academy/science.py`)

Five principles from the science of learning, each an executable instrument:

- **Retrieval practice.** `create_retrieval_drill` hides the facts from the
  prompt; `score_recall` measures what surfaces unaided (≥40% of a fact's
  keywords). Recognition is not recall.
- **Elaboration.** `elaboration_prompt(concept, related)` demands the
  mechanism; `score_elaboration` requires both terms plus causal language
  (because, therefore, leads to…).
- **Dual coding.** `dual_code_prompt` requires a verbal explanation **and**
  a structural ASCII map; `score_dual_code` passes only when both channels
  carry weight (≥2 labeled connected nodes).
- **Desirable difficulty.** `difficulty_tiers` escalates guided →
  unassisted → degraded (harder than the field, on purpose);
  `recommend_tier` escalates after two passes, steps down on any fail.
- **Metacognition.** `rate_confidence` per answer, `resolve_answer` on
  outcome, `metacognition_report` grades calibration A–F by Brier score —
  the same `brier_score` math as the stake-under-fog drills. Calibration is
  one skill with two instruments.

## Subjects (`core/levi/academy/subjects.py`)

Fourteen subjects beyond defensive analysis, each blue-team framed, each
mapped to a real exercise runner (`run_exercise` accepts every one):

threat intel · defensive OSINT tradecraft · digital forensics fundamentals ·
behavioral malware triage (safe — static only, never execute) · network
traffic analysis · secure code review · social-engineering defense ·
cryptography literacy · cloud posture · privacy engineering · purple-team
vs our own systems (authorized) · incident-report writing · briefing
non-technical stakeholders · LEVI canon operator training (organs, receipt
doctrine, money law).

Integration with the existing syllabus/ladder/lesson structures:

- Every subject emits day-entries shaped exactly like `syllabus.json`
  entries: `{title, objectives, key_questions, exercise_type}`.
- `as_track()` builds the catalog as a syllabus track
  (**D — Fieldcraft & Canon**); `merge_into(syllabus)` returns a *copy*
  with the track merged — the caller's syllabus is never mutated.
- `study_plan(learner_id, subject_id, mix_with=...)` wires subjects to
  methods: spaced-repetition reviews per objective, one interleaved
  session mixing two subjects, one Feynman drill per objective.

## Gates

- **Malware triage:** static analysis only. There is no sandbox here, so
  behavioral reasoning stays on paper. Handling live malware outside an
  isolated lab is forbidden.
- **Purple-team:** `authorize_purple_team` requires a named human approver
  and explicit scope (systems, techniques, window, abort conditions),
  Veil-sealed and tamper-evident. `check_purple_authorization` raises
  `PermissionError` without it and `SealError` on tamper. Own systems only.
  Defensive blue-team only — offensive material is never integrated.

## Tests

`tests/test_academy_methods.py` (11), `tests/test_academy_science.py` (8),
`tests/test_academy_subjects.py` (8) — all green, home-scoped, no network.
