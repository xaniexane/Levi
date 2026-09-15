---
skill_id: cyber_deploying_cloudflare_access_for_zero_trust
name: Deploying Cloudflare Access for Zero Trust
description: Put private applications behind Cloudflare Access with identity, device, and context-aware policies.
risk: low
permissions: []
requires_confirmation: false
tags: [ztna, identity, network]
version: 1.0.0
---
## Purpose

Replace VPN and publicly exposed admin panels with Cloudflare Access: every request to internal applications is authenticated, device-checked, and policy-evaluated at the edge before it reaches the origin. Least-privilege access without network-level trust.

## When to use

- Removing internal tools (Jenkins, Grafana, admin consoles) from the public internet.
- Giving remote and contractor users access to private apps without VPN.
- Enforcing device posture and step-up authentication for sensitive applications.
- Auditing an existing Access deployment for policy gaps.

## Prerequisites

- A Cloudflare Zero Trust account with an IdP integrated (Entra ID, Okta, Google Workspace) for SSO.
- DNS control for the protected hostnames and an origin that can be reached via Cloudflare Tunnel (cloudflared) or private network routing.
- Inventory of applications, their users/groups, and sensitivity levels.
- A pilot user group and a rollback plan (keep the old access path briefly during cutover).

## Procedure

1. **Connect origins without exposing them.** Deploy `cloudflared` tunnels from each private network or use Cloudflare's private-network routing so applications are reachable only through Cloudflare. Firewall the origins to accept traffic solely from Cloudflare IP ranges — an app still reachable directly has two front doors, and attackers use the unlocked one.
2. **Create one Access application per service.** Define each application with its exact hostname and session settings. Avoid wildcard applications covering unrelated services — policy granularity is the point of zero trust.
3. **Write layered Allow policies.** Start with identity (specific IdP groups, never "all authenticated users" for sensitive apps), then add device posture signals via WARP client checks (managed device, OS version, disk encryption, EDR running), and context signals (country, IP reputation, authentication method). Deny rules for high-risk contexts (impossible travel, anonymized IPs) go above the allows.
4. **Require step-up authentication for sensitive apps.** Enforce MFA at every Access session for admin tools, and consider short session durations (hours, not days) with re-authentication. For the most sensitive apps, require phishing-resistant MFA (FIDO2/WebAuthn) at the IdP level.
5. **Protect non-HTTP applications.** Use Access with SSH/RDP short-lived certificates or browser-rendered SSH so infrastructure access also passes through identity and policy — not just web apps. Log every session.
6. **Enable logging and alerting.** Forward Access audit logs (login events, policy decisions) to the SIEM. Alert on: denied access spikes, logins from new devices for privileged users, policy changes to Access applications, and any direct-to-origin traffic observed at the origin firewall (bypass attempts).
7. **Migrate users and decommission old paths.** Move users group by group, monitoring Access logs for adoption. Shrink and then remove the old VPN profiles and public exposures. Verify from an external network that the old paths are truly dead — DNS, direct IP, and alternate hostnames included.
8. **Review policies quarterly.** Audit application inventory (remove decommissioned apps), policy membership (stale groups), and posture rules (are the OS minimums still current?). Test a sample of applications from an unmanaged device to confirm posture enforcement actually blocks.

## Expected outputs

- Origins reachable only via Cloudflare with per-application Access policies (identity + device + context).
- Step-up MFA on sensitive apps; SSH/RDP also behind Access with session logging.
- SIEM-forwarded audit logs with bypass-attempt alerting; quarterly policy reviews.

## Pitfalls

- Leaving the origin publicly reachable "during migration" permanently — the second front door.
- "All authenticated users" Allow policies on sensitive apps — identity alone is not zero trust.
- No device posture checks — stolen credentials from any device then grant access.
- Wildcard applications with one loose policy covering everything from wikis to production consoles.
- Forgetting non-HTTP paths — attackers don't limit themselves to the apps you remembered to protect.

## References

- Cloudflare Zero Trust documentation — Access policies, Tunnel, device posture
- NIST SP 800-207 (Zero Trust Architecture)
- CISA Zero Trust Maturity Model
- MITRE ATT&CK T1133 (External Remote Services) and T1078 (Valid Accounts)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
