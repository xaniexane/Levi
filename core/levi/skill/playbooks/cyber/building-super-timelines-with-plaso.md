---
skill_id: cyber_building_super_timelines_with_plaso
name: Building Super Timelines with Plaso
description: Practitioner guide to generating comprehensive forensic super-timelines from disk images and log collections using Plaso.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, timeline, analysis]
version: 1.0.0
---
## Purpose
A super-timeline merges every timestamped artifact -- filesystem metadata, registry keys, event logs, browser history, emails -- into one chronological view. Plaso (the engine behind log2timeline) parses dozens of formats into that unified stream. This playbook covers collecting inputs, running Plaso efficiently, and producing timelines analysts can actually use.

## When to use
- Reconstructing activity on a compromised or suspect system.
- Correlating user actions with system and network events.
- Preparing timeline evidence for investigation reports.
- Feeding timelines into Timesketch or other analysis tools.

## Prerequisites
- Forensic image or logical file collection, acquired with write-blocking and hashing.
- Plaso installed with sufficient CPU, memory, and fast storage for the data volume.
- Understanding of the target OS artifacts relevant to the case.
- Case scope: time window and systems of interest.

## Procedure
1. Verify the evidence. Confirm image hashes match acquisition records before processing; work only on copies.
2. Plan the parsers. Select Plaso parser presets appropriate to the OS and case; full parsing is thorough but slow on large images.
3. Run log2timeline. Process the image or file collection with workers scaled to available CPU; monitor for parser errors on corrupt data.
4. Filter and reduce. Use psort to extract the relevant time window, remove noise (routine system events), and output to CSV or a Timesketch-compatible format.
5. Normalize timezones. Verify timestamps are interpreted correctly; document the timezone assumptions in the case notes.
6. Correlate key events. Identify logons, executions, file modifications, and persistence changes; annotate their significance.
7. Iterate with the investigation. As hypotheses develop, re-filter for new artifact types or time windows rather than re-running full parses.
8. Preserve the outputs. Store the raw plaso storage file and filtered timelines with the case evidence; document the Plaso version and options used.

## Expected outputs
- Super-timeline covering the scoped time window in analyst-usable format.
- Documented processing parameters (Plaso version, parsers, timezone).
- Filtered views supporting the investigation narrative.

## Pitfalls
- Processing multi-terabyte images without scoping wastes days; filter early.
- Timestamp misinterpretation (UTC versus local) silently reorders events.
- Parser errors on damaged files can be mistaken for evidence gaps; check the logs.
- Analysts drowning in millions of events need hypothesis-driven filtering, not more data.

## References
- Plaso (log2timeline) project documentation
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR508 timeline-analysis concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
