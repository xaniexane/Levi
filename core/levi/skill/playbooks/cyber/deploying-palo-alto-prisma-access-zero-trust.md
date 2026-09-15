---
skill_id: cyber_deploying_palo_alto_prisma_access_zero_trust
name: Deploying Palo Alto Prisma Access Zero Trust
description: Deploy Prisma Access with ZTNA policies, posture checks, and inspection for consistent zero-trust remote access.
risk: low
permissions: []
requires_confirmation: false
tags: [ztna, network, firewall]
version: 1.0.0
---
## Purpose

Deploy Palo Alto Prisma Access as the zero-trust remote-access plane: GlobalProtect agents with ZTNA 2.0 application policies, device posture enforcement, and full traffic inspection — one consistent policy for users wherever they are, replacing legacy VPN network access.

## When to use

- Migrating from VPN concentrators to a SASE-delivered zero-trust model.
- Standardizing remote-access security policy across regions and cloud environments.
- Enforcing consistent inspection (threat prevention, URL filtering, DLP) on remote traffic.
- Auditing an existing Prisma Access deployment for policy gaps.

## Prerequisites

- Prisma Access tenant with mobile-user and/or remote-network onboarding completed.
- IdP integrated for SAML authentication and an MDM/EDR inventory for posture signals.
- Application inventory: which private apps, SaaS apps, and internet categories each user group needs.
- Pilot user group and a phased migration plan away from legacy VPN.

## Procedure

1. **Onboard with the right service connections.** Establish service connections from Prisma Access to each data center and cloud VPC hosting private apps, with redundant connections per location. Verify routing and failover before any user traffic depends on them — a single service connection is a single point of failure.
2. **Deploy GlobalProtect with pre-logon and HIP.** Roll out the GlobalProtect agent with pre-logon (for domain-joined machines) and Host Information Profile (HIP) checks: OS patch level, disk encryption, EDR presence, firewall status. HIP data drives every access decision — keep the checks current with your actual standards.
3. **Build ZTNA application policies, not network policies.** Define applications (not subnets) and write policies on user/group + application + HIP posture. Default-deny; each allow names the app, the group, and the minimum posture. Avoid "allow all private apps" rules — that's VPN semantics wearing a ZTNA costume.
4. **Enable the full security processing stack.** Turn on threat prevention (vulnerability, anti-spyware, antivirus profiles), URL filtering, DNS security, and file blocking on the Prisma Access gateways. Remote users get the same inspection as on-prem users — that's the SASE promise; verify it's actually enabled, not just licensed.
5. **Add DLP and SaaS controls for data protection.** Enable DLP profiles on sensitive data patterns for upload/download paths and SaaS security policies for sanctioned/unsanctioned apps. Alert on DLP blocks involving sensitive data types and review them as potential insider or compromise signals.
6. **Log everything to Cortex Data Lake / SIEM.** Forward GlobalProtect, traffic, threat, and HIP logs. Alert on: HIP failures spiking (possible posture evasion), policy denies for privileged apps, new device enrollments, and threat-prevention blocks on remote-user traffic.
7. **Migrate and decommission legacy VPN.** Move users in waves, monitoring Prisma Access adoption versus legacy VPN usage. Shrink VPN access as waves complete, then decommission the concentrators. A parallel VPN undermines every zero-trust claim — track its usage to zero.
8. **Audit policies and posture quarterly.** Review application definitions for scope creep, access policies for stale memberships, HIP check definitions against current OS/EDR versions, and security profiles against the latest threat-prevention content updates.

## Expected outputs

- Redundant service connections with GlobalProtect + HIP posture enforcement fleet-wide.
- ZTNA application policies (user + app + posture) with full inspection stack enabled.
- Centralized logging with bypass and posture-evasion alerting; legacy VPN decommissioned.

## Pitfalls

- Subnet-wide application definitions — recreates VPN flat access inside Prisma.
- HIP checks defined once and never updated — posture decisions based on stale OS/EDR versions.
- Licensing the security stack but not enabling the profiles on the gateways.
- Single service connection per site — outages during maintenance windows.
- Leaving legacy VPN up "for exceptions" — exceptions become the standard path.

## References

- Palo Alto Networks Prisma Access deployment and administration documentation
- NIST SP 800-207 (Zero Trust Architecture)
- CISA Zero Trust Maturity Model
- MITRE ATT&CK T1133 (External Remote Services)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
