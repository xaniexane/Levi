---
skill_id: cyber_b3_golden_ticket_web_application_branch_office_managed
name: Golden Ticket Attack Defense for Web Applications in Branch Offices (Managed Maturity)
description: "Golden Ticket Attack defense playbook for Web Applications in Branch Offices at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, web, application, branch, network, maturity-managed]
version: 1.0.0
---
# Golden Ticket Attack Defense for Web Applications in Branch Offices (Managed Maturity)

## Purpose

Forged Kerberos TGTs using the stolen krbtgt hash grant unrestricted, long-lived domain access that survives password resets. Detection relies on ticket anomalies: impossible lifetimes, wrong encryption, or logons that bypass the DC. Applies to Web Applications in Branch Offices at Managed maturity.

## When to use

- TGTs with lifetimes far exceeding domain policy (e.g., 10 years), RC4-encrypted tickets in an AES-enforced domain, or tickets for accounts that never authenticated (no 4768).
- 4769 service-ticket requests referencing a TGT the DC never issued, or logons from hosts with no corresponding interactive session.
- The krbtgt account's own anomalous activity following a DCSync event.
- Lens: Best telemetry: app audit logs (with authenticated identity) + WAF logs + structured access logs. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Application audit log: who did what to which object, with session IDs and source IPs and WAF block logs and anomaly scores; web-server access/error logs around the incident; run `grep -E ' 4[0-9]{2} | 5[0-9]{2} ' /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -15` then `journalctl -u myapp --since '2 hours ago' | grep -iE 'error|unauthor|exception' | tail -30`.
3. **Analyze.** Confirm via ticket inspection (klist, network capture): lifetime, encryption type, and client name mismatches prove forgery. Then: Scope everything done under forged tickets — assume full domain compromise until proven otherwise.
4. **Contain and harden.** Rotate the krbtgt password TWICE (to invalidate both current and previous hash) after any suspected compromise. Asset layer: Authorization checks on every object reference, output encoding, parameterized queries, secure session handling. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating krbtgt only once — the N-1 hash remains valid and the golden ticket still works.
- Treating it as an account incident instead of a domain-trust incident; the response scope is the whole forest.

## References

- MITRE ATT&CK: T1558.001 (Credential Access: Golden Ticket)
- Vendor logging and hardening baselines for Web Applications; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
