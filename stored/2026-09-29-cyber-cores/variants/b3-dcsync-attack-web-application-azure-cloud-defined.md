---
skill_id: cyber_b3_dcsync_attack_web_application_azure_cloud_defined
name: DCSync Attack Defense for Web Applications in Azure Cloud (Defined Maturity)
description: "DCSync Attack defense playbook for Web Applications in Azure Cloud at Defined maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, web, application, cloud, azure, maturity-defined]
version: 1.0.0
---
# DCSync Attack Defense for Web Applications in Azure Cloud (Defined Maturity)

## Purpose

With replication rights, an attacker impersonates a domain controller and pulls password hashes for ANY account — including krbtgt — via normal replication traffic. It looks like DC-to-DC chatter, which is why it evades naive monitoring. Applies to Web Applications in Azure Cloud at Defined maturity.

## When to use

- 4662 (directory object access) on the domain root or krbtgt account by a principal that is not a real domain controller.
- Replication traffic (DRS) originating from a non-DC host, or a DC requesting replication far outside the normal schedule.
- Newly granted DS-Replication-Get-Changes rights (especially Get-Changes-All) to users, groups, or computers.
- Lens: Best telemetry: app audit logs (with authenticated identity) + WAF logs + structured access logs. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Application audit log: who did what to which object, with session IDs and source IPs and WAF block logs and anomaly scores; web-server access/error logs around the incident; run `grep -E ' 4[0-9]{2} | 5[0-9]{2} ' /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -15` then `journalctl -u myapp --since '2 hours ago' | grep -iE 'error|unauthor|exception' | tail -30`.
3. **Analyze.** Identify which account performed the sync and which hashes were pulled — a krbtgt pull means the entire domain's Kerberos trust must be reset (double krbtgt rotation). Then: Review how the attacker gained replication rights: compromised admin, delegated rights sprawl, or ACL abuse.
4. **Contain and harden.** Audit and strip replication rights to the minimum; alert on any grant of Get-Changes-All. Asset layer: Authorization checks on every object reference, output encoding, parameterized queries, secure session handling. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting user passwords but not the krbtgt — golden tickets forged from a stolen krbtgt survive password resets.
- Missing that DCSync needs only replication rights, not Domain Admin — delegated-rights sprawl is the usual enabler.

## References

- MITRE ATT&CK: T1003.006 (Credential Access: DCSync)
- Vendor logging and hardening baselines for Web Applications; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
