---
skill_id: cyber_b3_ad_acl_abuse_macos_endpoint_gcp_cloud_optimized
name: Active Directory ACL Abuse Defense for macOS Endpoints in GCP Cloud (Optimized Maturity)
description: "Active Directory ACL Abuse defense playbook for macOS Endpoints in GCP Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, macos, endpoint, cloud, gcp, maturity-optimized]
version: 1.0.0
---
# Active Directory ACL Abuse Defense for macOS Endpoints in GCP Cloud (Optimized Maturity)

## Purpose

Attackers abuse delegated Active Directory permissions — WriteDacl, GenericAll, ForceChangePassword — to escalate without exploits. These are legitimate rights granted too broadly, so detection means auditing WHO can do WHAT, continuously. Applies to macOS Endpoints in GCP Cloud at Optimized maturity.

## When to use

- 4662 events showing writes to security descriptors (WriteDacl / WriteOwner) on privileged groups, OUs, or the AdminSDHolder container.
- Password resets (4724) performed by non-helpdesk accounts, or new ACEs granting GenericAll over high-value targets.
- BloodHound-style LDAP enumeration (large object reads) preceding the ACL change — the attacker mapping attack paths.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Diff the object's ACL before and after: which principal gained which right, and was it granted through nested group membership? Then: Map the attack path the new right enables (e.g., GenericAll on a group -> add self -> Domain Admin) to scope the blast radius.
4. **Contain and harden.** Least-privilege delegation: no GenericAll/WriteDacl outside Domain Admins; regular ACL audits with alerting on changes to protected objects. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- One-time ACL cleanup without continuous monitoring — delegation sprawl regrows within months.
- Forgetting nested groups: the dangerous ACE is often three group-nestings away from the attacker.

## References

- MITRE ATT&CK: T1098 (Persistence: Account Manipulation)
- Vendor logging and hardening baselines for macOS Endpoints; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
