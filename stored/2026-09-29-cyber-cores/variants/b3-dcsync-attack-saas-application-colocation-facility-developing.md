---
skill_id: cyber_b3_dcsync_attack_saas_application_colocation_facility_developing
name: DCSync Attack Defense for SaaS Applications in Colocation Facilities (Developing Maturity)
description: "DCSync Attack defense playbook for SaaS Applications in Colocation Facilities at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, cloud, saas, on-prem, colocation, maturity-developing]
version: 1.0.0
---
# DCSync Attack Defense for SaaS Applications in Colocation Facilities (Developing Maturity)

## Purpose

With replication rights, an attacker impersonates a domain controller and pulls password hashes for ANY account — including krbtgt — via normal replication traffic. It looks like DC-to-DC chatter, which is why it evades naive monitoring. Applies to SaaS Applications in Colocation Facilities at Developing maturity.

## When to use

- 4662 (directory object access) on the domain root or krbtgt account by a principal that is not a real domain controller.
- Replication traffic (DRS) originating from a non-DC host, or a DC requesting replication far outside the normal schedule.
- Newly granted DS-Replication-Get-Changes rights (especially Get-Changes-All) to users, groups, or computers.
- Lens: Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Admin audit log (settings changes, user provisioning, sharing changes) and User activity logs: file access, downloads, external sharing events; run `# conceptually (SaaS APIs differ):` then `saas-cli audit log --category admin --last 7d --format table | head -25`.
3. **Analyze.** Identify which account performed the sync and which hashes were pulled — a krbtgt pull means the entire domain's Kerberos trust must be reset (double krbtgt rotation). Then: Review how the attacker gained replication rights: compromised admin, delegated rights sprawl, or ACL abuse.
4. **Contain and harden.** Audit and strip replication rights to the minimum; alert on any grant of Get-Changes-All. Asset layer: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting user passwords but not the krbtgt — golden tickets forged from a stolen krbtgt survive password resets.
- Missing that DCSync needs only replication rights, not Domain Admin — delegated-rights sprawl is the usual enabler.

## References

- MITRE ATT&CK: T1003.006 (Credential Access: DCSync)
- Vendor logging and hardening baselines for SaaS Applications; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
