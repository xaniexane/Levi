---
skill_id: cyber_configuring_windows_event_logging_for_detection
name: Configuring Windows Event Logging for Detection
description: Build a Windows audit policy and centralized log pipeline that gives the SOC the events it needs without drowning it.
risk: low
permissions: []
requires_confirmation: false
tags: [windows, logging, detection]
version: 1.0.0
---
## Purpose

Configure Windows auditing so the events that matter — logons, process creation with command lines, privilege use, and object access — are reliably generated, forwarded, and retained. Most post-incident "we couldn't see it" moments trace back to audit policy that was never configured.

## When to use

- Standing up detection on a Windows fleet (workstations and servers) for the first time.
- Remediating an incident where key events were missing because process-creation logging was off.
- Preparing for compliance (PCI DSS log requirements, CIS benchmarks, internal audit).
- Deploying Windows Event Forwarding (WEF) or a SIEM agent for centralized collection.

## Prerequisites

- Domain admin or GPO management rights; endpoints running Windows 10/11 or Server 2016+.
- A log collector (WEF collector, SIEM agent) sized for the event volume, with retention policy defined.
- A baseline event-volume measurement on a pilot group before fleet-wide rollout.
- Change window: audit-policy changes can briefly increase disk and network load.

## Procedure

1. **Set the audit policy baseline via GPO (Advanced Audit Policy).** Enable success and failure for: Logon/Logoff (4624, 4625, 4634, 4648, 4672), Account Logon (4768, 4769, 4771, 4776), Process Tracking — process creation (4688) with command-line logging enabled via policy, Privilege Use (4673), and Policy Change (4719, 4739). Disable noisy categories you can't action (e.g. detailed tracking of every handle operation).
2. **Enable command-line logging in process creation.** In the same GPO, turn on "Include command line in process creation events." Without this, 4688 tells you `powershell.exe` ran — useless for detection. Accept the credential-exposure caveat: review logs for passwords in command lines and remediate the scripts that put them there.
3. **Enable PowerShell and Sysmon-level telemetry.** Turn on PowerShell module logging and script-block logging (Event ID 4104) — the single richest source for fileless attack detection. Deploy Sysmon with a curated config (SwiftOnSecurity or a tailored variant) for process parent-child, network connections, driver loads, and registry events that native auditing misses.
4. **Configure Windows Event Forwarding (WEF).** Stand up a collector, create subscriptions by event source (Security, Sysmon/Operational, PowerShell), and push the subscription GPO to endpoints. Use source-initiated subscriptions with HTTPS transport and mutual authentication; verify with a test event from a pilot machine before fleet rollout.
5. **Size log retention on endpoints and collectors.** Set Security log size to at least 1 GB on servers (more on DCs) with "archive when full, do not overwrite" for critical systems. On the collector/SIEM, enforce the retention policy (90 days online minimum is a common baseline) and alert on forwarding gaps — a silent forwarder is a blind spot.
6. **Protect the logs themselves.** Restrict access to the Security log to administrators and the collector service account; alert on Event ID 1102 (audit log cleared) and 104 (log cleared) as high-priority incidents. Consider making the collector append-only where the SIEM supports it.
7. **Build the canonical detection views.** Pre-build SIEM searches for: 4625 bursts (password spraying), 4672/4769 anomalies (privilege escalation, Kerberos anomalies), 4688 with suspicious parents (Office spawning powershell), 4104 script blocks with obfuscation markers, and Sysmon network events from unexpected processes. Map each to a triage runbook.
8. **Audit the audit policy quarterly.** Attackers and admins both change audit settings. Monitor 4719 (system audit policy changed) and compare effective policy against the GPO baseline; any drift is a finding, and on a DC it's an incident until proven otherwise.

## Expected outputs

- A documented GPO-based audit baseline with command-line and script-block logging enabled.
- WEF subscriptions delivering Security/Sysmon/PowerShell events to the SIEM with monitored forwarding health.
- Pre-built detection searches and alert rules; quarterly audit-policy drift checks.

## Pitfalls

- Enabling process creation logging without command lines — you get volume with no value.
- Collecting everything: handle-manipulation and file-system auditing at full volume will bury the SOC and fill disks; audit what's actionable.
- Letting logs overwrite on full — evidence destruction by configuration.
- Script-block logging volume surprises: measure on the pilot group and size the pipeline first.
- Forgetting that 1102 (log cleared) needs its own alert — it's often the first sign of an active intrusion.

## References

- Microsoft Learn — Advanced security auditing policy settings
- Sysmon documentation and the SwiftOnSecurity sysmon-config baseline
- NIST SP 800-92 (Guide to Computer Security Log Management)
- MITRE ATT&CK T1070 (Indicator Removal) — log-clearing detection context
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
