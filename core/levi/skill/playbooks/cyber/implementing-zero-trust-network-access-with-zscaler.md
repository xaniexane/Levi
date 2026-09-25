---
skill_id: cyber_implementing_zero_trust_network_access_with_zscaler
name: Implementing ZTNA with Zscaler
description: Deploy Zscaler Private Access for brokered zero-trust application access.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, ztna, zscaler]
version: 1.0.0
---
## Purpose
This playbook deploys Zscaler Private Access (ZPA): application segments published through App Connectors, access policies driven by identity and posture, and full logging — replacing VPN with per-app zero-trust access.

## When to use
- Standardizing remote access on the Zscaler platform.
- Needing granular, audited access to private apps for employees and third parties.
- Reducing the attack surface of internet-exposed VPN concentrators.

## Prerequisites
- Zscaler tenant with ZPA licensed; admin access to the ZPA Admin Portal.
- Identity provider integrated (SAML/SCIM) and device posture signals available (e.g., via Zscaler Client Connector or MDM).
- Application inventory with hostnames/IPs, ports, and hosting locations for connector placement.

## Procedure
1. **Deploy App Connectors.** Place connectors near each application environment with outbound-only connectivity to the Zscaler cloud; size for throughput and redundancy.
2. **Define application segments.** Publish apps by FQDN or IP with ports and protocols; group by sensitivity so policies can differ between tiers.
3. **Build access policies.** Require identity, group membership, and posture (managed device, OS version, EDR status); use privileged remote access features for admin protocols.
4. **Configure the Client Connector.** Deploy with enforced profiles so users cannot disable it; validate split behavior for internet vs. private traffic.
5. **Enable logging and inspection.** Forward ZPA logs to the SIEM; enable TLS inspection policy where appropriate and legally permitted.
6. **Pilot and cut over.** Migrate a pilot group, verify every critical app works, then move cohorts off VPN and disable legacy access paths.
7. **Review continuously.** Audit segment definitions and policies quarterly; alert on policy changes and connector health.

8. **Use risk-based policy tuning.** Feed ZPA logs into risk scoring so repeated denied-access attempts from a user trigger step-up or review.
9. **Document the user experience.** Publish setup guides and a support path; ZTNA fails when users cannot self-serve basic connectivity issues.

## Expected outputs
- ZPA application segments with documented access policies.
- Connector deployment with health monitoring and redundancy.
- SIEM ingestion of ZPA access logs with allow/deny visibility.
- Example: an engineer on an unmanaged-device policy is denied production database access while retaining staging access, with the denial and policy reason logged for audit.

## Pitfalls
- Publishing entire subnets as segments instead of specific applications.
- Posture checks that exist in policy but never actually block non-compliant devices.
- Leaving the old VPN running indefinitely "just in case," preserving the attack surface.

- App Connector placement that backhauls traffic across continents; place connectors near the applications they serve and monitor latency.
- Defining segments by IP range instead of application identity, which reintroduces network-based trust through the back door.

## References
- Zscaler Private Access documentation (help.zscaler.com/zpa).
- NIST SP 800-207, Zero Trust Architecture.
- Zscaler deployment guides (help.zscaler.com) — connector sizing and placement.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
