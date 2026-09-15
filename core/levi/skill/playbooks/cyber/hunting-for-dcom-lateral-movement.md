---
skill_id: cyber_hunting_for_dcom_lateral_movement
name: Hunting for DCOM Lateral Movement
description: Detect lateral movement via DCOM: anomalous MMC20.Application, ShellBrowserWindow, and Office-DCOM instantiation in endpoint logs.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, lateral-movement, windows]
version: 1.0.0
---
## Purpose

Distributed Component Object Model (DCOM) lets attackers execute code on
remote Windows hosts without dropping binaries — instantiating objects
like `MMC20.Application` remotely to run commands. This playbook covers
detecting DCOM-based lateral movement in endpoint telemetry and
constraining DCOM exposure.

## When to use

- Investigating suspected lateral movement where no new binaries or
  services appeared on the target.
- Threat hunting after intel reports DCOM use by ransomware affiliates
  or APT groups.
- Validating EDR/Sysmon coverage of DCOM instantiation events.
- Post-incident: sweeping for additional DCOM-moved hosts.

## Prerequisites

- Sysmon with DCOM-relevant events (process creation with command
  lines, network connections) and/or EDR with equivalent visibility.
- Windows Security logs from targets (4688 process creation, 4624
  network logons).
- DCOM operational logs where enabled
  (Microsoft-Windows-DistributedCOM).
- Baseline of legitimate DCOM usage: management tools, software
  deployment, and monitoring agents that use DCOM legitimately.

## Procedure

1. **Know the abused objects.** The commonly abused DCOM application
   IDs include MMC20.Application (MMC20), ShellBrowserWindow/ShellWindows
   (explorer automation), and Office applications (Word/Excel DDE-style
   execution). Document the CLSIDs/AppIDs relevant to your hunt.
2. **Hunt remote instantiation.** Query for processes spawned via DCOM
   on remote hosts: child processes of `dllhost.exe`/`mmc.exe` with
   unusual command lines, `explorer.exe` spawned non-interactively on
   servers, and Office applications launching with automation flags
   from network logon sessions.
3. **Correlate with network logons.** DCOM lateral movement arrives over
   DCE/RPC (TCP 135 plus ephemeral ports). Correlate suspicious process
   creation on the target with type-3 network logons from the source
   host in the seconds before — the source→target pair is your lateral
   edge.
4. **Examine command lines.** DCOM execution often carries telltale
   command lines: script interpreters, encoded PowerShell, or LOLBin
   invocations as children of DCOM-launched processes. Capture and
   decode them.
5. **Baseline legitimate DCOM.** Management and deployment tools use
   DCOM routinely — build allow-lists by source host, AppID, and
   launched process. Alert on DCOM instantiation from non-management
   hosts and on AppIDs outside the legitimate set.
6. **Scope the movement.** From each confirmed DCOM edge, pivot: what
   ran on the target, what credentials were used, and where the
   attacker went next. DCOM is often one hop in a longer chain —
   reconstruct the full path.
7. **Contain and remediate.** Isolate affected hosts, revoke or reset
   credentials used in the movement, and review what the attacker
   accessed from each DCOM-reached host.
8. **Constrain DCOM structurally.** Limit DCOM launch/activation
   permissions via Group Policy to management hosts, firewall DCE/RPC
   so workstations cannot DCOM into each other, and add durable
   detections for the hunted patterns.

## Expected outputs

- DCOM lateral-movement findings: source→target edges with process
  and logon evidence.
- Full movement chains reconstructed per intrusion.
- Containment and credential-reset records.
- DCOM permission and firewall hardening changes.
- Durable detections for anomalous DCOM instantiation.

## Pitfalls

- Legitimate management tooling is DCOM-heavy — without baselining,
   the hunt produces overwhelming false positives.
- DCOM over the network needs 135 plus dynamic RPC ports — firewall
   logs alone may miss the full picture; endpoint correlation is key.
- Office-DCOM abuse requires Office installed on the target — server
   estates without Office are not exposed to that vector; scope the
   hunt to real exposure.
- Attackers can use less-common AppIDs — periodically review for
   DCOM instantiation outside your known-abused list.
- Disabling DCOM broadly breaks management — constrain by permissions
   and network, not by killing the service.

## References

- MITRE ATT&CK: T1021.003 (Distributed Component Object Model)
- Microsoft Learn: DCOM security and activation-permission
  documentation
- Sysmon documentation (process-creation and network events)
- Industry research on DCOM lateral-movement techniques (defensive
  summaries)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
