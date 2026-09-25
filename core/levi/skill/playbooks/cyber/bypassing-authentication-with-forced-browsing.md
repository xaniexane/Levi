---
skill_id: cyber_bypassing_authentication_with_forced_browsing
name: Detecting and Preventing Forced Browsing Attacks
description: Defensive playbook for detecting forced-browsing authorization bypasses and hardening applications against direct object reference abuse.
risk: low
permissions: []
requires_confirmation: false
tags: [web, detection, hardening]
version: 1.0.0
---
## Purpose
Forced browsing -- guessing or manipulating URLs and parameters to reach resources the user should not access -- exploits missing server-side authorization checks. This playbook is written for defenders: how to detect forced-browsing attempts in logs, test your own applications for the flaw during authorized assessments, and harden applications so every request is authorized. It does not teach exploitation technique.

## When to use
- Investigating suspicious access to admin or other-user resources in web logs.
- Hardening applications after a forced-browsing finding in a pentest report.
- Building detections for authorization-bypass attempts at the WAF or application layer.
- Training developers on insecure direct object reference (IDOR) prevention.

## Prerequisites
- Web access logs with authenticated user identity and requested URLs.
- Application source code or architecture documentation for the hardening side.
- WAF or application-layer logging if available.
- Authorized assessment scope if you will test your own applications.

## Procedure
1. Define the sensitive surface. Inventory admin endpoints, user-specific resources, and predictable identifiers (sequential IDs, filenames) in the application.
2. Hunt in access logs. Look for authenticated users requesting resources outside their role, sequential ID enumeration patterns, and direct hits on admin paths without prior navigation.
3. Correlate with outcomes. Distinguish blocked attempts (403s) from successful access (200s with sensitive data); successful ones are incidents, not just probes.
4. Verify authorization server-side. For each sensitive endpoint, confirm the application checks the session user's rights on every request, not just hides the link.
5. Replace predictable identifiers. Use indirect reference maps or unguessable UUIDs for sensitive objects; never rely on obscurity alone.
6. Enforce centralized authorization. Route access decisions through a single authorization layer with deny-by-default; audit it regularly.
7. Add monitoring. Alert on repeated 403s followed by 200s, ID enumeration rates, and access to deprecated or hidden endpoints.
8. Test after fixes. Re-run the authorized assessment to confirm bypasses are closed; include forced browsing in regression testing.

## Expected outputs
- Detection rules for forced-browsing patterns in web logs.
- Hardened authorization checks with test evidence.
- Developer guidance on IDOR prevention.

## Pitfalls
- Client-side hiding of links is not authorization; attackers request URLs directly.
- Sequential IDs make enumeration trivial even with good auth checks elsewhere.
- Logging without user identity makes attribution of attempts impossible.
- Fixing one endpoint while leaving the API equivalent exposed.

## References
- OWASP Top 10: Broken Access Control
- OWASP Testing Guide: testing for forced browsing
- NIST SP 800-53, Access Control family
- MITRE ATT&CK: T1548-adjacent privilege concepts; CWE-639 (Authorization Bypass Through User-Controlled Key)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
