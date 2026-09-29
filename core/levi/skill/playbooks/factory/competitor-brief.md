---
skill_id: factory.competitor_brief
name: Competitor Brief
description: Reads DemandPulse competitor state and writes a plain-speech competitor brief for the morning brief.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, demandpulse, competitors, brief]
version: 1.0.0
---

# Competitor Brief

Reads DemandPulse competitor state and writes a plain-speech brief (prices,
tactics, user-base signals) for the morning brief. Advisory only: reads and
reports; never posts, never scrapes aggressively, invents nothing. Polite
reads stay polite.

## How to write the brief

1. Read the competitor state (seeded competitors + extracted price/tactic/
   user-base dimensions from the scan upgrade).
2. For each competitor, one plain-speech block:
   - **Prices:** what they charge now, and what changed since last brief.
   - **Tactics:** what they're doing (launches, promos, positioning shifts).
   - **User-base signals:** what scannable signals say about their users.
3. Every number is cited to a scan source or labeled projection. A number
   with no source is not printed — the gap is stated instead.
4. Close with 1–3 plain-speech implications for our line (what changed,
   what it suggests — never a command, never a decision made).

## Example

```
Competitor: Acme SaaS
Prices: $29/mo (unchanged since 2026-09-20; source: pricing page scan)
Tactics: launched annual plan $290/yr (source: blog scan 2026-09-23)
User-base: forum chatter up on r/smallbusiness (projection, unverified)
Implication: annual-plan pressure on our monthly tiers — worth a pricing
review, not a pricing decision.
```

## Laws

- Polite reads only: keyless/public sources, never hammering.
- Cited or labeled: numbers carry sources or the word "projection".
- Never posts, publishes, replies, or writes anywhere.
- The brief advises; decisions stay with Chauncey.
