---
skill_id: factory.signal_triage
name: Signal Triage
description: Applies a deterministic 1-10 triage to demand signals; no invented scores, no invented signals.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, demandpulse, signals, triage]
version: "1.0.0"
---

# Signal Triage

Applies a deterministic 1-10 triage to demand signals. The score follows
the rules below — nothing invented, nothing rounded up quietly.

## How to triage

- 1–3: faint signal — mentioned once, no corroboration.
- 4–6: real signal — corroborated or repeated, small scale.
- 7–8: strong signal — money or repeat demand visible.
- 9–10: exceptional — only with hard evidence (orders, deposits,
  signed commitments). A 10 is almost never given.

## Laws

1. Never invent a signal — every triaged signal is cited.
2. Never inflate a score — the number follows the rules above.
3. Demand-pulse direction is sensing; triage advises, never decides.
4. Direction-fit scoring rides alongside when available.

## Limits

- Never acts on a signal; never posts, publishes, or replies.
- Never promises an outcome from a score — a 9 is not a sale.

## Notes

- Pairs with DemandPulse scanning: scan → score → surface.
