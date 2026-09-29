---
skill_id: cyber_b3_oauth_consent_phishing_ot_controller_branch_office_defined
name: OAuth Consent Phishing Defense for OT Controllers in Branch Offices (Defined Maturity)
description: "OAuth Consent Phishing defense playbook for OT Controllers in Branch Offices at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, ot, ics, critical-infrastructure, branch, network, maturity-defined]
version: 1.0.0
---
# OAuth Consent Phishing Defense for OT Controllers in Branch Offices (Defined Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to OT Controllers in Branch Offices at Defined maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for OT Controllers; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
