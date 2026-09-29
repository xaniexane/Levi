---
skill_id: cyber_b3_privilege_escalation_windows_web_application_gcp_cloud_optimized
name: Windows Privilege Escalation Defense for Web Applications in GCP Cloud (Optimized Maturity)
description: "Windows Privilege Escalation defense playbook for Web Applications in GCP Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, web, application, cloud, gcp, maturity-optimized]
version: 1.0.0
---
# Windows Privilege Escalation Defense for Web Applications in GCP Cloud (Optimized Maturity)

## Purpose

From standard user to SYSTEM/Administrator via unquoted service paths, writable service binaries, AlwaysInstallElevated, token manipulation, or kernel exploits. Windows privesc is usually a misconfiguration the attacker read, not a zero-day they brought. Applies to Web Applications in GCP Cloud at Optimized maturity.

## When to use

- Service creation or modification events (7045/4697) pointing at user-writable paths, or processes spawning as SYSTEM from unexpected parents.
- Registry writes to AlwaysInstallElevated keys, accessibility binary replacement (sethc/utilman), or token duplication API patterns in EDR telemetry.
- Enumeration tooling: whoami /priv, accesschk, or PowerShell privesc scripts running before the escalation.
- Lens: Best telemetry: app audit logs (with authenticated identity) + WAF logs + structured access logs. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Application audit log: who did what to which object, with session IDs and source IPs and WAF block logs and anomaly scores; web-server access/error logs around the incident; run `grep -E ' 4[0-9]{2} | 5[0-9]{2} ' /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -15` then `journalctl -u myapp --since '2 hours ago' | grep -iE 'error|unauthor|exception' | tail -30`.
3. **Analyze.** Pin down the primitive: unquoted path, weak service ACL, scheduled task with stored creds, or kernel CVE — then check how many fleet hosts share it. Then: Review what the elevated access touched: SAM/LSASS access after escalation means credential theft followed.
4. **Contain and harden.** Fix service ACLs and paths fleet-wide, disable AlwaysInstallElevated, and enforce signed-driver and LSA protection policies. Asset layer: Authorization checks on every object reference, output encoding, parameterized queries, secure session handling. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reimaging one host while the GPO-deployed misconfiguration recreates the hole on every rebuild.
- Missing that the attacker already dumped credentials post-escalation — scope the follow-on theft, not just the privesc.

## References

- MITRE ATT&CK: T1068 (Privilege Escalation: Exploitation for Privilege Escalation)
- Vendor logging and hardening baselines for Web Applications; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
