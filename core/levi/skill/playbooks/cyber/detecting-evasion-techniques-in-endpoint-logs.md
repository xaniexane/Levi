---
skill_id: cyber_detecting_evasion_techniques_in_endpoint_logs
name: Detecting Evasion Techniques in Endpoint Logs
description: Detect defense-evasion behaviors — log tampering, AMSI/ETW interference, and timestomping — in endpoint telemetry.
risk: info
permissions: []
requires_confirmation: false
tags: [endpoint, detection, evasion]
version: 1.0.0
---
## Purpose

Catch attackers trying to blind your defenses: clearing logs, disabling security tools, tampering with AMSI/ETW, timestomping artifacts, and unloading EDR drivers. Evasion detection is meta-detection — you're watching the watchers, and an attacker fighting your telemetry is confirming they're there.

## When to use

- Building defense-evasion detection for the SOC (ATT&CK TA0005 coverage).
- Hunting for sophisticated intruders who evade primary detections.
- Investigating gaps in telemetry (missing logs are themselves evidence).
- Validating tamper-protection on EDR and logging agents.

## Prerequisites

- Endpoint telemetry: EDR, Sysmon, Windows Security/ PowerShell logs, centralized and tamper-evident.
- Baseline of legitimate administrative actions that resemble evasion (admin tools that touch security services).
- Tamper protection enabled on EDR and logging agents.
- Alerting path with high severity — evasion attempts are inherently suspicious.

## Procedure

1. **Detect log tampering.** Alert on: Event ID 1102 (audit log cleared) and 104 (log cleared) on any host, unexpected gaps in log sequences (sequence numbers jumping), logging services stopped outside change windows, and SIEM forwarder agents disabled or uninstalled. A host that suddenly goes quiet during an incident is tampering until proven otherwise.
2. **Detect security-tool disabling.** Alert on: EDR/AV services stopped or drivers unloaded, tamper-protection disable attempts, Windows Defender exclusions added (especially broad ones), firewall rules disabled or deleted, and Sysmon configuration changes or uninstallation. Baseline legitimate admin tooling that touches these (your RMM, patch management) and alert on everything else.
3. **Detect AMSI and ETW interference.** Alert on: AMSI provider registry modifications, `amsi.dll` tampering or unhooking indicators, ETW provider disables, and PowerShell logging (module/script-block) being turned off. These are the specific blinds attackers put on PowerShell visibility — their tampering is often more detectable than the payloads they hide.
4. **Detect timestomping and artifact manipulation.** Alert on: `SetFileTime` API usage and MACE timestamp anomalies (creation time after modification time, timestamps in the future), USN journal tampering indicators, and Event Log record-level deletions (not just full clears — selective deletion via tools). Timestomping shows forensic awareness — treat the host as a sophisticated intrusion.
5. **Detect process and indicator hiding.** Alert on: rootkit-like behaviors (hidden processes via DKOM indicators, unlinked process lists), direct syscalls bypassing user-mode hooks (syscall stubs in unusual processes), and EDR-unhooking patterns (memory patches in `ntdll.dll`). These are advanced techniques — any detection here is a high-severity incident.
6. **Correlate evasion with the underlying activity.** Evasion is never the goal — it's cover for something. When evasion is detected, hunt backward and forward: what happened on the host in the hour before the logs were cleared? What network connections occurred? The evasion alert defines the investigation window; the surrounding telemetry defines the incident.
7. **Harden the telemetry itself.** Implement: tamper protection on all security agents, WEF/SIEM forwarding with no local-only logs, protected event logging (Windows 11/Server 2025 crypto-protected logs where available), restricted access to log-clearing privileges, and monitoring of the monitoring (alert when any agent stops reporting). Your telemetry must survive the attacker.

## Expected outputs

- Detections for log tampering, tool disabling, AMSI/ETW interference, timestomping, and process hiding.
- Evasion-correlated investigation procedures (the evasion defines the window; surrounding telemetry defines the incident).
- Hardened, tamper-resistant telemetry with monitoring-of-monitoring.

## Pitfalls

- No baseline for legitimate admin tooling — your own RMM triggers evasion alerts daily.
- Treating the evasion as the incident — it's the cover; find what it was covering.
- Local-only logs — cleared logs with no forwarded copy are gone forever.
- Ignoring telemetry gaps — a silent host is the loudest evasion signal.
- Disabling detections because "admins do this too" — scope the exception to the specific admin tool, not the technique.

## References

- MITRE ATT&CK TA0005 (Defense Evasion) — full technique coverage mapping
- Microsoft Learn — Windows event logging, AMSI, and protected event logging
- Sysmon documentation — configuration for evasion-relevant events
- NIST SP 800-92 (Guide to Computer Security Log Management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
