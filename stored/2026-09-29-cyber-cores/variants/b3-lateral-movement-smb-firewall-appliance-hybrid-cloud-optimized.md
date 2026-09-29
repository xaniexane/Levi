---
skill_id: cyber_b3_lateral_movement_smb_firewall_appliance_hybrid_cloud_optimized
name: SMB Lateral Movement Defense for Firewall Appliances in Hybrid Cloud (Optimized Maturity)
description: "SMB Lateral Movement defense playbook for Firewall Appliances in Hybrid Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, network, firewall, hybrid, cloud, on-prem, maturity-optimized]
version: 1.0.0
---
# SMB Lateral Movement Defense for Firewall Appliances in Hybrid Cloud (Optimized Maturity)

## Purpose

Attackers move host-to-host over SMB using stolen credentials — PsExec-style service creation, admin shares, or WMI. In a flat network, one compromised workstation becomes the whole domain in hours. Applies to Firewall Appliances in Hybrid Cloud at Optimized maturity.

## When to use

- SMB sessions from a workstation to many other hosts in a short window, especially to ADMIN$ or C$ shares the user never touches normally.
- Service creation events (7045) with service binaries in ADMIN$\system32, or 4624 type-3 logons with the same account across dozens of hosts.
- EDR process trees showing services.exe spawning cmd/powershell shortly after a remote SMB session.
- Lens: Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log and Configuration revisions and diffs; VPN session logs and authentication failures; run `# vendor CLIs differ; conceptually:` then `show log traffic query (source <suspect-ip>)             # Palo Alto style`.
3. **Analyze.** Map the movement graph: source host, credential used, target hosts, timestamps — this is the incident's skeleton. Then: Determine which credential enabled it (stolen hash, ticket, or plaintext) to know what must be rotated enterprise-wide.
4. **Contain and harden.** Segment the network (workstation-to-workstation SMB blocked), deploy LAPS for unique local admin passwords, and restrict lateral logon rights via tiered admin model. Asset layer: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning patient zero while the attacker's beachheads on hosts 3, 7, and 12 remain active.
- Rotating the compromised account's password but not the kerberos tickets/hashes already stolen from it.

## References

- MITRE ATT&CK: T1021.002 (Lateral Movement: SMB/Windows Admin Shares)
- Vendor logging and hardening baselines for Firewall Appliances; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
