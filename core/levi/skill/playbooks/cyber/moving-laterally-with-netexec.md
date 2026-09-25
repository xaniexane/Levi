---
skill_id: cyber_moving_laterally_with_netexec
name: Detecting Lateral Movement via NetExec (Defensive)
description: Detect and investigate lateral movement conducted with NetExec and similar SMB tooling.
risk: low
permissions: []
requires_confirmation: false
tags: [lateral-movement, detection, active-directory]
version: 1.0.0
---
## Purpose
NetExec (the maintained successor to CrackMapExec) is a dual-use administration and assessment tool frequently abused for SMB-based lateral movement. This is a defensive playbook: recognizing its network and host artifacts, building detections, and hardening against the techniques it enables. It does not teach offensive use.

## When to use
- Hunting for lateral movement in a Windows/AD environment.
- An alert or incident suggests SMB-based movement with credentialed access.
- Validating that EDR and network detections catch common movement tooling.

## Prerequisites
- Centralized Windows security event logs (4624/4625, 4672, 4688/4689) and SMB/network telemetry.
- EDR coverage on servers and workstations with process command-line logging.
- Baseline of legitimate administrative SMB usage (patching, admin tools) to distinguish from abuse.

## Procedure
1. **Know the artifacts.** NetExec-style movement leaves: SMB logons (event 4624 type 3) from unusual sources, rapid sequential logons across many hosts, `ADMIN$`/`C$` share access, remote service creation (7045), and scheduled-task or WMI-based execution.
2. **Build network detections.** Alert on one source authenticating to many destinations over SMB in a short window, especially with local admin or service accounts, and on SMB sessions outside admin jump-host patterns.
3. **Build host detections.** Alert on remote service creation with suspicious binary paths, `schtasks`/`sc.exe` launched remotely, and LSASS-adjacent credential access preceding the movement.
4. **Hunt historically.** Query for the patterns above over 30-90 days during suspected intrusions; movement often precedes ransomware detonation by days.
5. **Correlate with credential hygiene.** Identify which credential was abused (local admin password reuse is the classic enabler) and scope every host it touched.
6. **Contain and eradicate.** Isolate affected hosts, rotate abused credentials enterprise-wide (not just on touched hosts), and remove persistence the movement established.
7. **Harden against recurrence.** Deploy LAPS for local admins, tier admin accounts, block SMB at host firewalls except from admin subnets, and require EDR on every endpoint.

8. **Monitor for tooling presence.** Alert on the appearance of NetExec-like binaries or renamed variants on endpoints; legitimate admin use should be inventoried and expected.
9. **Exercise the playbook.** Include SMB lateral-movement scenarios in tabletop and purple-team exercises so the detections are proven, not theoretical.

## Expected outputs
- SIEM detections for SMB lateral-movement patterns with tuned thresholds.
- Hunt queries for historical movement and credential-abuse scoping.
- Hardening actions: LAPS, tiering, SMB firewall policy.
- Example: a single workstation authenticating via SMB to 40 servers in 10 minutes triggers an alert; investigation shows a compromised local admin credential, driving enterprise-wide rotation and LAPS deployment.

## Pitfalls
- Alerting on every admin SMB session: baseline legitimate tooling first.
- Rotating credentials only on confirmed-compromised hosts while the same password lives elsewhere.
- Missing movement over alternate protocols (WinRM, RDP, WMI) while fixating on SMB.

- Focusing only on SMB while attackers move over WinRM, RDP, or DCOM; build movement detections across all remote-service protocols.
- Assuming EDR blocks all such tooling; test your EDR against renamed and modified variants in a lab, not just the default binary.

## References
- MITRE ATT&CK T1021 (Remote Services) and T1047 (Windows Management Instrumentation).
- Microsoft Learn: mitigating lateral movement guidance (learn.microsoft.com).
- CISA guidance on valid-account abuse and lateral movement (cisa.gov).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
