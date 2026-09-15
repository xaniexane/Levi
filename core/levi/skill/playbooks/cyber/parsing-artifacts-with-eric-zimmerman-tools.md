---
skill_id: cyber_parsing_artifacts_with_eric_zimmerman_tools
name: Parsing Artifacts with Eric Zimmerman's Tools
description: Parse Windows forensic artifacts at scale using EZ Tools for timeline analysis.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows, artifacts]
version: 1.0.0
---
## Purpose
This playbook standardizes Windows artifact parsing with Eric Zimmerman's free toolset (MFTECmd, JLECmd, RLA, AppCompatCacheParser, AmcacheParser, EvtxECmd, SQLECmd, etc.): extracting structured timelines from forensic images or live triage collections for investigation and incident response.

## When to use
- Analyzing a Windows disk image or triage package during an investigation.
- Building a super-timeline of user and system activity around an incident window.
- You need fast, reliable parsing of ESE databases, registry hives, and event logs.

## Prerequisites
- Forensic image or collected artifacts (MFT, registry hives, event logs, prefetch, jumplists) with chain of custody.
- EZ Tools installed on an analysis workstation (Windows or Linux via the .NET builds).
- Case time window and key questions defined before parsing begins.

## Procedure
1. **Stage the evidence.** Mount the image read-only or work from exported artifact files; record hashes of everything you parse.
2. **Parse the file system.** Run MFTECmd against $MFT to get full file timelines; filter to the incident window and look for timestomping anomalies and recently-created executables.
3. **Parse execution artifacts.** Run AppCompatCacheParser (ShimCache), AmcacheParser, and prefetch parsers to establish what executed and when — including deleted binaries.
4. **Parse user activity.** Run JLECmd (jumplist/LNK), RLA (recycle bin), and browser history parsers (via EvtxECmd/SQLECmd where applicable) to reconstruct user actions.
5. **Parse event logs.** Run EvtxECmd across Security, System, and PowerShell logs; correlate logons, service installs, and script blocks with the file timeline.
6. **Build the super-timeline.** Merge outputs into a single chronological view; anchor on known-good events (user logon) and known-bad events (malware execution) to validate the timeline.
7. **Document and preserve.** Save parser versions, command lines, and outputs with the case; timelines are evidence and must be reproducible.

8. **Automate the routine.** Script the standard parser sequence so triage collections get a baseline timeline within minutes of ingestion, freeing analysts for interpretation.
9. **Keep tools current.** Update EZ Tools regularly; artifact formats change with Windows updates and stale parsers silently miss data.

## Expected outputs
- Parsed artifact datasets with hashes and parser provenance.
- Super-timeline covering the incident window with anchored key events.
- Findings report linking artifacts to investigative conclusions.
- Example: MFTECmd shows a malicious executable created at 02:14, ShimCache confirms execution at 02:15, and Security.evtx shows the resulting service installation at 02:16 — a complete execution chain from three artifacts.

## Pitfalls
- Parsing without a time window: drowning in millions of rows of normal activity.
- Mixing parser versions across a case, making results hard to reproduce.
- Trusting timestamps blindly: check for timestomping and clock anomalies.

- Parsing a live system's artifacts in place and altering access times; always work from images or exported copies for evidential integrity.
- Cherry-picking artifacts that support the initial theory; parse broadly first, then narrow — the timeline should be able to surprise you.

## References
- Eric Zimmerman's tool documentation (ericzimmerman.github.io).
- SANS FOR500 Windows Forensics concepts (sans.org) for artifact interpretation.
- "Windows Forensic Analysis Toolkit" methodology references (Syngress) — artifact correlation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
