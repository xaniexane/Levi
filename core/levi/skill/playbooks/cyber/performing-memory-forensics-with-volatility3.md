---
skill_id: cyber_performing_memory_forensics_with_volatility3
name: Memory Forensics with Volatility 3
description: Analyze captured RAM images with Volatility 3 to find injected code, hidden processes, and malicious network activity.
risk: low
permissions: []
requires_confirmation: false
tags: [memory, forensics, volatility]
version: 1.0.0
---

## Purpose
- Recover evidence that exists only in volatile memory, such as injected shellcode, decrypted payloads, and active network connections.
- Give analysts a standard Volatility 3 workflow that works across Windows, Linux, and macOS memory images.
- Produce timeline-ready artifacts with process, network, and registry data for incident case files.
- Provide an independent check on endpoint telemetry when EDR data is incomplete or suspect.

## When to use
- When endpoint telemetry suggests fileless malware, process injection, or in-memory credential theft.
- When a disk image shows no malware but the host behaved maliciously while running.
- When validating EDR alerts about suspicious process behavior with independent memory evidence.
- When an incident timeline has gaps that only running-process state can fill.

## Prerequisites
- A verified memory image acquired through an approved process, with acquisition hashes and timestamps recorded.
- Volatility 3 installed with the correct symbol tables for the target operating system version.
- Sufficient disk space and RAM on the analysis workstation; large images benefit from 32 GB or more of memory.
- Context on the suspect host: OS build, running services, and the behaviors that triggered the investigation.

## Procedure
1. Verify the image hash against the acquisition record and confirm the Volatility 3 profile or symbol set matches the OS build.
2. Run a process listing and process tree to establish the running baseline, noting processes with no disk-backed image or unusual parentage.
3. Scan for injected code and unlinked modules using memory-mapping and injection-detection plugins, and dump suspicious regions for string analysis.
4. Review network artifacts from the image: active connections, listening sockets, and recently closed sessions, correlating remote endpoints with threat intel.
5. Examine loaded kernel modules and drivers for unsigned or hidden entries that indicate rootkit activity.
6. Check for credential artifacts in memory, such as LSASS-process anomalies on Windows, and record findings without exporting cleartext secrets into reports.
7. Inspect command history and console buffers recovered from memory for attacker commands typed during the session.
8. Correlate memory findings with disk and log evidence: match process start times to event logs and binary paths to disk hashes.
9. Dump key artifacts (malicious process memory, injected regions) into the case evidence store with hashes.
10. Summarize findings in the case file with plugin outputs, IOCs, and an analyst assessment of confidence.

## Expected outputs
- A memory forensics report with confirmed malicious processes, injected code regions, and network indicators.
- Dumped memory regions and process images preserved as evidence with integrity hashes.
- IOCs (IPs, domains, hashes, mutexes) ready for enterprise-wide hunting.
- Correlated timeline entries linking memory artifacts to log and disk evidence.

## Pitfalls
- Using the wrong symbol table, which produces garbage output that looks plausible; always verify the OS build first.
- Analyzing the only copy of an image on a live system instead of a working copy, risking evidence alteration.
- Treating every injected-looking region as malicious; legitimate security and virtualization tools inject code too.
- Copying cleartext credentials recovered from memory into reports or tickets where they become a new exposure.

## References
- Volatility 3 documentation, https://volatility3.readthedocs.io/
- The Art of Memory Forensics (Wiley) for plugin theory and interpretation
- MITRE ATT&CK defense evasion techniques involving memory, https://attack.mitre.org/tactics/TA0005/
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
