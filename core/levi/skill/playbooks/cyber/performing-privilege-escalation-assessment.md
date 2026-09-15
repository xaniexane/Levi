---
skill_id: cyber_performing_privilege_escalation_assessment
name: Privilege Escalation Assessment
description: Identify privilege escalation paths during authorized assessments and build detections and hardening to close them.
risk: low
permissions: []
requires_confirmation: false
tags: [privesc, assessment, hardening]
version: 1.0.0
---

## Purpose
- This playbook covers authorized assessment of privilege escalation weaknesses plus detection and hardening; it is not a guide to escalating privileges on systems without authorization.
- Find misconfigurations and weak controls that let attackers move from foothold to administrator or root.
- Prioritize fixes by exploitability and blast radius so the most dangerous paths close first.
- Build detections for escalation techniques so attempts are caught even where hardening lags.

## When to use
- During authorized vulnerability assessments and penetration tests with escalation in scope.
- When hardening servers and workstations against lateral movement and privilege abuse.
- After incidents where attackers escalated privileges, to find and close the paths they used.
- When tuning EDR and SIEM detections for privilege escalation techniques.

## Prerequisites
- Written authorization covering the target systems and the assessment techniques permitted.
- A test environment or maintenance window for any active validation, to avoid production impact.
- Baseline knowledge of the platform's privilege model: Windows tokens and privileges, Linux sudo and capabilities, cloud IAM.
- Logging in place so assessment activity can be distinguished from real attacker activity.

## Procedure
1. Confirm authorization and scope in writing, including whether active exploitation attempts are permitted or if the assessment is configuration-only.
2. Inventory privileged accounts, groups, and roles on each target system and in the directory or IAM service.
3. Review service and application configurations for classic escalation vectors: unquoted service paths, writable service binaries, weak scheduled tasks.
4. Check credential storage: unattended credentials in scripts, Group Policy preferences, and accessible memory or vaults.
5. Assess token and delegation configurations: unconstrained delegation, weak Kerberos settings, over-broad sudo rules.
6. Evaluate patch levels for known local privilege escalation vulnerabilities relevant to the OS build.
7. For each confirmed path, document prerequisites, the resulting privilege level, and the blast radius.
8. Recommend hardening per finding: least privilege, credential hygiene, configuration fixes, and patching.
9. Build or tune detections for the techniques assessed, mapping each to ATT&CK privilege escalation techniques.
10. Retest after remediation to confirm the paths are closed and detections fire correctly.

## Expected outputs
- An escalation-path register with prerequisites, impact, and remediation for each finding.
- Hardening recommendations prioritized by risk.
- Detection rules mapped to ATT&CK for the assessed techniques.
- A retest report confirming closed paths and working detections.
- Hardening baselines updated with the configuration fixes validated during the assessment.

## Pitfalls
- Actively exploiting escalation on production systems without explicit permission; configuration review is often sufficient.
- Reporting theoretical paths without validating prerequisites, which wastes remediation effort.
- Fixing the exploited path but missing equivalent paths on other systems; assess the fleet, not just the sample.

## References
- NSA guidance on mitigating privileged access risks
- MITRE ATT&CK privilege escalation tactics, https://attack.mitre.org/tactics/TA0004/
- Microsoft Learn documentation on Windows privileges and access tokens
- NIST SP 800-53 access control family
- CIS Benchmarks for the assessed platforms
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
