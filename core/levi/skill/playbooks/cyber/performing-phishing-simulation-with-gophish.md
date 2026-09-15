---
skill_id: cyber_performing_phishing_simulation_with_gophish
name: Phishing Simulation with Gophish
description: Run authorized phishing simulations with Gophish to measure susceptibility, train staff, and improve email defenses.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, awareness, gophish]
version: 1.0.0
---

## Purpose
- Measure how susceptible the organization is to phishing with controlled, authorized simulations.
- Turn simulation results into targeted training for the people and departments that need it most.
- Validate that email security controls and SOC detection actually catch realistic phishing lures.
- Track improvement over time with consistent metrics leadership can understand.

## When to use
- As part of a recurring security awareness program, typically quarterly.
- After a real phishing incident, to test whether the lessons stuck.
- When onboarding new departments or after organizational changes that bring in new staff.
- Before high-risk periods such as tax season or major corporate announcements that attackers exploit.

## Prerequisites
- Written authorization from leadership and legal, including approval of lure themes and target scope.
- Gophish deployed on infrastructure that will not be mistaken for a real attack, with allowlisted sending domains or IPs.
- Coordination with the SOC and help desk so simulation reports are recognized and not treated as incidents.
- A landing page and training module ready for users who click, plus a reporting mechanism such as a phish-report button.

## Procedure
1. Get written approval for the campaign: target groups, lure themes, sending infrastructure, and schedule.
2. Notify the SOC, help desk, and mail administrators of the campaign window and how to distinguish it from real attacks.
3. Configure the Gophish sending profile with proper SPF, DKIM, and DMARC alignment on an approved domain.
4. Build the email template and landing page, keeping lures realistic but avoiding themes that cause genuine distress.
5. Set up user groups, excluding anyone under active investigation or on approved exemption lists.
6. Launch the campaign in a staggered send to avoid overwhelming the help desk and to mimic real attack pacing.
7. Monitor results: open rates, click rates, credential submissions, and reports to the SOC or abuse mailbox.
8. Deliver just-in-time training to users who clicked, focusing on the specific red flags in the lure they received.
9. Analyze results by department, role, and repeat-offender status to target follow-up training.
10. Brief leadership on trends, not just raw click rates, and compare against previous campaigns and industry benchmarks.
11. Feed successful lures into email gateway tuning and SOC detection content.
12. Archive campaign data per the retention policy and schedule the next simulation.

## Expected outputs
- Campaign metrics: delivery, open, click, submit, and report rates by group.
- Targeted training completions for at-risk users.
- Detection and control improvements derived from the lures that succeeded.
- A repeat-offender coaching plan for users who fail multiple simulations.
- Benchmark comparisons against prior campaigns and industry data.

## Pitfalls
- Running simulations without SOC coordination, which burns analyst time on a fake incident.
- Using lures that embarrass or frighten staff; the goal is education, not punishment.
- Punishing clickers instead of training them, which teaches people to hide mistakes rather than report them.
- Measuring only click rates while ignoring the report rate, which is the metric that actually stops real attacks.

## References
- SANS Security Awareness planning resources
- Gophish official documentation
- NIST SP 800-50 Building an Information Technology Security Awareness and Training Program
- CISA phishing guidance and report-phishing resources
- ENISA threat landscape reports on social engineering trends
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
