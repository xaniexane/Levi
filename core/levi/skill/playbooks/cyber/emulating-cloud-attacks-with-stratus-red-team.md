---
skill_id: cyber_emulating_cloud_attacks_with_stratus_red_team
name: Emulating Cloud Attacks with Stratus Red Team
description: Validate cloud detections by safely emulating attack techniques with Stratus Red Team.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, purple-team, detection-validation]
version: 1.0.0
---
## Purpose

Stratus Red Team emulates cloud attack techniques (credential exfiltration, privilege escalation, persistence) in a controlled way so defenders can verify their CloudTrail/audit-log detections actually fire. This playbook is defensive: using adversary emulation to validate and improve detection coverage — run only in dedicated test accounts with explicit authorization, never in production.

## When to use

- You need to validate cloud detections against real attack techniques.
- Detection-engineering backlog needs cloud coverage verification.
- After building CloudTrail detections, you need to prove they work.
- Purple-team program expanding into cloud threat emulation.

## Prerequisites

- A dedicated AWS/GCP/Azure test account or subscription — isolated from production, with no production data or access.
- Written authorization for adversary emulation in the test environment.
- CloudTrail (or equivalent audit logging) enabled in the test account, feeding your SIEM/detection stack.
- Stratus Red Team installed on an operator workstation with test-account credentials; cleanup procedures understood.

## Procedure

1. Isolate the emulation environment. Confirm: the test account has no trust relationships with production, no production data, and billing alerts set. Document the authorized technique list and time window. Emulation in production 'because it's just logging' is prohibited — techniques like persistence and exfiltration have real effects even in test accounts.
2. Map techniques to your detections first. Before running anything, list which Stratus techniques map to which of your CloudTrail detections (e.g., credential-exfiltration techniques → your anomalous STS/IAM detections). Emulation without a detection-mapping step produces activity but no learning — the mapping is the test plan.
3. Execute techniques individually with baselining. Run one technique at a time: record the start time, execute, then check whether the expected detection fired with correct severity and context. Between techniques, verify the environment is clean (Stratus provides cleanup; verify it worked). Running techniques back-to-back without baselining makes attribution of detections impossible.
4. Detonate for persistence techniques carefully. Techniques that create persistence (backdoor IAM users, policy modifications) must be fully cleaned up and verified — an uncleaned test backdoor is a real vulnerability. Maintain a checklist per technique: what it creates, how Stratus cleans it, and how you verify cleanup independently.
5. Turn misses into detection backlog. Every technique that didn't fire as expected becomes a ticket: which log source was missing, which rule needs writing or tuning, and what the expected detection logic is. Prioritize by technique prevalence in real intrusions (credential theft and privilege escalation before exotic persistence).
6. Report and re-test. Document per-technique results (detected/missed/partial, with evidence), present coverage improvements to stakeholders, and re-run the suite after detection changes and quarterly. Emulation is a continuous validation loop, not a one-time exercise.

## Expected outputs

- Isolated test account with authorization records and billing alerts.
- Technique-to-detection mapping (test plan) before execution.
- Per-technique results: detected/missed/partial with evidence and cleanup verification.
- Detection backlog from misses, with re-test schedule.

## Pitfalls

- Running emulation in production or shared accounts risks real compromise — isolate strictly.
- Uncleaned persistence techniques leave real backdoors — verify cleanup independently.
- Executing techniques without mapping to detections first wastes the exercise.
- Some techniques generate real cloud charges or API effects — set billing alerts and scope carefully.
- One emulation run proves nothing about drift — re-test on a schedule.

## References

- Stratus Red Team documentation (stratus-red-team.cloud); MITRE ATT&CK Cloud matrix — https://attack.mitre.org/ (Cloud platform techniques); NIST SP 800-61 Rev. 2 (exercise planning)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
