---
skill_id: cyber_detecting_fileless_attacks_on_endpoints
name: Detecting Fileless Attacks on Endpoints
description: Detect fileless attacks on endpoints with memory, script, and behavioral telemetry — no disk artifacts required.
risk: info
permissions: []
requires_confirmation: false
tags: [endpoint, detection, fileless]
version: 1.0.0
---
## Purpose

Detect attacks that never touch disk — PowerShell, WMI, and living-off-the-land binaries executing malicious logic purely in memory. Fileless attacks defeat file-scanning AV by design; detection must come from behavior, script telemetry, and memory analysis.

## When to use

- Building endpoint detection for fileless and living-off-the-land techniques.
- Hunting after an incident where disk forensics found nothing.
- Tuning EDR behavioral detections and PowerShell logging.
- Validating that script-block logging and AMSI are actually catching malicious scripts.

## Prerequisites

- EDR with behavioral detection on all endpoints; PowerShell script-block and module logging enabled.
- Sysmon with process-creation (command-line), image-load, and WMI-event monitoring.
- AMSI enabled and untampered; Windows Event Forwarding or SIEM collection of 4104/4688.
- Baseline of legitimate PowerShell/WMI usage (admins and automation use these too).

## Procedure

1. **Enable the script-visibility stack.** Turn on PowerShell script-block logging (4104), module logging, and transcription for high-risk hosts. Verify AMSI is active and its logs reach the SIEM. Without script content, fileless attacks are invisible — the command line alone (`powershell -enc <blob>`) tells you something happened but not what.
2. **Detect obfuscated and encoded execution.** Alert on: `-EncodedCommand` / `-enc` with large payloads, `IEX`/`Invoke-Expression` on decoded strings, `DownloadString`/`Invoke-WebRequest` piped to invocation, and AMSI-bypass patterns. Baseline legitimate encoded usage (some admin tools use it) and alert on deviations in size, parent process, and network follow-on.
3. **Monitor living-off-the-land binaries (LOLBins).** Alert on LOLBins used abnormally: `mshta`, `rundll32`, `regsvr32`, `certutil`, `bitsadmin`, `wmic` with suspicious arguments or unexpected parents (Office spawning `rundll32` is never normal). Maintain a LOLBin list mapped to your environment's legitimate use — the parent-child relationship is the detection, not the binary name alone.
4. **Detect WMI-based persistence and execution.** Alert on: `wmic` process creation with encoded commands, WMI event-subscription creation (`__EventFilter`/`CommandLineEventConsumer` — the classic fileless persistence), and WMI used for lateral movement. WMI persistence survives reboots with no disk artifact — monitor the WMI repository for new subscriptions.
5. **Correlate with memory and network signals.** Fileless attacks still do things: alert on the combination of script execution + network connection to rare destinations, script execution + credential access (LSASS), and script execution + persistence creation. Single signals are noisy; the behavior chain is the detection.
6. **Hunt with memory forensics on suspicion.** When behavioral signals indicate fileless activity, capture memory and analyze: injected code sections, hollowed processes, reflective DLLs, and malicious script content in process memory. Memory is the disk for fileless malware — Volatility or EDR memory analysis recovers what disk forensics cannot.
7. **Constrain the execution environment.** Harden with: Constrained Language Mode for PowerShell where feasible, AMSI + script-block logging enforced by policy (tampering = alert), AppLocker/WDAC limiting which binaries can execute scripts, and disabling unused LOLBins and WMI where business allows. Prevention shrinks the fileless attack surface permanently.

## Expected outputs

- Full script-visibility stack (4104, module logging, AMSI) with obfuscation and LOLBin detections.
- WMI persistence monitoring and behavior-chain correlation (script + network + credential access).
- Memory-forensics procedures and execution-environment hardening (CLM, AppLocker/WDAC).

## Pitfalls

- Script-block logging without collection — the events exist locally and nobody sees them.
- Alerting on LOLBin names alone — legitimate use is common; parent-child-context is the detection.
- Missing WMI event subscriptions — the persistence mechanism with no disk footprint.
- Treating `-EncodedCommand` as automatically malicious — baseline legitimate admin use first.
- No memory capability — when behavioral signals fire, you need memory to confirm.

## References

- MITRE ATT&CK T1059 (Command and Scripting Interpreter) and T1546.003 (WMI Event Subscription)
- Microsoft Learn — PowerShell logging, AMSI, Constrained Language Mode
- LOLBAS project (lolbas-project.github.io) — living-off-the-land binary reference
- NIST SP 800-53 SI-7 / CM-7 (software integrity, least functionality)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
