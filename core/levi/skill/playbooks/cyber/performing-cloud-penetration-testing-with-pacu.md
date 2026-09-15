---
skill_id: cyber_performing_cloud_penetration_testing_with_pacu
name: Control Validation with Pacu
description: Validate AWS least-privilege controls and detection coverage using Pacu in authorized lab tenants.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, assessment, aws]
version: 1.0.0
---

## Purpose

Pacu is an AWS security-assessment framework whose modules exercise real API calls — the same calls an attacker with stolen credentials would make. Used defensively and only in tenants you own (lab, staging, or a dedicated assessment account), it answers two questions no checklist can: do my IAM policies actually enforce least privilege, and do my detections fire when someone abuses the permissions that remain? This playbook covers scoping, safe module selection, and converting results into control improvements. It is control validation, not unauthorized testing.

## When to use

- Validating IAM least-privilege after a policy refactoring or new service rollout.
- Testing whether your CloudTrail alerting and GuardDuty coverage detect privilege-abuse patterns.
- Purple-team exercises where the "red" actions must be safe, repeatable, and scoped.
- Pre-production security gates for new AWS accounts or landing zones.
- Demonstrating control effectiveness to auditors with executed evidence rather than screenshots of policies.

## Prerequisites

- Written authorization naming the exact AWS accounts/regions in scope; assessment accounts should be isolated from production with no trust relationships to it.
- A dedicated assessment IAM principal whose permissions mirror the scenario under test (e.g., "developer role as actually granted").
- Pacu installed in a controlled runner (analyst VM or container), with session logging enabled.
- Baseline knowledge of the detections you expect to fire, so you can measure coverage gaps.
- Rollback plan for any module that creates resources (keys, users, functions) — enumeration-only first, mutating modules only with explicit approval.

## Procedure

1. **Define the scenario and success criteria.** Write down what you are validating: e.g., "a compromised developer key cannot escalate to admin" or "enumeration of IAM users triggers our CloudTrail alert within 15 minutes." Vague testing produces vague results.
2. **Build the isolated target.** Use a dedicated assessment account that mirrors production IAM structure but contains no real data. Confirm no VPC peering, resource policies, or role trusts connect it to production.
3. **Start with enumeration modules.** Run Pacu's discovery modules (IAM, EC2, S3, Lambda enumeration) as the test principal. Record exactly which APIs succeed — every successful call the scenario should not allow is a least-privilege finding.
4. **Test privilege boundaries.** Attempt the escalation paths relevant to your policies: `iam:PassRole` combinations, policy version manipulation, and role assumption chains. Stop at proof of capability — demonstrating that an API call succeeds is sufficient evidence; actually creating persistent backdoors is unnecessary and risky.
5. **Measure detection, not just prevention.** For each action taken, check whether your monitoring fired: CloudTrail alerts, GuardDuty findings, SIEM rules. A blocked action nobody detected and an allowed action nobody detected are different failures — record both.
6. **Clean up thoroughly.** Remove every artifact the modules created: access keys, users, policies, functions, and test data. Re-run enumeration to confirm the account is back to its pre-test state, and revoke the assessment principal's credentials.
7. **Convert results to control changes.** For each finding, specify the fix: tighter IAM policy (with the exact statement), a new detection rule, or an architectural change (permission boundaries, SCPs). Prioritize by what the test principal could actually reach.
8. **Report with evidence.** Document the scenario, modules run, API-level results, detection outcomes, and remediation. Executed test evidence is far more persuasive to engineering teams and auditors than theoretical policy review.

## Expected outputs

- Scoped test plan with scenarios, success criteria, and authorization records.
- Enumeration results showing the effective permissions of the test principal.
- Privilege-boundary test outcomes: which escalation paths succeeded or failed.
- Detection coverage assessment: which test actions fired alerts and which were silent.
- Remediation backlog: policy fixes, new detections, and architectural changes with owners.

## Pitfalls

- Running Pacu modules against production accounts — enumeration alone can trigger rate limits, cost spikes (e.g., resource creation), and operational alerts.
- Mutating modules without cleanup: leftover access keys and users become real attack surface.
- Confusing "the API call was denied" with "we would have detected it" — prevention and detection are separate controls; test both.
- Scope creep into accounts or regions not authorized; cloud APIs make it easy to wander.
- Treating a clean Pacu run as proof of security — it validates the scenarios you tested, nothing more.

## References

- Pacu project documentation (Rhino Security Labs)
- AWS IAM documentation (policy evaluation logic, permission boundaries)
- MITRE ATT&CK T1078 (Valid Accounts), T1548 (Abuse Elevation Control Mechanism)
- NIST SP 800-53 controls AC-6 (Least Privilege) and AU-6 (Audit Review)
- AWS CloudTrail documentation for detection validation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
