---
skill_id: cyber_b3_dcsync_attack_active_directory_dc_air_gapped_network_foundational
name: DCSync Attack Defense for Active Directory Domain Controllers in Air-Gapped Networks (Foundational Maturity)
description: "DCSync Attack defense playbook for Active Directory Domain Controllers in Air-Gapped Networks at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, windows, air-gap, ot, high-security, maturity-foundational]
version: 1.0.0
---
# DCSync Attack Defense for Active Directory Domain Controllers in Air-Gapped Networks (Foundational Maturity)

## Purpose

With replication rights, an attacker impersonates a domain controller and pulls password hashes for ANY account — including krbtgt — via normal replication traffic. It looks like DC-to-DC chatter, which is why it evades naive monitoring. Applies to Active Directory Domain Controllers in Air-Gapped Networks at Foundational maturity.

## When to use

- 4662 (directory object access) on the domain root or krbtgt account by a principal that is not a real domain controller.
- Replication traffic (DRS) originating from a non-DC host, or a DC requesting replication far outside the normal schedule.
- Newly granted DS-Replication-Get-Changes rights (especially Get-Changes-All) to users, groups, or computers.
- Lens: Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log Kerberos events (4768 TGT requests, 4769 service tickets, 4771 pre-auth failures) and Directory-service change events (5136/5137) and replication metadata (repadmin /showobjmeta); run `repadmin /showrepl | Select-String -Pattern 'error|fail' -Context 2` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4769} -MaxEvents 200 | Group-Object {$_.Properties[0].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Identify which account performed the sync and which hashes were pulled — a krbtgt pull means the entire domain's Kerberos trust must be reset (double krbtgt rotation). Then: Review how the attacker gained replication rights: compromised admin, delegated rights sprawl, or ACL abuse.
4. **Contain and harden.** Audit and strip replication rights to the minimum; alert on any grant of Get-Changes-All. Asset layer: Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting user passwords but not the krbtgt — golden tickets forged from a stolen krbtgt survive password resets.
- Missing that DCSync needs only replication rights, not Domain Admin — delegated-rights sprawl is the usual enabler.

## References

- MITRE ATT&CK: T1003.006 (Credential Access: DCSync)
- Vendor logging and hardening baselines for Active Directory Domain Controllers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
