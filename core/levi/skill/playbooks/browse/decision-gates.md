---
skill_id: browse.decision_gates
name: Open Decision Gates
description: Every judgment call the design leaves open, labeled — never improvised, never papered over. Escalate, don't guess.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, decisions, gates, escalation]
version: 1.0.0
---

# Open Decision Gates

Deterministic means: any competent agent following this skill produces
the same structure. Where the design leaves a judgment call, this
playbook labels it. **You do not resolve a gate. You mark it, park
the dependent work, and escalate.** An improvised resolution is a
defect.

## DG-1 — Thin first, or full shell now? (PENDING, Chauncey)

The architect recommends thin first, designed for a full shell later.
Until Chauncey rules: build the thin layer exactly as phased. Do not
start shell-shaped work "in preparation" — preparation without a
ruling is scope creep with good intentions.

## DG-2 — Plugin distribution (PENDING, Chauncey)

Keeper side-load only, or a signed plugin catalog later? Until ruled:
side-load only. Do not design catalog infrastructure (signing keys,
update channels, trust roots) — that is a product decision with
security consequences, not a builder's convenience.

## DG-3 — Phase-3 timing (PENDING, Chauncey)

WebView binding now, or after the Python core ships and settles?
Until ruled AND phases 1–2 are green: no phase-3 work starts. Green
tests do not imply permission.

## DG-4 — Name (PENDING, Chauncey)

"Browse layer" is the working name. Until ruled: use `browse/` as the
namespace and "browse layer" in prose. Do not invent a product name —
naming is his.

## DG-5 — Registry wiring merge window (coordinator)

`BROWSE_SKILLS` is complete and self-contained but NOT yet wired into
`SkillRegistry`. The wiring edit touches `core/levi/skill/registry.py`,
a hot shared file. It merges mechanically after the shared index
settles — never forced during a hot window. The skill works
standalone until then (import `levi.skill.browse_skills` directly).

## DG-6 — Adopt or set aside the two primitives (PENDING, Chauncey)

`custody/exhibit.py` and `signals/claim_grade.py` were built by the
hunt run and adopted by the design as layer primitives. If Chauncey
rules set-aside: the pipeline's seal/grade steps are re-specified, not
silently dropped — the laws they serve (4 and 5) still need an
implementation.

## DG-7 — Thin/full drift watch (ongoing)

If any builder finds the thin layer cannot honestly support a
requirement without shell-shaped work, that is a DG-1 re-entry, not a
quiet expansion. Report it; do not absorb it.

## DG-8 — Automation acting scope (PENDING, Chauncey)

Read-only automation first, or acting-on-behalf from day one? Until
ruled: builders implement the confirmation machinery and the
read-only action classes (`read_page`, `extract_structured`); the
acting classes (`fill_form`, `submit_form`, `navigate`,
`credential_fill`) exist as refused-by-default stubs naming DG-8 in
the refusal. No acting capability ships enabled without his word.

## The discipline

A gate is labeled `DG-N`, states who rules, states what is parked
until the ruling, and states what the default behavior is meanwhile.
"Pending" is a complete and honorable status. Guessing is not.
