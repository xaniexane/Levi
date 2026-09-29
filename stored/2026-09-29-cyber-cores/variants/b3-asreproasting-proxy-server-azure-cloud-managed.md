---
skill_id: cyber_b3_asreproasting_proxy_server_azure_cloud_managed
name: ASREPRoasting Defense for Proxy Servers in Azure Cloud (Managed Maturity)
description: "ASREPRoasting defense playbook for Proxy Servers in Azure Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, network, proxy, web, cloud, azure, maturity-managed]
version: 1.0.0
---
# ASREPRoasting Defense for Proxy Servers in Azure Cloud (Managed Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to Proxy Servers in Azure Cloud at Managed maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for Proxy Servers; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
