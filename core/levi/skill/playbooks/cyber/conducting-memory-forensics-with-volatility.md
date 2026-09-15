---
skill_id: cyber_conducting_memory_forensics_with_volatility
name: Conducting Memory Forensics with Volatility
description: Practitioner guide to analyzing memory images with the Volatility framework, from profile identification to malware artifact extraction.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, memory, analysis]
version: 1.0.0
---
## Purpose
Memory holds what disk does not: running malware, injected code, encryption keys, and network connections at capture time. This playbook structures Volatility-based memory analysis -- identifying the right profile, enumerating processes and artifacts, detecting injection and rootkits, and extracting indicators for the investigation.

## When to use
- Analyzing memory images captured during incident response.
- Investigating suspected fileless malware or process injection.
- Extracting credentials, keys, or C2 configuration from memory.
- Corroborating disk-forensics findings with runtime state.

## Prerequisites
- Memory image acquired forensically with verified hashes.
- Volatility installed with profiles or symbol support matching the target OS.
- Case context: what the investigation is trying to answer.
- Sufficient compute for large images.

## Procedure
1. Verify and identify. Confirm the image hash, then determine the OS profile (imageinfo or automatic profile detection) before running any plugins.
2. Establish the baseline. List processes, and note the system time, uptime, and any obvious anomalies in the process tree.
3. Enumerate key artifacts. Examine network connections, loaded DLLs, handles, services, and scheduled artifacts as captured in memory.
4. Hunt for injection and hiding. Compare process listings across plugins to find hidden or unlinked processes; examine memory regions for injected code.
5. Check persistence and credentials. Review autostart locations reflected in memory and look for credential material only where the case requires it.
6. Extract indicators. Pull file paths, hashes of dumped suspicious regions, C2 addresses, and mutexes for the IOC package.
7. Correlate with other evidence. Match memory findings against disk timelines, logs, and network captures to build the full picture.
8. Document the analysis. Record Volatility version, profile, plugins run, and findings with offsets and PIDs for reproducibility.

## Expected outputs
- Memory analysis report with findings tied to PIDs and artifacts.
- Extracted IOCs (processes, network indicators, injected code hashes).
- Documented methodology for reproducibility.

## Pitfalls
- Wrong profile selection produces garbage output; verify OS identification first.
- Analyzing the live system instead of an image risks contamination and misses the point.
- Plugin output without case context becomes an unfocused data dump.
- Memory images age instantly; capture as close to the incident as possible.

## References
- Volatility Framework documentation
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR508 memory-forensics methodology concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
