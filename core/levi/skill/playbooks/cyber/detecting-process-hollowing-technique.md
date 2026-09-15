---
skill_id: cyber_detecting_process_hollowing_technique
name: Detecting Process Hollowing Technique
description: Detect process hollowing — malicious code running inside a hollowed legitimate process.
risk: low
permissions: []
requires_confirmation: false
tags: [process-injection, malware, detection]
version: 1.0.0
---
## Purpose

Process hollowing replaces a legitimate process's memory image with malicious code, so the malicious activity appears under a trusted process name. This playbook focuses on the memory and behavioral artifacts that expose hollowing: mismatched image paths, unbacked executable memory, and the API call sequences hollowers can't avoid.

## When to use

- EDR or threat intel indicates hollowing-capable malware in your environment.
- You need injection-detection coverage that survives process-name spoofing.
- Malware analysis: confirming whether a sample uses hollowing.
- Validating EDR memory-protection rules with purple-team tests.

## Prerequisites

- Endpoint telemetry with memory visibility: Sysmon (Event IDs 1, 8, 10) or EDR with memory-scan capability.
- Ability to capture process memory or run memory forensics (Volatility) on suspect hosts.
- Baseline of legitimate processes that use similar techniques (some packers, .NET NGEN, security products).
- YARA or memory-scanning capability for payload identification.

## Procedure

1. Know the hollowing sequence. Classic hollowing: create a legitimate process suspended (CreateProcess with CREATE_SUSPENDED), unmap/hollow its memory (NtUnmapViewOfSection), allocate and write malicious code (VirtualAllocEx/WriteProcessMemory), set the entry point (SetThreadContext), resume. Each step is individually legitimate; the sequence plus the target being a trusted system binary is the detection.
2. Detect via image-path and memory anomalies. Alert on: processes whose in-memory image doesn't match their on-disk image (PEB image path vs. loaded modules), executable memory regions not backed by any file (unbacked RWX/private executable memory) in system processes, and hollowed-process indicators like mismatched entry points. Memory scanners and EDRs with hollow-detection catch these regardless of the payload.
3. Use Sysmon/EDR event patterns. Correlate: process creation with suspicious parentage → CreateRemoteThread (Event ID 8) or process-access (Event ID 10) targeting a freshly created suspended process → network connections from the hollowed process. Also watch for the unmap-then-write sequence via API monitoring where available. Single events are weak; the chain is strong.
4. Confirm with memory forensics. For suspect processes: capture memory, use Volatility (malfind, hollowshim, ldrmodules) to identify injected/hollowed regions, extract the payload for analysis, and determine the payload's capability (C2, credential theft, ransomware). Memory confirmation turns a behavioral alert into a scoped incident.
5. Scope and remediate as code-execution compromise. Hollowing means arbitrary code ran as the hollowed process's user: isolate the host, determine the initial access vector (how the hollower arrived), hunt fleet-wide for the same parent/child patterns and payload hashes, and reset credentials for accounts active on the host.
6. Harden against the technique class: application control to block the initial hollower, EDR memory-protection features enabled, patch the exploited initial-access vectors, and remove local admin rights that let hollowers target SYSTEM processes.

## Expected outputs

- Hollowing detection rules: memory-anomaly (unbacked executable), event-chain (suspend→inject→resume), parent/child patterns.
- Memory-forensics procedure: capture, Volatility analysis, payload extraction.
- Fleet-hunting queries for hollowing indicators and payload IOCs.
- EDR memory-protection coverage assessment.

## Pitfalls

- Some legitimate software (packers, DRM, .NET) produces hollow-like memory artifacts — baseline before alerting.
- Event-only detection without memory confirmation produces false positives; pair behavioral rules with memory validation.
- Attackers use hollowing variants (transacted, phantom DLL) — memory-anomaly detection outlasts sequence-specific rules.
- Analyzing the hollowed process without capturing the payload's C2 misses the campaign — always extract and analyze.
- Relying on process-name allowlists is exactly what hollowing defeats — never trust the name.

## References

- MITRE ATT&CK T1055.012 (Process Injection: Process Hollowing) — https://attack.mitre.org/techniques/T1055/012/; Volatility documentation: malfind and related plugins; Microsoft Learn: Sysmon event reference
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
