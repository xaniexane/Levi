---
skill_id: cyber_b3_business_email_compromise_identity_provider_sso_colocation_facility_managed
name: Business Email Compromise Defense for SSO Identity Providers in Colocation Facilities (Managed Maturity)
description: "Business Email Compromise defense playbook for SSO Identity Providers in Colocation Facilities at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, fraud, identity, sso, authentication, on-prem, colocation, maturity-managed]
version: 1.0.0
---
# Business Email Compromise Defense for SSO Identity Providers in Colocation Facilities (Managed Maturity)

## Purpose

Attackers operate inside a compromised mailbox (or a lookalike domain) to redirect payments, harvest invoices, or pivot to executives. Dwell time is often weeks; the fraud, not the malware, is the payload. Applies to SSO Identity Providers in Colocation Facilities at Managed maturity.

## When to use

- Mailbox audit logs show inbox rules created to move or delete messages containing 'invoice', 'payment', 'wire', or executive names — the classic BEC rule footprint.
- Outbound messages to finance vendors from a slightly altered domain, or a legitimate mailbox suddenly sending payment-change requests with urgent tone.
- Logons to the mailbox from foreign IPs or anonymizing VPNs followed by long read-only sessions (the attacker learning the payment workflow before striking).
- Lens: Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Authentication logs per application (success/failure, MFA method, device, location) and Application assignment and provisioning logs; new SSO integrations; run `# conceptually (IdP APIs differ):` then `idp-cli logs auth --user <upn> --last 7d --format table | head -25`.
3. **Analyze.** Export all inbox/transport rules for the affected mailbox and diff against a known-good baseline; BEC rules often hide with names like ';' or whitespace. Then: Trace every payment instruction the mailbox sent in the dwell window: which were acted on, which bank details changed, and whether funds are recallable.
4. **Contain and harden.** Require out-of-band (voice/video) verification for any payment detail change, no exceptions, and alert on new inbox rules fleet-wide. Asset layer: Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Focusing only on the compromised mailbox while the attacker already harvested the vendor's thread and will re-target from another account.
- Treating a lookalike-domain BEC as an IT problem alone — finance process change is the actual fix.

## References

- MITRE ATT&CK: T1566 (Initial Access: Phishing) leading to collection/fraud
- Vendor logging and hardening baselines for SSO Identity Providers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
