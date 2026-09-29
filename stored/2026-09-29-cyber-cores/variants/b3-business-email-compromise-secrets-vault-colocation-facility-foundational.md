---
skill_id: cyber_b3_business_email_compromise_secrets_vault_colocation_facility_foundational
name: Business Email Compromise Defense for Secrets Vaults in Colocation Facilities (Foundational Maturity)
description: "Business Email Compromise defense playbook for Secrets Vaults in Colocation Facilities at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, fraud, secrets, identity, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Business Email Compromise Defense for Secrets Vaults in Colocation Facilities (Foundational Maturity)

## Purpose

Attackers operate inside a compromised mailbox (or a lookalike domain) to redirect payments, harvest invoices, or pivot to executives. Dwell time is often weeks; the fraud, not the malware, is the payload. Applies to Secrets Vaults in Colocation Facilities at Foundational maturity.

## When to use

- Mailbox audit logs show inbox rules created to move or delete messages containing 'invoice', 'payment', 'wire', or executive names — the classic BEC rule footprint.
- Outbound messages to finance vendors from a slightly altered domain, or a legitimate mailbox suddenly sending payment-change requests with urgent tone.
- Logons to the mailbox from foreign IPs or anonymizing VPNs followed by long read-only sessions (the attacker learning the payment workflow before striking).
- Lens: Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Audit log of secret reads/writes/deletes with client identity and source IP and Policy and auth-method changes; root-token generation events; run `vault audit log --since 24h 2>/dev/null | grep -E '"path":"secret' | head -20` then `vault list sys/policy 2>/dev/null; vault auth list 2>/dev/null`.
3. **Analyze.** Export all inbox/transport rules for the affected mailbox and diff against a known-good baseline; BEC rules often hide with names like ';' or whitespace. Then: Trace every payment instruction the mailbox sent in the dwell window: which were acted on, which bank details changed, and whether funds are recallable.
4. **Contain and harden.** Require out-of-band (voice/video) verification for any payment detail change, no exceptions, and alert on new inbox rules fleet-wide. Asset layer: Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Focusing only on the compromised mailbox while the attacker already harvested the vendor's thread and will re-target from another account.
- Treating a lookalike-domain BEC as an IT problem alone — finance process change is the actual fix.

## References

- MITRE ATT&CK: T1566 (Initial Access: Phishing) leading to collection/fraud
- Vendor logging and hardening baselines for Secrets Vaults; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
