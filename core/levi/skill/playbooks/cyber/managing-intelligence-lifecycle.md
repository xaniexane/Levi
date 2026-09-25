---
skill_id: cyber_managing_intelligence_lifecycle
name: Managing the Intelligence Lifecycle
description: Operate the day-to-day intelligence cycle: tasking, collection, analysis, and dissemination.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intelligence, lifecycle, operations]
version: 1.0.0
---
## Purpose
This playbook is the operational companion to lifecycle design: the daily and weekly rhythms that keep the intelligence cycle turning — intake triage, collection tasking, production scheduling, and stakeholder feedback.

## When to use
- A CTI team exists but work is reactive and unprioritized.
- Intelligence products ship late or miss the decisions they were meant to inform.
- You need to demonstrate the CTI function's operational value.

## Prerequisites
- Agreed priority intelligence requirements (PIRs) and a stakeholder list.
- Collection sources and analyst tooling (TIP, link analysis, writing templates).
- A tracking system for requirements, tasks, and products.

## Procedure
1. **Run intake triage daily.** Review new requirements, tip-offs, and RFIs; accept, defer, or decline each with a recorded rationale and deadline.
2. **Task collection explicitly.** Convert accepted requirements into collection tasks with source, method, and due date; track which PIR each task serves.
3. **Hold a weekly production meeting.** Review in-progress analysis, unblock stalled items, and confirm dissemination plans for the week's products.
4. **Write to template.** Use standard formats (one-page brief, indicator package, TTP assessment) so consumers know where to find the judgment, the evidence, and the confidence level.
5. **Disseminate on schedule.** Publish recurring products (weekly threat roundup, monthly strategic brief) reliably; ad-hoc products go through the same review bar.
6. **Track requirement satisfaction.** For each PIR, record whether it was answered, partially answered, or unanswerable with current collection — and why.
7. **Conduct quarterly retrospectives.** With stakeholders, review which products drove decisions and which were ignored; adjust PIRs and formats accordingly.

8. **Maintain a collection catalog.** Document every source's coverage, cost, and reliability so tasking decisions are informed, not habitual.
9. **Protect sources and methods.** Apply need-to-know to sensitive collection details; a leaked source is a lost source.

## Expected outputs
- Operating cadence: daily triage, weekly production, quarterly review.
- Requirement tracker linking PIRs to tasks to delivered products.
- Stakeholder satisfaction and product-utilization metrics.
- Example: the weekly threat roundup ships every Monday with three sections (actor activity, vulnerability watch, sector incidents), each item tagged to the PIR it answers and the decision it supports.

## Pitfalls
- Letting the loudest stakeholder's ad-hoc requests starve standing PIRs.
- Analysis that never ships because the bar for "finished" is perfection.
- Measuring output volume instead of decisions influenced.

- Letting the loudest stakeholder's ad-hoc requests starve standing PIRs; protect a fixed share of capacity for priority requirements.
- Analysis that never ships because the bar for "finished" is perfection; a timely good assessment beats a late perfect one.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- Sherman Kent-style analytic tradecraft references for structured analysis (CIA Center for the Study of Intelligence).
- "Psychology of Intelligence Analysis" (Heuer, CIA) — cognitive bias mitigation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
