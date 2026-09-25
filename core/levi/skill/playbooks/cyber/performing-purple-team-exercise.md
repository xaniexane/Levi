---
skill_id: cyber_performing_purple_team_exercise
name: Purple Team Exercise
description: Plan and run collaborative purple team exercises where offense and defense improve detections together in real time.
risk: low
permissions: []
requires_confirmation: false
tags: [purple-team, exercise, detection]
version: 1.0.0
---

## Purpose
- Bring red and blue teams together to test defenses against realistic adversary scenarios.
- Improve detections during the exercise itself, not weeks later in a report.
- Build shared understanding of attacker tradecraft and defender visibility.
- Produce measurable improvement in detection coverage for the scenario's techniques.

## When to use
- When the organization wants to move beyond point-in-time penetration tests to continuous defense validation.
- When a specific threat actor or technique set needs focused defensive attention.
- After major control deployments, to prove they work against realistic activity.
- As a recurring program, typically quarterly, to keep detections sharp.

## Prerequisites
- Executive sponsorship and written authorization with defined scope and rules of engagement.
- Red and blue team participants with agreed roles, plus a facilitator to keep the exercise on track.
- A scenario based on a real threat actor or technique chain relevant to the organization.
- Test or production-safe targets with SOC coordination and a defined abort process.

## Procedure
1. Define exercise objectives: which techniques or actor behaviors will be emulated and what success looks like.
2. Build the scenario from threat intelligence, mapping each planned action to ATT&CK techniques.
3. Agree rules of engagement: allowed systems, forbidden actions, communication channels, and abort criteria.
4. Brief all participants including the SOC, with exercise identifiers for alert correlation.
5. Execute the scenario in phases, pausing after each phase for the blue team to review what fired and what did not.
6. Tune or create detections live during pauses, then continue the scenario to validate the improvements.
7. Capture every action with timestamps so alerts and logs can be correlated precisely.
8. Hold a hot-wash immediately after: what worked, what failed, and which gaps remain.
9. Write the exercise report with technique-by-technique detection status and remediation owners.
10. Track remediation to completion and rerun key scenario elements to confirm the fixes.
11. Archive scenario materials so the exercise can be repeated or adapted for new teams.
12. Feed lessons into detection engineering backlogs and threat-hunting hypotheses.

## Expected outputs
- An exercise report with per-technique detection results and gap remediation plans.
- Improved detections validated during the exercise.
- Reusable scenario materials and a stronger red-blue working relationship.
- A detection engineering backlog prioritized from exercise findings.
- Participant feedback improving the next exercise's realism and pacing.

## Pitfalls
- Letting the exercise become a red-team show with no blue-team learning; structure pauses for defense review.
- Skipping the remediation tracking; untested gaps found in exercises tend to stay open.
- Choosing scenarios disconnected from the organization's actual threat model.
- Running exercises so aggressively that production is impacted; keep within the agreed rules.
- Exercising without the actual on-call staff misses the people who will respond at 3 AM.

## References
- MITRE Caldera documentation for automated adversary emulation
- MITRE ATT&CK for scenario design, https://attack.mitre.org/
- SANS purple team methodology resources
- NIST SP 800-53 control CA-8
- CISA adversary emulation and assessment resources
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
