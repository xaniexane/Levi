---
skill_id: cyber_hunting_for_lateral_movement_via_wmi
name: Hunting for Lateral Movement via WMI
description: Detect WMI-based lateral movement: anomalous wmic/process-call-create usage, DCOM-RPC patterns, and resulting process chains.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, lateral-movement, windows]
version: 1.0.0
---
## Purpose

Windows Management Instrumentation (WMI) is a built-in remote-
administration framework that attackers abuse for lateral movement:
executing processes on remote hosts via `wmic` or scripted DCOM calls
without dropping tools. This playbook covers detecting WMI-based movement
in endpoint and network telemetry.

## When to use

- Investigating lateral movement where the vector is unclear.
- Hunting after intel reports WMI use in ransomware or APT playbooks.
- Validating Sysmon/EDR coverage of WMI process-creation events.
- Sweeping for additional compromised hosts after one WMI-moved host
  is found.

## Prerequisites

- Sysmon (event 1 process creation with command lines, event 3 network)
  or EDR with WMI visibility; Windows Security logs (4688, 4624).
- WMI operational logs
  (Microsoft-Windows-WMI-Activity/Operational) where collected.
- Baseline of legitimate WMI usage: SCCM/MEM, monitoring agents, and
  admin scripts that use WMI remotely.

## Procedure

1. **Know the execution patterns.** WMI lateral movement typically
   appears as: `wmic /node:<target> process call create "<cmd>"`,
   PowerShell `Invoke-WmiMethod Win32_Process Create`, or scripted
   DCOM calls — followed by a child process on the target whose parent
   chain traces to WMIPrvSE.exe.
2. **Hunt wmic and scripted invocation.** Query process-creation logs
   for `wmic.exe` with `/node` targeting remote hosts, and for
   PowerShell/script hosts invoking WMI process-creation methods with
   remote computer names. Flag interactive users running these outside
   admin tooling.
3. **Hunt the target-side artifacts.** On potential targets, look for
   processes parented to `WmiPrvSE.exe` with suspicious command lines
   (script interpreters, encoded PowerShell, LOLBins), correlated with
   type-3 network logons from the source host moments before.
4. **Correlate network DCOM/RPC.** WMI remote calls traverse DCE/RPC
   (TCP 135 + dynamic ports). Correlate source→target RPC connections
   with the process-creation events to build the lateral edge, and
   check firewall logs for workstation-to-workstation 135 traffic —
   rarely legitimate.
5. **Baseline legitimate WMI.** Management platforms and monitoring
   generate heavy WMI traffic — allow-list by source host (management
   servers), WMI namespace, and resulting process. Alert on WMI
   execution originating from workstations or user contexts.
6. **Check for WMI persistence pairings.** Attackers who move via WMI
   often persist via WMI event subscriptions — when you find WMI
   movement, also hunt for new event consumers/filters on the affected
   hosts.
7. **Scope and contain.** Reconstruct the full movement graph (every
   source→target edge), isolate affected hosts, reset credentials used
   in the movement, and review data accessed from each reached host.
8. **Constrain WMI structurally.** Firewall DCE/RPC between
   workstations, restrict remote WMI permissions to management hosts
   via GPO, and deploy durable detections for the hunted patterns.

## Expected outputs

- WMI lateral-movement edges: source→target with process, logon, and
  network evidence.
- Full movement graphs per intrusion with scoping notes.
- Containment and credential-reset records.
- WMI permission and firewall hardening changes.
- Durable detections for anomalous WMI execution.

## Pitfalls

- Legitimate management WMI is voluminous — baselining by source and
  namespace is non-negotiable.
- WMI-Activity operational logs are verbose and often not collected —
   verify collection before relying on them; process-creation data is
   the more reliable primary source.
- Attackers can invoke WMI without `wmic.exe` (COM scripting) —
   target-side parent-chain analysis catches what source-side
   command-line hunting misses.
- Workstation-to-workstation RPC is the key network signal — ensure
   firewall logging covers it.
- Remediation that only reimages targets misses the source foothold —
   always trace movement back to patient zero.

## References

- MITRE ATT&CK: T1047 (Windows Management Instrumentation)
- Microsoft Learn: WMI architecture and remote-WMI security
  documentation
- Sysmon documentation (process-creation and parent-chain analysis)
- NIST SP 800-92: log management (WMI operational logs)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
