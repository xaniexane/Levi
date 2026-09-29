---
skill_id: cyber_b3_lateral_movement_rdp_linux_workstation_colocation_facility_foundational
name: RDP Lateral Movement Defense for Linux Workstations in Colocation Facilities (Foundational Maturity)
description: "RDP Lateral Movement defense playbook for Linux Workstations in Colocation Facilities at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, linux, endpoint, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# RDP Lateral Movement Defense for Linux Workstations in Colocation Facilities (Foundational Maturity)

## Purpose

RDP is both an admin tool and the attacker's favorite lateral highway. Compromised credentials plus unrestricted RDP equals domain-wide movement that looks almost legitimate in the logs. Applies to Linux Workstations in Colocation Facilities at Foundational maturity.

## When to use

- 4624 type-10 (RDP) logons from a workstation to servers or other workstations outside the user's normal admin pattern.
- RDP sessions at unusual hours, from hosts the account never logged into before, or with clipboard/drive redirection moving tools onto the target.
- TerminalServices-LocalSessionManager events (21/25) on targets without a matching helpdesk ticket or change record.
- Lens: Best telemetry: auditd user-session logging + EDR agent + desktop shell histories (with user notice). Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in User shell histories (~/.bash_history), desktop autostart entries (~/.config/autostart/) and auditd execve logs and USB device logs; browser profiles for web-vector cases; run `ls -la ~/.config/autostart/ 2>/dev/null; grep -r 'Exec=' ~/.config/autostart/ 2>/dev/null` then `sudo ausearch --start recent -m EXECVE -i | tail -30`.
3. **Analyze.** Correlate RDP logons with the source host's compromise timeline to distinguish attacker sessions from legitimate admin work. Then: Check for credential harvesting on each RDP target: LSASS access or SAM reads following the session indicate theft.
4. **Contain and harden.** RDP restricted to jump hosts/bastions with MFA; Network Level Authentication enforced; no direct workstation-to-server RDP. Asset layer: Standard user accounts for daily work, full-disk encryption, and screen-lock enforcement. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Allowing 'temporary' RDP exceptions that become permanent lateral paths.
- Missing RDP-based movement because you only hunted SMB — attackers use whatever is open.

## References

- MITRE ATT&CK: T1021.001 (Lateral Movement: Remote Desktop Protocol)
- Vendor logging and hardening baselines for Linux Workstations; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
