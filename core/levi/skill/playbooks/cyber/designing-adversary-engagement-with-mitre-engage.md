---
skill_id: cyber_designing_adversary_engagement_with_mitre_engage
name: Designing Adversary Engagement with MITRE Engage
description: Plan defensive adversary-engagement operations using the MITRE Engage framework to waste attacker time and gather intel.
risk: info
permissions: []
requires_confirmation: false
tags: [deception, strategy, threat-intel]
version: 1.0.0
---
## Purpose

Use MITRE Engage — the framework for planning adversary-engagement (deception) operations — to design activities that deny, disrupt, and degrade attackers while collecting intelligence on their TTPs. This is defensive deception planning: slowing and studying the adversary, never attacking back.

## When to use

- Building a deception program beyond ad-hoc honeypots (engagement operations with objectives).
- Planning how to respond when an intruder is detected in a deception environment: observe, misdirect, or expel.
- Justifying deception investments to leadership with a structured framework.
- Training defenders on adversary-engagement tradecraft within legal and ethical bounds.

## Prerequisites

- Written authorization for deception operations, with legal review of applicable laws (CFAA, wiretapping/ECPA considerations, entrapment concerns are minimal for defenders but document anyway).
- Defined objectives: what you want to learn or achieve (TTP collection, dwell-time measurement, protecting real assets).
- A deception environment or instrumented production segments where engagement can occur safely.
- Rules of engagement: what defenders may and may not do (observe and misdirect; never hack back, never leave your network to retaliate).

## Procedure

1. **Learn the Engage structure.** MITRE Engage organizes activities into approaches (e.g. precision engagement vs. tailored engagement) and activities mapped to adversary goals: collect (gather intel on the adversary), detect (identify their presence), direct (influence their actions), disrupt (interfere with their operations), and reassure (validate your defenses). Map your objectives to these categories first.
2. **Define the operation's objective and scope.** Write a one-page concept: the adversary behavior you're targeting (e.g. credential theft, lateral movement), what you want to achieve (collect their tooling? measure dwell time? protect the real asset by misdirection?), and the boundaries (which systems, what data is fake, when to terminate the engagement).
3. **Design the engagement environment.** Build or designate the space: decoy networks with instrumented hosts, fake data that looks valuable, and breadcrumb trails (documents, credentials, shares) that lead the adversary into the engagement zone and away from production. Every element should answer: what will the attacker do here, and what will we learn from it?
4. **Plan the activity sequence.** Using Engage activities, script the operation: detect their entry into the deception environment, collect their tooling and commands (full packet capture, keystroke-level logging where legal), direct them toward richer decoys with planted leads, and disrupt by feeding false information or silently blocking their real objectives. Plan decision points: when do we observe versus when do we expel?
5. **Instrument for intelligence collection.** Deploy comprehensive logging in the engagement environment: network capture, endpoint telemetry, and application logs — all centralized and retained. The intelligence product (TTPs, tooling, infrastructure) is the primary output; design collection before the operation starts, not during.
6. **Establish termination criteria.** Define in advance what ends the engagement: adversary approaching real assets, risk to production, legal boundary reached, or objectives achieved. Have the kill-switch tested — the ability to isolate the engagement environment instantly. An engagement without an exit plan is a liability.
7. **Execute with strict operational security.** Limit knowledge of the operation to the engagement team. Adversaries who know they're in a deception environment change behavior; insiders who know may interfere. Log all defender actions for the after-action review.
8. **Produce the intelligence product and after-action report.** Document: adversary TTPs observed (mapped to ATT&CK), tooling and infrastructure collected, dwell time and actions taken, what worked in the deception design, and recommended defensive improvements. Feed TTPs into detection engineering and share sanitized findings with your ISAC.

## Expected outputs

- A written engagement concept with objectives, scope, boundaries, and termination criteria.
- An instrumented deception environment producing adversary TTP intelligence mapped to ATT&CK.
- An after-action report feeding detections and defensive improvements.

## Pitfalls

- Engaging without legal review — deception is defensive, but collection methods (keystroke logging, packet capture) have legal constraints.
- No termination criteria — the engagement drifts and the adversary reaches real assets.
- Collecting without a plan for the intelligence — gigabytes of logs nobody analyzes.
- Overly complex deception the team can't maintain — start with simple, instrumented decoys.
- Confusing engagement with retaliation — defenders observe, misdirect, and expel; they never attack the adversary's infrastructure.

## References

- MITRE Engage (engage.mitre.org) — framework, activities, and operational guidance
- NIST SP 800-53 SC-26 (honeypots) and SI-4 (system monitoring)
- CISA guidance on active defense and deception (defensive scope)
- MITRE ATT&CK — mapping collected TTPs to techniques
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
