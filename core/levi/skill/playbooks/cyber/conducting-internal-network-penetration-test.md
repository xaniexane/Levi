---
skill_id: cyber_conducting_internal_network_penetration_test
name: Conducting Authorized Internal Network Penetration Tests
description: Practitioner guide to planning and executing authorized internal network penetration tests, from scoping to remediation validation.
risk: info
permissions: []
requires_confirmation: false
tags: [network, assessment, pentest]
version: 1.0.0
---
## Purpose
An internal network pentest assumes the attacker is already inside -- via a compromised workstation, malicious insider, or rogue device -- and measures how far they can go. This playbook structures authorized internal testing: scoping, rules of engagement, methodology from network access to domain dominance, and reporting that prioritizes fixes by real-world impact.

## When to use
- Assessing lateral-movement risk and internal segmentation effectiveness.
- Meeting compliance requirements for periodic internal testing.
- Validating Active Directory hardening and credential hygiene.
- Establishing a baseline before a major network architecture change.

## Prerequisites
- Written authorization with defined network ranges, excluded systems, and testing windows.
- Rules of engagement: permitted techniques, data-handling rules, emergency contacts.
- Test starting point defined (for example, standard workstation access or network drop).
- Coordination with SOC to distinguish test traffic from real incidents.

## Procedure
1. Confirm scope and authorization. Document in-scope ranges, out-of-scope systems (safety-critical, fragile legacy), and get signed approval.
2. Establish the foothold scenario. Agree on the starting position and any provided credentials; document assumptions explicitly.
3. Enumerate the internal network. Map hosts, services, shares, and trust relationships within scope using approved scanning methods.
4. Assess credential exposure. Check for default, weak, or reused credentials and exposed credential material per the rules of engagement.
5. Test lateral movement paths. Evaluate how an attacker could move between systems and escalate privilege, focusing on misconfigurations and excessive trust.
6. Assess Active Directory security. Review Kerberos, LDAP, group policies, and privileged-group membership for common weaknesses.
7. Demonstrate business impact carefully. Show what data or control is reachable without exfiltrating or disrupting real operations.
8. Report, remediate, retest. Deliver findings ranked by exploitability and impact with concrete fixes; verify remediation with targeted retesting.

## Expected outputs
- Pentest report with evidenced findings and remediation guidance.
- Attack-path documentation showing lateral-movement routes.
- Retest confirmation of critical fixes.

## Pitfalls
- Scope creep into out-of-scope or production-critical systems causes outages and liability.
- Failing to coordinate with the SOC triggers full incident response on test traffic.
- Credential testing without rules risks account lockouts; agree on lockout policies first.
- Reports listing vulnerabilities without attack paths get deprioritized by IT.

## References
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- MITRE ATT&CK enterprise matrix for technique coverage
- CISA guidance on Active Directory and network hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
