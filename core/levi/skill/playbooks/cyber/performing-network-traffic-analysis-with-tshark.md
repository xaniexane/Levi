---
skill_id: cyber_performing_network_traffic_analysis_with_tshark
name: Network Traffic Analysis with tshark
description: Use tshark for scripted, large-scale packet analysis, statistics, and IOC extraction from the command line.
risk: low
permissions: []
requires_confirmation: false
tags: [network, tshark, analysis]
version: 1.0.0
---

## Purpose
- Analyze captures too large for interactive tools through fast command-line statistics and filtering.
- Script repetitive analysis so the same checks run identically across every capture in an incident.
- Extract fields and IOCs in machine-readable form for direct ingestion into SIEMs and threat-intel platforms.
- Enable remote and headless analysis on sensors and jump hosts without a GUI.

## When to use
- When captures exceed what fits comfortably in an interactive Wireshark session.
- When automating triage across many captures from distributed sensors.
- When field-level extraction (DNS queries, TLS SNI, HTTP hosts) is needed for hunting.
- When working over SSH on a sensor or analysis server with no graphical interface.

## Prerequisites
- tshark installed with capture privileges configured, plus disk space for extracted output.
- Familiarity with display filters and field names, and a reference for the protocols in the capture.
- Incident context: time windows, suspect hosts, and the questions to answer.
- A scripting environment (shell or Python) for chaining tshark output into further analysis.

## Procedure
1. Verify the capture file and record its basic properties: packet count, duration, and capture interface metadata.
2. Generate summary statistics: protocol hierarchy, conversation lists, and IO statistics over time to spot bursts and anomalies.
3. Extract DNS queries and responses, listing queried names, response codes, and unusually long or frequent queries.
4. Extract TLS handshake details including SNI values, certificate subjects, and JA3-style fingerprints where tooling supports it.
5. Extract HTTP request hosts, URIs, user agents, and response codes, flagging rare user agents and odd methods.
6. Filter to suspect hosts and windows, then dump full packet details or reassembled streams for the shortlisted sessions.
7. Run entropy and size analysis on DNS and ICMP payloads to surface tunneling candidates.
8. Export findings as CSV or JSON for correlation with logs and for sharing with the wider team.
9. Save every command in a script file so the full analysis reruns identically on the next capture.
10. Document the exact tshark commands and filters used so the analysis is reproducible.

## Expected outputs
- Statistical profiles and field extractions in structured formats ready for correlation.
- A shortlist of suspicious sessions with supporting packet evidence.
- Reproducible command history for the case file.
- Reusable tshark scripts for future triage work.

## Pitfalls
- Writing display filters from memory and silently filtering out the evidence; test filters on a known sample first.
- Letting huge default outputs exhaust disk; always scope extractions with filters and output limits.
- Forgetting time-zone handling when correlating tshark timestamps with log sources.
- Assuming field names are stable across Wireshark versions; verify against the installed version's field reference.

## References
- tshark manual and Wireshark documentation, https://www.wireshark.org/docs/man-pages/tshark.html
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- Wireshark display filter reference, https://www.wireshark.org/docs/dfref/
- Wireshark fields documentation for the installed version
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
