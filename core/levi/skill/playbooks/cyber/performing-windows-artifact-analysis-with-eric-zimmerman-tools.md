---
skill_id: cyber_performing_windows_artifact_analysis_with_eric_zimmerman_tools
name: Windows Artifact Analysis with Eric Zimmerman Tools
description: Parse Windows forensic artifacts with Eric Zimmerman's tool suite and build timelines for investigation.
risk: info
permissions: []
requires_confirmation: false
tags: [forensics, windows, artifacts]
version: 1.0.0
---

## Purpose
Windows systems record a wealth of execution, file, and user-activity evidence. This playbook shows how to analyze those artifacts with Eric Zimmerman's free tool suite (MFTECmd, AmcacheParser, AppCompatCacheParser, JLECmd, LECmd, RBECmd, and Timeline Explorer). Analysis is performed on forensic copies, preserving the original evidence, and results feed timeline reconstruction for incident response.

## When to use
- Post-compromise host investigation or insider-threat review.
- Building a super-timeline from a disk image or triage collection.
- Malware execution tracing: what ran, when, and from where.
- Validating EDR telemetry against on-disk artifacts.

## Prerequisites
- Forensic image or logical collection of the target (never analyze the live original directly).
- Eric Zimmerman's tools installed on an analysis workstation.
- Basic familiarity with NTFS structures, Registry hives, and Windows event logs.
- Case notes template and chain-of-custody documentation.

## Procedure
1. Verify image integrity with hashes before mounting read-only or extracting artifacts.
2. Parse the $MFT with MFTECmd to get file creation, modification, and access timestamps plus resident attributes.
3. Run AmcacheParser and AppCompatCacheParser (Shimcache) to list executed programs with first-execution times.
4. Parse jump lists and LNK files with JLECmd and LECmd for user-opened files and application usage.
5. Parse RecentFileCache, BAM/DAM, and UserAssist data to corroborate execution.
6. Load all CSV outputs into Timeline Explorer, filter by the incident window, and sort chronologically.
7. Correlate artifact timestamps with EDR, firewall, and authentication logs to build the attack narrative.
8. Document each conclusion with the artifact, tool, and timestamp cited so findings are reproducible.
9. Export a hashed file listing of every parsed artifact to prove collection completeness.
10. Normalize all timestamps to UTC and document the source timezone to avoid timeline errors.
11. Cross-check Shimcache/Amcache execution evidence against Prefetch for corroboration.

## Expected outputs
- Parsed artifact CSVs per tool with hashes of source files.
- Consolidated timeline (Timeline Explorer workbook) covering the incident window.
- Written findings linking artifacts to the investigated activity, with citations.
- Hashed manifest of parsed artifacts proving completeness.
- UTC-normalized timeline with timezone documentation.
- Corroboration matrix showing which conclusions rest on multiple artifacts.

## Pitfalls
- Timestamps can be manipulated by timestomping; corroborate across multiple artifact types.
- Shimcache and Amcache have size limits and rotation; absence of an entry is not proof of non-execution.
- Analyzing the live disk alters artifacts; always work from a copy.
- Tool versions change parsers; record the exact version used for reproducibility.
- Timezone confusion across artifacts ruins timelines; normalize early.
- Portable executables run from USB may leave minimal traces; check mount and link artifacts.
- Tool output CSVs are large; filter by the incident window before deep analysis.

## References
- Eric Zimmerman tool documentation (ericzimmerman.github.io).
- SANS FOR500 Windows Forensics course materials (concepts).
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
