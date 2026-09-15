---
skill_id: cyber_performing_ssl_stripping_attack
name: SSL Stripping Detection and Prevention
description: Detect SSL stripping attacks on the network and harden applications with HSTS and secure defaults.
risk: low
permissions: []
requires_confirmation: false
tags: [tls, detection, hardening]
version: 1.0.0
---

## Purpose
- This playbook is defensive: detect SSL-stripping attacks and prevent them. It does not cover performing stripping attacks against networks you do not own or have permission to test.
- Teach analysts to recognize the signs of SSL stripping in traffic and user reports.
- Harden web applications and infrastructure so stripping attacks fail by default.
- Validate defenses through authorized testing in controlled environments.

## When to use
- When users report security warnings disappearing or HTTP where HTTPS is expected.
- When assessing network segments where adversary-in-the-middle attacks are a concern.
- During application security reviews, to verify HSTS and secure redirect behavior.
- When threat intelligence warns of stripping toolkits targeting your users.

## Prerequisites
- An inventory of web applications with their HTTPS and HSTS configurations.
- Network visibility or endpoint telemetry to observe HTTP versus HTTPS usage.
- An authorized test lab if active validation of defenses is planned.
- Coordination with network operations for any defensive testing.

## Procedure
1. Verify HSTS deployment on all applications: header presence, max-age, includeSubDomains, and preload submission.
2. Check redirect behavior: HTTP to HTTPS redirects must not carry sensitive data or session tokens.
3. Review mixed-content handling: applications must not load active content over HTTP.
4. Ensure cookies are flagged Secure so they are never sent over plaintext connections.
5. Monitor for stripping indicators: unexpected HTTP traffic to HTTPS-only applications and certificate warnings followed by HTTP sessions.
6. Analyze proxy and DNS logs for signs of adversary-in-the-middle positioning preceding stripping.
7. In authorized lab testing, validate that HSTS-preloaded clients refuse to downgrade.
8. Harden the network path: prefer encrypted DNS, deploy certificate pinning for critical mobile apps, and segment untrusted networks.
9. Educate users to recognize missing HTTPS indicators and to report them rather than proceeding.
10. Add stripping-detection checks to SOC monitoring for high-value applications.

## Expected outputs
- An HSTS and secure-defaults compliance assessment for web applications.
- Detection coverage for stripping indicators in SOC monitoring.
- Hardening recommendations for applications and network paths.
- A user awareness module on recognizing downgrade attacks.
- Periodic revalidation of HSTS preload status for key domains.

## Pitfalls
- Assuming HTTPS availability equals stripping resistance; without HSTS, the first connection is still vulnerable.
- Forgetting subdomains and API endpoints in HSTS deployment.
- Testing stripping techniques outside an authorized lab; on-path attacks on real networks are illegal without permission.
- Assuming VPNs make stripping irrelevant; the attack works wherever plaintext HTTP appears.
- Deploying HSTS without testing legacy clients that may not support it.

## References
- EFF guidance on HTTPS deployment best practices
- RFC 6797 on HTTP Strict Transport Security
- OWASP guidance on transport layer protection
- NIST SP 800-52 Guidelines for TLS
- HSTS preload list submission guidance, https://hstspreload.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
