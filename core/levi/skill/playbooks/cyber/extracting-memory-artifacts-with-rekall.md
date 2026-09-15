---
skill_id: cyber_extracting_memory_artifacts_with_rekall
name: Extracting Memory Artifacts with Rekall
description: Analyze acquired memory images with the Rekall framework (and its Volatility successors), extracting processes, network state, and injected code.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, memory, analysis]
version: 1.0.0
---
## Purpose

Memory forensics reveals what disk forensics cannot: running processes,
open network connections, injected code, and in-memory-only malware. This
playbook covers analyzing an acquired memory image with Rekall-style
workflows — noting that Rekall itself is discontinued and its techniques
now live on in Volatility 3 and similar frameworks — to extract the core
artifact classes every investigation needs.

## When to use

- You hold a memory image from an incident and need processes, network
  connections, and code-injection evidence.
- Triaging suspected fileless malware or in-memory implants.
- Validating EDR findings about process behavior with an independent
  forensic source.
- Training analysts on memory-forensics fundamentals.

## Prerequisites

- A forensically acquired memory image with verified hashes and
  documented chain of custody.
- A memory-analysis framework installed (Volatility 3 recommended for
  current work; Rekall workflows apply where the tool is still
  available) with correct OS profiles/symbols for the image.
- An analysis workstation with enough RAM to process the image and
  encrypted storage for outputs.
- Baseline knowledge of the expected process set for the OS version in
  the image.

## Procedure

1. **Identify the image.** Determine the OS, version, and architecture
   from the image (imageinfo-style identification) and load the matching
   profile/symbols. A wrong profile silently produces misleading output
   — verify with a known-good artifact (e.g. the kernel process list).
2. **Enumerate processes.** List active processes from multiple sources
   (active list, CSRSS handles, thread scans) and diff them — processes
   visible to scanners but absent from the OS list indicate DKOM-style
   hiding. Record PIDs, PPIDs, start times, and command lines.
3. **Map the process tree.** Reconstruct parent-child relationships and
   flag anomalies: processes with orphaned or spoofed parents (e.g.
   explorer.exe spawned by an unusual parent), unexpected children of
   system processes, and processes running from temp or user-writable
   paths.
4. **Extract network state.** Recover open sockets, listening ports, and
   recent connections with owning PIDs. Correlate against firewall/proxy
   logs — in-memory C2 often shows here even when logs were cleared.
5. **Hunt injected code.** Scan for memory regions that are executable
   but not backed by a disk image (private RWX), mismatched PE headers
   in process memory (hollowing), and suspicious loaded DLLs (unsigned,
   unusual paths, or injected into system processes).
6. **Examine persistence-adjacent artifacts.** Check loaded drivers and
   kernel modules for unsigned or unexpected entries, and review handles
   and registry hives resident in memory for tampering indicators.
7. **Timeline the findings.** Anchor process start times, connection
   timestamps, and injection events into the incident timeline alongside
   disk and log evidence to sequence the attacker's actions.
8. **Document tool and profile versions.** Record the framework version,
   profile/symbols used, and plugin parameters so the analysis is
   reproducible — memory-forensics results must be defensible.

## Expected outputs

- A process inventory with hidden-process analysis and tree anomalies.
- Network state: connections, listeners, and owning processes.
- Injected-code findings: RWX regions, hollowed processes, suspect
  DLLs.
- A memory-derived timeline integrated with the incident timeline.
- Reproducibility notes (tool, profile, plugin versions).

## Pitfalls

- Rekall is unmaintained: prefer Volatility 3 (or current equivalents)
  for new work; keep Rekall only for legacy image compatibility.
- Profile mismatches are the top source of false findings — always
  validate the profile against known artifacts first.
- Memory is a point-in-time snapshot: terminated processes and closed
  connections may be partially recoverable but are often incomplete —
  pair with logs.
- Timestamps in memory can reflect clock manipulation; corroborate with
  external sources.
- Large images on underpowered workstations lead to truncated or
  crashed analysis — size the workstation to the image.

## References

- Volatility 3 documentation (framework and plugin references)
- NIST SP 800-86: Guide to Integrating Forensic Techniques into
  Incident Response
- MITRE ATT&CK: T1055 (Process Injection), T1014 (Rootkit)
- SANS/community memory-forensics poster and cheat-sheet material
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
