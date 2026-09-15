---
skill_id: cyber_conducting_network_penetration_test
name: Conducting Authorized Network Penetration Tests
description: Practitioner guide to planning and executing authorized external and internal network penetration tests with defensible methodology.
risk: info
permissions: []
requires_confirmation: false
tags: [network, assessment, pentest]
version: 1.0.0
---
## Purpose
Network penetration testing validates that exposed services, misconfigurations, and weak credentials cannot be turned into compromise. This playbook provides the full methodology for authorized testing -- external perimeter and internal network -- from scoping through reporting, emphasizing proof of impact without disruption.

## When to use
- Assessing perimeter or internal network security posture.
- Meeting compliance requirements for periodic penetration testing.
- Validating network segmentation and firewall effectiveness.
- Establishing a security baseline for a new environment.

## Prerequisites
- Written authorization with IP ranges, domains, excluded systems, and testing windows.
- Rules of engagement: allowed techniques, data handling, emergency contacts.
- SOC coordination to distinguish test activity from real attacks.
- Defined objectives: what questions the test must answer.

## Procedure
1. Confirm scope and rules. Document targets, exclusions, windows, and get signed authorization before any active testing.
2. Perform reconnaissance. Gather DNS records, IP ranges, and service banners within scope using non-disruptive methods first.
3. Enumerate services. Identify open ports and services; fingerprint versions to find known vulnerabilities.
4. Assess vulnerabilities. Validate scanner findings manually; prioritize by exploitability rather than CVSS alone.
5. Attempt controlled exploitation. Demonstrate impact (access achieved, data reachable) without disrupting services or exfiltrating real data.
6. Test credentials carefully. Check for default and weak credentials per the agreed policy, respecting lockout thresholds.
7. Document attack paths. Show how findings chain together from initial access to meaningful impact.
8. Report, remediate, retest. Deliver prioritized findings with evidence and fixes; verify critical remediations.

## Expected outputs
- Pentest report with evidenced findings ranked by real-world risk.
- Attack-path documentation.
- Retest results for critical findings.

## Pitfalls
- Scanning outside the authorized scope, even accidentally, is unauthorized access.
- Aggressive scanning or exploitation causing outages destroys trust.
- Scanner-only reports without manual validation are full of false positives.
- Failing to notify the SOC triggers expensive incident response on test traffic.

## References
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- MITRE ATT&CK enterprise matrix
- OWASP Testing Guide (for web-facing components)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
