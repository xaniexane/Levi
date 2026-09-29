---
skill_id: cyber_b3_lateral_movement_rdp_email_gateway_remote_workforce_developing
name: RDP Lateral Movement Defense for Email Gateways in Remote Workforce (Developing Maturity)
description: "RDP Lateral Movement defense playbook for Email Gateways in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, email, phishing, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# RDP Lateral Movement Defense for Email Gateways in Remote Workforce (Developing Maturity)

## Purpose

RDP is both an admin tool and the attacker's favorite lateral highway. Compromised credentials plus unrestricted RDP equals domain-wide movement that looks almost legitimate in the logs. Applies to Email Gateways in Remote Workforce at Developing maturity.

## When to use

- 4624 type-10 (RDP) logons from a workstation to servers or other workstations outside the user's normal admin pattern.
- RDP sessions at unusual hours, from hosts the account never logged into before, or with clipboard/drive redirection moving tools onto the target.
- TerminalServices-LocalSessionManager events (21/25) on targets without a matching helpdesk ticket or change record.
- Lens: Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Message tracking (sender, recipients, subject hash, attachments, verdicts) for the campaign window and Sandbox detonation reports for attachments/URLs; quarantined message copies; run `# conceptually (gateway CLIs differ):` then `message-tracking --sender <suspect-domain> --last 7d`.
3. **Analyze.** Correlate RDP logons with the source host's compromise timeline to distinguish attacker sessions from legitimate admin work. Then: Check for credential harvesting on each RDP target: LSASS access or SAM reads following the session indicate theft.
4. **Contain and harden.** RDP restricted to jump hosts/bastions with MFA; Network Level Authentication enforced; no direct workstation-to-server RDP. Asset layer: Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Allowing 'temporary' RDP exceptions that become permanent lateral paths.
- Missing RDP-based movement because you only hunted SMB — attackers use whatever is open.

## References

- MITRE ATT&CK: T1021.001 (Lateral Movement: Remote Desktop Protocol)
- Vendor logging and hardening baselines for Email Gateways; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
