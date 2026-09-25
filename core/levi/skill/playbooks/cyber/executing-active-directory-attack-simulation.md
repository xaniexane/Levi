---
skill_id: cyber_executing_active_directory_attack_simulation
name: Executing Active Directory Attack Simulation
description: Run authorized Active Directory attack simulations to validate detections.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, purple-team, detection-validation]
version: 1.0.0
---
## Purpose

Active Directory is the keys-to-the-kingdom target in most intrusions — Kerberoasting, DCSync, delegation abuse, GPO manipulation. This playbook covers running authorized AD attack simulations (purple-team style) to validate that your detections actually catch these techniques: scoping, safe execution, measurement, and turning misses into detection improvements. Offensive tradecraft knowledge is applied only in authorized test environments for defensive validation.

## When to use

- You need to validate AD detection coverage (Kerberoasting, DCSync, delegation).
- New SIEM rules for AD attacks need testing before relying on them.
- Purple-team program expanding into identity/AD scenarios.
- Compliance requires testing of AD monitoring controls.

## Prerequisites

- Written authorization: scope (which domains/OUs/accounts), time window, permitted techniques, and emergency stop contacts.
- A test AD environment or tightly scoped production authorization — never broad production testing without explicit approval.
- SIEM/EDR detection inventory mapped to the techniques to be simulated.
- Safety controls: technique-by-technique execution, monitoring for unintended effects, rollback plan.

## Procedure

1. Define the technique list and expected detections. Select AD techniques to simulate (e.g., SPN enumeration + Kerberoasting, DCSync, unconstrained-delegation abuse, GPO modification, AdminSDHolder tampering). For each, record which detection should fire, at what severity, with what context. This mapping is the test plan — simulation without it is just noise.
2. Establish safety boundaries. Agree: no production credential exposure (use dedicated test accounts), no persistent changes without documented rollback (KRBTGT touches are off-limits in production-adjacent environments), monitoring by a dedicated observer, and an immediate-stop trigger (any unexpected production impact halts the exercise). Get sign-off from AD owners, not just security leadership.
3. Execute technique by technique with measurement. Run one technique, record start/stop times, verify whether the expected detection fired (and whether unexpected ones did — bonus coverage), then clean up before the next. Measure: time-to-detect, alert accuracy, and analyst triage quality. Technique batching without per-technique measurement wastes the exercise.
4. Test the evasive variants. After baseline techniques are detected, test realistic variations: Kerberoasting with AES tickets instead of RC4, DCSync from unexpected hosts, slow/low-volume variants. Detections that only catch the textbook version fail against real adversaries — variant testing is where the value is.
5. Convert misses to detection engineering. Every undetected technique becomes a ticket with: the telemetry gap (which log was missing), the proposed detection logic, and a re-test date. Prioritize by real-world prevalence — Kerberoasting and DCSync coverage before exotic delegation abuses.
6. Report honestly and re-test. Document detected/missed/partial per technique with evidence, present coverage deltas to stakeholders, and schedule re-testing after detection changes. Attack simulation is a validation loop — adversary techniques evolve, so the suite must too.

## Expected outputs

- Authorization record: scope, techniques, window, stop conditions, sign-offs.
- Technique-to-detection test plan with expected outcomes.
- Per-technique results: detection status, time-to-detect, evidence.
- Detection backlog from misses with re-test schedule.

## Pitfalls

- Simulating in production without AD-owner sign-off risks outages and trust — get explicit approval.
- KRBTGT and schema-level techniques can have forest-wide effects — exclude or isolate them.
- Running techniques without per-technique measurement produces activity, not validation.
- Testing only textbook variants creates false confidence — include evasive variations.
- Uncleaned test artifacts (accounts, SPNs, delegations) become real attack surface — verify cleanup.

## References

- MITRE ATT&CK: T1558 (Kerberoasting/DCSync), T1484 (Domain Policy Modification) — https://attack.mitre.org/; Microsoft Learn: AD security best practices; NIST SP 800-115 (security testing) for exercise methodology
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
