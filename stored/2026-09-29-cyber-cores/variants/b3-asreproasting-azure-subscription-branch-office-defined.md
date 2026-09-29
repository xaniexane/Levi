---
skill_id: cyber_b3_asreproasting_azure_subscription_branch_office_defined
name: ASREPRoasting Defense for Azure Subscriptions in Branch Offices (Defined Maturity)
description: "ASREPRoasting defense playbook for Azure Subscriptions in Branch Offices at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, cloud, azure, branch, network, maturity-defined]
version: 1.0.0
---
# ASREPRoasting Defense for Azure Subscriptions in Branch Offices (Defined Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to Azure Subscriptions in Branch Offices at Defined maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Azure Activity Log (write/delete on IAM, policy, network) and Entra audit/sign-in logs and Defender for Cloud recommendations and alerts; resource-change history; run `az monitor activity-log list --max-events 25 --query '[].{time:eventTimestamp, op:operationName.value, caller:caller}' -o table` then `az security alert list --query '[].{name:alertDisplayName, severity:severity, time:timeGeneratedUtc}' -o table`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for Azure Subscriptions; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
