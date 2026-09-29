---
skill_id: cyber_b3_ad_acl_abuse_linux_server_hybrid_cloud_defined
name: Active Directory ACL Abuse Defense for Linux Servers in Hybrid Cloud (Defined Maturity)
description: "Active Directory ACL Abuse defense playbook for Linux Servers in Hybrid Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, linux, server, hybrid, cloud, on-prem, maturity-defined]
version: 1.0.0
---
# Active Directory ACL Abuse Defense for Linux Servers in Hybrid Cloud (Defined Maturity)

## Purpose

Attackers abuse delegated Active Directory permissions — WriteDacl, GenericAll, ForceChangePassword — to escalate without exploits. These are legitimate rights granted too broadly, so detection means auditing WHO can do WHAT, continuously. Applies to Linux Servers in Hybrid Cloud at Defined maturity.

## When to use

- 4662 events showing writes to security descriptors (WriteDacl / WriteOwner) on privileged groups, OUs, or the AdminSDHolder container.
- Password resets (4724) performed by non-helpdesk accounts, or new ACEs granting GenericAll over high-value targets.
- BloodHound-style LDAP enumeration (large object reads) preceding the ACL change — the attacker mapping attack paths.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** Diff the object's ACL before and after: which principal gained which right, and was it granted through nested group membership? Then: Map the attack path the new right enables (e.g., GenericAll on a group -> add self -> Domain Admin) to scope the blast radius.
4. **Contain and harden.** Least-privilege delegation: no GenericAll/WriteDacl outside Domain Admins; regular ACL audits with alerting on changes to protected objects. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- One-time ACL cleanup without continuous monitoring — delegation sprawl regrows within months.
- Forgetting nested groups: the dangerous ACE is often three group-nestings away from the attacker.

## References

- MITRE ATT&CK: T1098 (Persistence: Account Manipulation)
- Vendor logging and hardening baselines for Linux Servers; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
