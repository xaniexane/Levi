---
skill_id: cyber_performing_timeline_reconstruction_with_plaso
name: Timeline Reconstruction with Plaso
description: Build super-timelines with Plaso (log2timeline) to reconstruct incident sequences from diverse evidence sources.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, timeline, plaso]
version: 1.0.0
---

## Purpose
- Combine file system, registry, log, and browser artifacts into a single chronological timeline.
- Answer the critical incident questions: when did it start, what happened in what order, what is still missing.
- Give investigators and stakeholders one authoritative event sequence.

## When to use
- During forensic investigations when the event sequence is unclear.
- When correlating evidence from multiple systems into a single incident narrative.
- When preparing expert reports that require precise chronology.
- When validating or challenging timelines from other tools.

## Prerequisites
- Forensic images or collected artifacts with hashes recorded.
- Plaso installed with sufficient storage; timelines for large images need tens of gigabytes.
- Time-zone documentation for every evidence source.
- Investigative questions the timeline must answer.

## Procedure
1. Verify evidence hashes and document the sources going into the timeline.
2. Run log2timeline against the image or artifact set, selecting parsers relevant to the case.
3. Store the output in a Plaso storage file; keep the raw collection for reprocessing.
4. Use psort to filter by date range, focusing on the incident window plus buffer periods.
5. Normalize time zones: confirm each source's zone and convert to a common reference.
6. Identify key events: initial access, persistence, lateral movement, and exfiltration markers.
7. Correlate timeline events with network, memory, and log evidence.
8. Flag clock anomalies: skewed timestamps, future dates, and anti-forensic timestomping.
9. Build the narrative: a concise event sequence with supporting timeline entries cited.
10. Export filtered timelines for the case file and for sharing with stakeholders.
11. Document parser versions and commands so the timeline can be reproduced.
12. Archive the storage file with the case evidence.

## Expected outputs
- A super-timeline covering the incident window with normalized timestamps.
- A narrative event sequence with cited timeline entries.
- Reproducible processing documentation.
- A timeline template with the standard event categories for the team.
- Peer review of the narrative by a second analyst before reporting.

## Pitfalls
- Mixing time zones without normalizing; the timeline will lie convincingly.
- Including every parser on huge images; processing time explodes, so scope parsers to the case.
- Treating timeline entries as facts; each entry needs interpretation against the evidence.
- Presenting tool output as the conclusion; the timeline supports analysis, it is not the analysis.

## References
- Plaso GitHub project documentation for parser details
- Plaso documentation
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR508 timeline analysis methodology
- log2timeline parser documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
