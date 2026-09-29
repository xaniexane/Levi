---
skill_id: cyber_b3_asreproasting_api_gateway_remote_workforce_developing
name: ASREPRoasting Defense for API Gateways in Remote Workforce (Developing Maturity)
description: "ASREPRoasting defense playbook for API Gateways in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, web, api, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# ASREPRoasting Defense for API Gateways in Remote Workforce (Developing Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to API Gateways in Remote Workforce at Developing maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for API Gateways; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
