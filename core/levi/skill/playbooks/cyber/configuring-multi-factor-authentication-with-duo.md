---
skill_id: cyber_configuring_multi_factor_authentication_with_duo
name: Configuring Multi-Factor Authentication with Duo
description: Practitioner guide to deploying Duo MFA across applications, VPNs, and servers with enrollment, policy, and phishing-resistant options.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, authentication, hardening]
version: 1.0.0
---
## Purpose
Passwords alone fail; multi-factor authentication is the single highest-leverage identity control. This playbook deploys Duo MFA -- integrating applications, VPNs, and servers, driving user enrollment, setting sensible policies, and moving toward phishing-resistant factors where it matters most.

## When to use
- Rolling out MFA organization-wide for the first time.
- Extending MFA to VPN, RDP, SSH, and on-premises applications.
- Reducing MFA fatigue and push-bombing risk.
- Meeting cyber-insurance or compliance MFA requirements.

## Prerequisites
- Duo account with administrative access and licensing sized for the user base.
- Inventory of applications and access paths to protect, prioritized by risk.
- User directory integration (AD, Entra ID, or Google Workspace).
- Communication plan for enrollment and support.

## Procedure
1. Integrate the directory. Connect Duo to the identity source; verify user sync and group mappings for policy targeting.
2. Protect the highest-risk access first. Start with VPN, privileged accounts, and email; expand to all applications in phases.
3. Choose authentication methods. Prefer phishing-resistant options (security keys, platform biometrics) for privileged users; configure allowed methods per policy.
4. Harden against fatigue attacks. Enable number matching or biometric confirmation for push; set policies limiting consecutive push attempts.
5. Drive enrollment. Run enrollment campaigns with deadlines, manager accountability, and help-desk support; track enrollment rates by department.
6. Integrate applications. Use SSO, RADIUS, LDAP proxy, or native integrations per application type; test each before cutover.
7. Define bypass and recovery. Create a secure, audited process for temporary bypasses and lost-device recovery; never leave permanent bypasses.
8. Monitor and improve. Review authentication logs for anomalies, track bypass usage, and report MFA coverage to leadership.

## Expected outputs
- Duo MFA protecting prioritized applications and access paths.
- Enrollment completion with department-level tracking.
- Hardened policies against push fatigue and secure recovery procedures.

## Pitfalls
- Push-only MFA without number matching is vulnerable to fatigue attacks.
- Permanent bypass accounts become the attacker's target; audit and expire them.
- Enrolling without a deadline leaves the long tail unprotected indefinitely.
- Help-desk social engineering to reset MFA; verify identity rigorously.

## References
- Duo (Cisco) deployment documentation
- CISA guidance on phishing-resistant MFA
- NIST SP 800-63B, Digital Identity Guidelines: Authentication and Lifecycle Management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
