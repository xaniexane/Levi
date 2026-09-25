---
skill_id: cyber_performing_ssl_tls_security_assessment
name: SSL/TLS Security Assessment
description: Assess TLS configurations across servers and services for weak protocols, ciphers, and certificate issues.
risk: low
permissions: []
requires_confirmation: false
tags: [tls, assessment, hardening]
version: 1.0.0
---

## Purpose
- Find weak TLS configurations: outdated protocols, weak ciphers, and certificate problems.
- Prioritize fixes by exposure: internet-facing services first, then internal.
- Establish a repeatable assessment the team can run after every infrastructure change.

## When to use
- During infrastructure security assessments and pre-launch reviews.
- After protocol vulnerabilities are disclosed, to find affected systems quickly.
- When standardizing TLS configuration across load balancers, servers, and appliances.
- As a recurring scan, typically monthly for external and quarterly for internal.

## Prerequisites
- An inventory of TLS endpoints: IPs, hostnames, and ports.
- Scanning tools such as testssl.sh or SSL Labs methodology, approved for the target scope.
- A TLS baseline policy: minimum version, approved ciphers, and certificate requirements.
- Change windows for remediation on production services.

## Procedure
1. Confirm authorization for scanning, especially for third-party or customer-facing endpoints.
2. Enumerate TLS endpoints from asset inventory, CMDB, and certificate transparency logs.
3. Scan each endpoint for supported protocol versions, flagging anything below TLS 1.2.
4. Review cipher suites: flag weak, null, export, and anonymous ciphers and ciphers without forward secrecy.
5. Check certificate validity: expiry, hostname matching, chain completeness, and revocation status.
6. Test for known vulnerabilities: Heartbleed-style issues, ROBOT, DROWN, and compression-based attacks.
7. Check HSTS, secure renegotiation, and session resumption settings.
8. Assess certificate management: validity periods, key sizes, and whether automation is in place.
9. Rank findings by exposure and exploitability; internet-facing weak TLS goes first.
10. Provide remediation configurations per platform: web servers, load balancers, and appliances.
11. Verify fixes with rescans and confirm no client compatibility breakage beyond the approved baseline.
12. Schedule recurring scans and trend the results.

## Expected outputs
- A per-endpoint TLS assessment with graded findings.
- Platform-specific remediation configurations.
- Rescan evidence confirming fixes and trend data.
- A TLS configuration standard published for infrastructure teams.
- Integration of TLS scanning into vulnerability management SLAs.

## Pitfalls
- Scanning without authorization; even benign TLS scans can alarm third parties.
- Disabling TLS 1.0 and 1.1 without checking legacy client impact first.
- Fixing the web tier while forgetting mail servers, VPNs, and appliances with weak TLS.
- Grading only the best-configured endpoint behind a load balancer.

## References
- NIST SP 800-52 Rev 2 for detailed configuration guidance
- NIST SP 800-52 Guidelines for TLS
- Mozilla SSL configuration generator documentation
- SSL Labs rating guide methodology
- IETF RFCs for TLS 1.2 and 1.3
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
