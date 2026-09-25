---
skill_id: cyber_executing_phishing_simulation_campaign
name: Executing Phishing Simulation Campaign
description: Run authorized phishing simulations that measurably improve resilience.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, awareness, simulation]
version: 1.0.0
---
## Purpose

Phishing simulations measure and improve human resilience — but poorly run programs punish users and teach nothing. This playbook covers running authorized, ethical phishing simulations: getting approval, designing realistic-but-fair lures, measuring the right metrics, and converting results into training that actually changes behavior.

## When to use

- Leadership wants a phishing-simulation program (new or improved).
- Click rates are high and you need a measurement-and-training loop.
- A real phishing incident revealed gaps a simulation program should address.
- Compliance requires security-awareness testing.

## Prerequisites

- Written authorization: HR, legal, and executive sponsorship — phishing simulations touch employees and need explicit approval.
- Simulation platform (commercial or built) with reporting, scheduling, and training-integration features.
- Baseline metrics definition: what you'll measure (click rate, report rate, credential-submission rate).
- Allowlisting: ensure simulated phish bypasses the email gateway (or the test measures the gateway, not users).

## Procedure

1. Get the governance right first. Document: who authorized the program, which groups are in/out of scope (executives included — exempting leadership undermines credibility), data handling for results (individual results stay with training/HR, never public shaming), and the no-punishment policy. Simulations perceived as traps destroy trust — the policy must be explicit and communicated.
2. Design fair, realistic lures. Base scenarios on real threats your organization faces (vendor invoice lures for finance, IT-helpdesk lures broadly, QR-code lures as they rise). Keep difficulty calibrated: lures should be catchable by a trained eye, not indistinguishable from legitimate mail. Vary difficulty across campaigns to measure improvement, and never use lures exploiting personal trauma or sensitive topics.
3. Measure report rate, not just click rate. The metrics that matter: credential-submission rate (the real failure), click rate, and — most importantly — report rate via the phishing-report button. A user who clicks then reports is a partial success; a user who silently deletes is neutral; a user who ignores the report button needs training on reporting. Track trends per department, not individuals, for program decisions.
4. Deliver immediate, constructive training. Users who fall for a simulation should get instant micro-training explaining the indicators they missed — delivered as coaching, not punishment. Repeat offenders get targeted training, not public exposure. The goal is behavior change; shame produces concealment.
5. Close the loop with the SOC. Feed simulation infrastructure (domains, sender patterns) to the SOC so real-vs-simulated triage is fast, share campaign timing so analysts aren't chasing ghosts, and use simulation results to tune email-gateway rules for the lure types users miss most. The program should improve technical controls too, not just humans.
6. Report trends, protect individuals. Report to leadership: organization and department trends, report-rate improvement, and training completion — never individual 'wall of shame' lists. Review the program annually: lure relevance, metric definitions, and whether click rates are actually declining. A flat trendline means the training isn't working — change the training, not the users.

## Expected outputs

- Authorization record: HR/legal/executive approval, scope, data-handling policy.
- Campaign plan: lure scenarios mapped to real threats, difficulty calibration, schedule.
- Metrics dashboard: click, credential-submit, and report rates trended per department.
- Training content linked to missed indicators, with completion tracking.

## Pitfalls

- Simulations without HR/legal approval create employment-law exposure — authorize first.
- Public shaming of clickers destroys trust and suppresses reporting — coach, don't punish.
- Measuring only click rate misses the point — report rate is the resilience metric.
- Lures that are impossible to detect teach helplessness, not vigilance — keep them fair.
- Exempting executives from simulations signals the program is theater — include everyone.

## References

- NIST SP 800-50 (security awareness program); CISA phishing guidance; SANS Security Awareness planning resources
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
