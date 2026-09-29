# Factory spec — baremetrics-alt (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-007`
- **Kind:** `venture`
- **Source:** profit-ranked report 2026-09-24, Chauncey's 2026-09-24 full-speed order
- **Status:** spec'd

## Purpose

Open-source Baremetrics alternative (#391). Fit 9/10 — the revenue proof
layer for DirectDepositDaemon: metric ingestion, MRR dashboards, honest
projection-vs-confirmed separation. This spec is the venture STARTER for a
later dedicated build thread.

## Starter design

- Metric ingestion: append-only JSONL deposits/metrics log, local-first.
- MRR dashboards: projection vs confirmed shown side by side, never summed;
  every number cited or labeled projection.
- Pricing: $9/mo tier. Code-only until profitable: no paid infra, no ad
  spend, no third-party billing until revenue exists and he approves.

## Laws

1. Code-only until profitable — no spending without his word after revenue.
2. No accounts, payments, or public surface until he approves each gate.
3. Honest ledger: confirmed vs projected never conflated; no invented
   revenue or customers.
4. Dynasty eyes-only for canon/IP material.

## Registry target

- Future build thread: `core/levi/ventures/baremetrics_alt/` (does not exist yet).

## Proof plan

- Spec-only: no code, no tests. Proof = spec review against laws + honest
  limits (Notes).

## Out of scope (gated on his word)

Live product, billing, public surface, spending — each its own gate.

## Builder

- Glyph: 🧵

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*

## Notes (honest limits)

- Design package only; no code exists yet.
- Venture build is a separate thread, parked until he dispatches it.
