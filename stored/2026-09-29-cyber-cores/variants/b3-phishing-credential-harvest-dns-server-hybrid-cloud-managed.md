---
skill_id: cyber_b3_phishing_credential_harvest_dns_server_hybrid_cloud_managed
name: Phishing Credential Harvest Defense for DNS Servers in Hybrid Cloud (Managed Maturity)
description: "Phishing Credential Harvest defense playbook for DNS Servers in Hybrid Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, phishing, network, dns, hybrid, cloud, on-prem, maturity-managed]
version: 1.0.0
---
# Phishing Credential Harvest Defense for DNS Servers in Hybrid Cloud (Managed Maturity)

## Purpose

Users are lured to lookalike login pages (often via adversary-in-the-middle kits that relay MFA) and submit credentials. The defender's job: find who clicked, who submitted, and whether sessions were hijacked even where MFA appeared to hold. Applies to DNS Servers in Hybrid Cloud at Managed maturity.

## When to use

- Email gateway logs show a burst of messages with lookalike domains, newly registered domains, or QR-code lures pointing at a credential-harvest kit URL.
- Proxy/DNS logs show visits to the kit domain followed within minutes by logons from unusual IPs or impossible-travel pairs for the same user.
- AiTM kits leave telltales: logon session created without a matching MFA challenge event, or token replay from datacenter IP ranges.
- Lens: Best telemetry: query logs (or passive DNS) + zone-transfer/change audit + resolver cache stats. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in DNS query logs showing tunneling/DGA patterns; zone files and their change history and Zone-transfer (AXFR) request logs; DNSSEC validation failure logs; run `grep -E '.{60,}' /var/log/named/query.log | tail -20   # long labels: tunneling/DGA` then `rndc status; echo ---; journalctl -u named --since '1 hour ago' | grep -iE 'transfer|denied|error' | tail -15`.
3. **Analyze.** Pull the kit URL from the email, fetch it in a sandbox, and extract the credential-post endpoint and any session-cookie exfiltration to scope which submissions completed. Then: For each submitter, check for concurrent sessions: revoke all refresh tokens and list OAuth app consents granted in the phish window.
4. **Contain and harden.** Move to phishing-resistant MFA (FIDO2/WebAuthn); TOTP and push MFA fall to AiTM relay. Asset layer: Restrict recursion to internal clients, block outbound port 53 except resolvers, DNSSEC validation on. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without revoking sessions leaves the attacker logged in via stolen tokens.
- Blaming the clicker instead of fixing the control gap guarantees a repeat with a better lure.

## References

- MITRE ATT&CK: T1566.002 (Initial Access: Phishing: Spearphishing Link)
- Vendor logging and hardening baselines for DNS Servers; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
