---
skill_id: cyber_performing_lateral_movement_with_wmiexec
name: WMIexec-Style Lateral Movement Defense
description: Detect WMI-based remote execution and harden Windows management plane.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, windows, hardening]
version: 1.0.0
---
# WMIexec-Style Lateral Movement Defense

## Purpose

WMI-based remote execution (the technique behind tools like WMIexec)
lets an attacker with credentials run commands on remote Windows hosts
without dropping files — via WMI process creation or DCOM. This
playbook is defensive: recognizing the telemetry signature, detecting
it in your environment, and hardening WMI/DCOM so the technique loses
its value.

## When to use

- Building detections for fileless lateral movement on Windows.
- Hunting for WMI abuse during an incident.
- Hardening the Windows management plane (WMI, DCOM, WinRM).
- Validating EDR coverage against living-off-the-land techniques.

## Prerequisites

- Sysmon or EDR process-creation telemetry with parent-child
  relationships and command lines, plus Windows Security logs (4688,
  4624) centralized in the SIEM.
- WMI operational logs (Microsoft-Windows-WMI-Activity/Operational)
  forwarded from critical servers.
- Authority to adjust DCOM/WMI permissions and firewall rules on the
  management plane.

## Procedure

1. Learn the signature: WMI remote execution appears as
   `wmiprvse.exe` spawning `cmd.exe` or `powershell.exe` on the
   target, preceded by a DCOM network logon (4624 type 3) from the
   source host on port 135 with dynamic RPC ports.
2. Baseline legitimate WMI: inventory which management tools and
   service accounts use WMI remotely (SCCM, monitoring agents) so
   detection can exclude them precisely.
3. Build the detection: alert on `wmiprvse.exe` with command-line
   children outside the allowlisted management tools, especially
   `cmd.exe /Q /c` patterns or base64 PowerShell.
4. Correlate the logon: join the WMI event with the preceding 4624
   type-3 logon from an unusual source — user workstations initiating
   DCOM to servers is rarely legitimate.
5. Harden DCOM/WMI: restrict remote WMI and DCOM activation to
   dedicated admin accounts via `dcomcnfg` launch permissions and
   WMI namespace security; deny it for standard users entirely.
6. Segment the management plane: firewall RPC/WMI ports so only jump
   hosts and management servers can initiate them; block
   workstation-to-server DCOM.
7. Reduce credential exposure: Credential Guard, LSA protection, and
   tiered admin accounts so a compromised workstation does not yield
   credentials usable for WMI movement.
8. Validate with simulation: run controlled WMI remote-execution tests
   from a lab host and confirm the detection fires end to end.

## Expected outputs

- Detection rules for WMI-based remote execution with allowlisted
  management tools.
- Hardened DCOM/WMI permissions and firewall segmentation.
- Credential-theft mitigations (Credential Guard, tiering) in place.
- Validated alerting from purple-team simulation.

## Pitfalls

- Name-based detection only: attackers rename or use alternate WMI
   consumers — parent-child and protocol patterns are more durable.
- Allowlisting too broadly: "all SCCM servers" without scoping which
   accounts may use WMI from them.
- Blocking WMI outright without understanding monitoring
   dependencies: you will break the tools that watch the network.
- Forgetting DCOM hardening while fixing WMI: the techniques share
   the same underlying access.

## References

- MITRE ATT&CK: Windows Management Instrumentation (T1047)
- Microsoft Learn: WMI security and DCOM hardening documentation
- NIST SP 800-53, System and Communications Protection (SC-7)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
