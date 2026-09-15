---
skill_id: cyber_building_incident_timeline_with_timesketch
name: Building Incident Timelines with Timesketch
description: Practitioner guide to constructing collaborative forensic timelines with Timesketch for incident reconstruction and analysis.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, incident-response, timeline]
version: 1.0.0
---
## Purpose
Reconstructing what happened during an incident requires merging filesystem, registry, log, and network events into one ordered view. This playbook uses Timesketch -- an open-source collaborative timeline-analysis tool -- to ingest plaso-processed timelines, annotate events, and build a defensible narrative of attacker activity.

## When to use
- Reconstructing the sequence of events in a compromise investigation.
- Collaborating across analysts on a shared timeline during a major incident.
- Correlating endpoint, network, and log evidence into one narrative.
- Preparing a timeline exhibit for legal or executive reporting.

## Prerequisites
- Timesketch deployment with storage and processing capacity sized for the case.
- Forensic images or log exports processed into a timeline format (plaso output).
- Case scope and time window agreed with the investigation lead.
- Analyst accounts with appropriate case-access permissions.

## Procedure
1. Scope the timeline. Define the hosts, time window, and event types relevant to the investigation; exclude noise sources early.
2. Ingest the data. Import plaso timelines or CSV event exports into a Timesketch sketch; verify timestamps parsed correctly and timezones are consistent.
3. Establish the known-good baseline. Identify normal user and system activity patterns so anomalies stand out.
4. Search and filter iteratively. Use Timesketch search to isolate execution events, persistence mechanisms, and lateral movement; save useful views.
5. Annotate key events. Tag events with labels and add analyst comments linking evidence to hypotheses; this builds the shared narrative.
6. Build stories. Assemble annotated events into a chronological story that answers who, what, when, and how.
7. Correlate across sketches. When multiple hosts are involved, align their timelines to trace lateral movement between systems.
8. Export and preserve. Export the final timeline and story for the case report; retain the sketch for the evidence-retention period.

## Expected outputs
- Collaborative Timesketch sketch with annotated events and a narrative story.
- Exported timeline supporting the investigation report.
- Saved views reusable for similar future investigations.

## Pitfalls
- Timezone mismatches between sources silently scramble event order; normalize first.
- Ingesting everything without scoping overwhelms analysts and slows the tool.
- Unannotated timelines are hard to defend later; comment as you analyze.
- Overwriting or deleting the sketch before retention requirements expire.

## References
- Timesketch project documentation
- Plaso (log2timeline) documentation for timeline generation
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR508 concepts for timeline analysis
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
