# Factory spec — bg-remover (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-008`
- **Kind:** `venture`
- **Source:** profit-ranked report 2026-09-24, Chauncey's 2026-09-24 full-speed order
- **Status:** spec'd

## Purpose

AI background remover (#400). Fit 8/10 — improves resale listing photos for
the mystery-box/resale chain. This spec is the venture STARTER for a later
dedicated build thread.

## Starter design

- Pipeline: upload → mask → transparent PNG. Local-first, stdlib-friendly
  masking first; heavier models only when paid revenue funds them.
- Batch mode for listing-photo sets (fits the resale chain).
- Pricing: $3/mo tier. Code-only until profitable: no paid GPU, no paid
  APIs, no ad spend until revenue exists and he approves.

## Laws

1. Code-only until profitable — no spending without his word after revenue.
2. No accounts, public surface, or payments until he approves each gate.
3. Honest output limits: masking quality is stated plainly; no "AI magic"
   claims.
4. Dynasty eyes-only for canon/IP material.

## Registry target

- Future build thread: `core/levi/ventures/bg_remover/` (does not exist yet).

## Proof plan

- Spec-only: no code, no tests. Proof = spec review against laws + honest
  limits (Notes).

## Out of scope (gated on his word)

Live product, billing, public surface, paid model APIs, spending.

## Builder

- Glyph: 🧵

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*

## Notes (honest limits)

- Design package only; no code exists yet.
- Venture build is a separate thread, parked until he dispatches it.
