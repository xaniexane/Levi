---
skill_id: cyber_implementing_mitre_attack_coverage_mapping
name: Implementing MITRE ATT&CK Coverage Mapping
description: Map detective and preventive controls to MITRE ATT&CK techniques to measure real coverage, find gaps, and prioritize detection engineering by adversary behavior.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-modeling, detection, mitre-attack]
version: 1.0.0
---
## Purpose

Replace "we have a SIEM and an EDR" with an evidence-backed answer to which adversary techniques you can actually detect and prevent. By mapping every control and detection to ATT&CK techniques and scoring the quality of each mapping, you turn the framework into a decision tool: where to write the next detection, which control gaps accept the most risk, and how coverage changes over time.

## When to use

- Prioritizing detection engineering with limited analyst time.
- Justifying security investments with adversary-informed risk language leadership understands.
- Preparing for threat-informed assessments (red team scoping, purple team exercises).
- Measuring whether a new tool (EDR, NDR, DLP) actually closes gaps or duplicates coverage.
- Reporting security posture to the board in terms of attacker capability denied, not alert counts.

## Prerequisites

- Inventory of security controls: preventive (firewalls, EDR blocking, allowlisting) and detective (SIEM rules, EDR detections, NDR analytics), each with a named owner.
- Defined scoring rubric for mapping quality (e.g., none / partial / strong) applied consistently — coverage claims without quality grades are vanity metrics.
- ATT&CK Navigator (or equivalent) for visualization, and a maintained data source (spreadsheets rot; use a versioned layer file or a GRC/detection platform).
- Threat intelligence on which adversaries and techniques actually target your sector, to weight the map.
- Agreement that the map is a living assessment, not a one-time project deliverable.

## Procedure

1. **Define scope and technique set.** Start with Enterprise ATT&CK techniques relevant to your environment (add ICS/Mobile matrices if in scope). Exclude techniques that cannot occur in your environment (e.g., cloud techniques with no cloud footprint) and document why — exclusions are decisions, not oversights.
2. **Inventory controls with technique candidates.** For each control, list the techniques it plausibly addresses: EDR process telemetry → T1059, T1003; email gateway → T1566; firewall egress rules → T1048/T1041. Be specific about data sources, not product names — "EDR" is not a technique mapping, "Sysmon Event ID 1 process creation with command line" is.
3. **Score honestly.** Grade each mapping: strong (reliable detection/prevention with tested logic and alerting), partial (telemetry exists but no tuned detection, or prevention bypassable), none. Require evidence for "strong": a tested detection rule, a purple-team validation, or a blocked red-team attempt. Default to partial when in doubt.
4. **Visualize and analyze.** Load scores into ATT&CK Navigator layers (one for prevention, one for detection). Look for patterns: entire tactics with no strong coverage (commonly Defense Evasion, Discovery), techniques with neither prevention nor detection, and over-invested techniques with five overlapping partial detections.
5. **Weight by threat intelligence.** Overlay sector-relevant adversary profiles (ransomware affiliates, your industry's APT groups) using their known technique sets. A gap in a technique your top threat actor uses weekly outranks a gap in one nobody employs.
6. **Convert gaps to a prioritized backlog.** Each gap becomes a detection-engineering or control-implementation ticket with the technique, tactic, threat relevance, and expected effort. Prioritize: high-threat-relevance × low-effort first; document accepted risks for the rest with owner sign-off.
7. **Validate with adversary emulation.** Run purple-team exercises against a sample of "strong" mappings — especially new ones. Mappings routinely fail first contact with real emulation (logic errors, missing data sources, alerts nobody triaged). Downgrade scores based on results.
8. **Reassess on cadence.** Update the map quarterly and on major changes (new EDR, cloud migration, acquired company). Track coverage trends as a security metric; a map that never changes is a map nobody maintains.

## Expected outputs

- Scoped technique set with documented exclusions.
- Control-to-technique mapping inventory with evidence-graded scores.
- ATT&CK Navigator layers for prevention and detection coverage.
- Threat-weighted gap analysis and prioritized engineering backlog.
- Purple-team validation results and quarterly coverage trend reports.

## Pitfalls

- **Product-name mappings.** "Covered by Splunk" means nothing. Map data sources and detection logic, or the map measures procurement, not protection.
- **Grade inflation.** Marking everything "strong" without tested detections produces a beautiful green heatmap and zero insight. Require evidence for strong.
- **Ignoring prevention.** Detection-only maps miss the cheaper win: blocking T1566 at the gateway beats detecting it in every mailbox. Score both layers.
- **Technique-counting as progress.** Covering 200 techniques partially is worse than covering the 30 your adversaries use strongly. Weight by threat, not by count.
- **Static deliverable.** A coverage map presented once to the board and never updated becomes fiction within two quarters as tools, teams, and threats change.

## References

- MITRE ATT&CK — https://attack.mitre.org/
- ATT&CK Navigator — https://mitre-attack.github.io/attack-navigator/
- CISA guidance on threat-informed defense and adversary emulation
- MITRE Engenuity ATT&CK Evaluations (methodology reference for validation) — https://attackevals.mitre-engenuity.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
