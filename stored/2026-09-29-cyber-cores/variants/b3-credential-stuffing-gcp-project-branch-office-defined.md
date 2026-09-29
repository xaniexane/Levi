---
skill_id: cyber_b3_credential_stuffing_gcp_project_branch_office_defined
name: Credential Stuffing Defense for GCP Projects in Branch Offices (Defined Maturity)
description: "Credential Stuffing defense playbook for GCP Projects in Branch Offices at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, cloud, gcp, branch, network, maturity-defined]
version: 1.0.0
---
# Credential Stuffing Defense for GCP Projects in Branch Offices (Defined Maturity)

## Purpose

Attackers replay username/password pairs stolen from third-party breaches against your login endpoints, betting on password reuse. It shows up as high-volume failed logons from distributed IPs, occasionally followed by a small number of successful takeovers. Applies to GCP Projects in Branch Offices at Defined maturity.

## When to use

- Authentication logs show a spike in failed logons (often 100s per minute) from many source IPs against a single login endpoint, with a low success rate and common password patterns.
- Successful logons immediately followed by password or MFA changes, mailbox rule creation, or impossible-travel alerts for the same account within minutes.
- WAF/bot-management flags distributed requests with identical user-agent strings, headless-browser markers, or known credential-stuffing tool signatures.
- Lens: Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Cloud Audit Logs: setIamPolicy, storage.setIamPermissions, compute inserts, and console logons and Security Command Center findings; Forseti/Config Validator drift reports where deployed; run `gcloud logging read 'protoPayload.methodName:"SetIamPolicy"' --limit 20 --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, resourceName)'` then `gcloud scc findings list organizations/$ORG_ID --filter='state="ACTIVE"' --limit 15`.
3. **Analyze.** Separate spray from stuffing: stuffing reuses many passwords per username from breach corpora; confirm by checking whether the attempted passwords appear in public breach datasets. Then: For each successful post-stuffing logon, inventory session actions: read mail rules, forwarding addresses, OAuth grants, and API keys created in the 24 hours after compromise.
4. **Contain and harden.** Enforce MFA everywhere and block legacy/basic authentication; stuffing dies against phishing-resistant MFA. Asset layer: Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking single IPs is whack-a-mole against botnets; block on behavior (velocity, fingerprint) rather than address.
- Forcing a fleet-wide password reset without confirming which accounts were actually taken over burns goodwill and teaches users to pick weaker passwords.

## References

- MITRE ATT&CK: T1110.004 (Credential Access: Brute Force: Credential Stuffing)
- Vendor logging and hardening baselines for GCP Projects; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
