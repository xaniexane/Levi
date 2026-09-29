---
skill_id: cyber_b3_asreproasting_dns_server_azure_cloud_foundational
name: ASREPRoasting Defense for DNS Servers in Azure Cloud (Foundational Maturity)
description: "ASREPRoasting defense playbook for DNS Servers in Azure Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, network, dns, cloud, azure, maturity-foundational]
version: 1.0.0
---
# ASREPRoasting Defense for DNS Servers in Azure Cloud (Foundational Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to DNS Servers in Azure Cloud at Foundational maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: query logs (or passive DNS) + zone-transfer/change audit + resolver cache stats. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in DNS query logs showing tunneling/DGA patterns; zone files and their change history and Zone-transfer (AXFR) request logs; DNSSEC validation failure logs; run `grep -E '.{60,}' /var/log/named/query.log | tail -20   # long labels: tunneling/DGA` then `rndc status; echo ---; journalctl -u named --since '1 hour ago' | grep -iE 'transfer|denied|error' | tail -15`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Restrict recursion to internal clients, block outbound port 53 except resolvers, DNSSEC validation on. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for DNS Servers; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
