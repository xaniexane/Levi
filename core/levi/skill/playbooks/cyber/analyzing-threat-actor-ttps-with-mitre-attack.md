---
skill_id: cyber_analyzing_threat_actor_ttps_with_mitre_attack
name: Analyzing Threat Actor TTPs with MITRE ATT&CK
description: Map adversary behavior to ATT&CK: technique mapping and coverage gaps.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intel]
version: 1.0.0
---
# Analyzing Threat Actor TTPs with MITRE ATT&CK

See also: analyzing-threat-actor-ttps-with-mitre-navigator.md

## Purpose

Turn scattered incident evidence and threat-intel reporting into a structured technique profile
using the MITRE ATT&CK framework: map observed behaviors to technique and sub-technique IDs,
identify which tactics are covered and which are blind spots, and produce an intelligence product
that defenders can act on. ATT&CK gives every stakeholder the same vocabulary.

A good technique profile does two jobs at once: it describes what the actor did (intelligence), and
it exposes what you cannot see (detection gaps). This playbook treats both as deliverables.

## When to use

- Post-incident: reconstructing the full technique chain an intruder used in your environment.
- Threat-intel consumption: converting a vendor report ("the actor uses X") into technique mappings
  your detection team can implement.
- Gap analysis: comparing your detection coverage against the techniques a tracked actor is known to
  use.
- Tabletop or purple-team planning: defining the exact behaviors the exercise will emulate and
  detect.
- Detection engineering intake: turning "we need to detect this actor" into a concrete technique
  list.

## Prerequisites

- Written authorization for the investigation scope (incident charter or intel-tasking memo),
  including which environments' data you may analyze and how findings may be shared (internal only,
  TLP marking).
- The evidence set: incident timelines, endpoint telemetry, firewall/proxy logs, malware analysis
  notes, or the intel report being mapped — with sources and collection dates recorded.
- Access to the current ATT&CK enterprise matrix (attack.mitre.org or an offline export); note the
  ATT&CK version in your work product since technique IDs and names change between releases.
- Chain-of-custody notes for any forensic evidence underlying the mappings.

## Procedure

1. Fix the ATT&CK version. Record the exact version (e.g., v16) you are mapping against. Technique
   IDs are stable, but names, sub-techniques, and tactic assignments shift — version-pinning keeps
   the product reproducible.
2. Extract candidate behaviors from the evidence. Walk the incident timeline or intel report and
   list every discrete attacker action: "created a scheduled task named Updater," "dumped LSASS
   memory," "used PsExec to move laterally." Keep each behavior as a one-line, source-cited fact.
3. Map each behavior to a technique. For each action, find the most specific ATT&CK technique or
   sub-technique: scheduled task creation → T1053.005 (Scheduled Task/Job: Scheduled Task); LSASS
   dump → T1003.001 (OS Credential Dumping: LSASS Memory); PsExec lateral movement → T1021.002
   (Remote Services: SMB/Windows Admin Shares) or T1569.002 (Service Execution), depending on
   mechanics. Record the reasoning when the mapping is ambiguous.
4. Assign tactics and build the chain. Order the mapped techniques along the kill chain — initial
   access → execution → persistence → privilege escalation → defense evasion → credential access →
   discovery → lateral movement → collection → exfiltration → impact. Gaps in the chain are
   investigative leads, not absences: an actor who exfiltrated must have collected.
5. Distinguish observed vs. reported. Tag each technique: directly observed in your telemetry,
   reported by a trusted source, or inferred. Never let an inferred technique carry the same weight
   as an observed one in defensive planning.
6. Resolve ambiguous mappings explicitly. When two techniques fit (e.g., T1021.002 vs. T1569.002 for
   PsExec), record both candidates, the evidence for each, and your chosen primary with rationale.
   Ambiguity documented beats false precision.
7. Score detection coverage. For each mapped technique, record your current detection state:
   alerting, logged-but-not-alerted, or no visibility. This produces the gap list that drives
   detection engineering priorities.
8. Identify the actor's preferences. Aggregate across incidents or reports: which techniques recur,
   which tooling implements them (native LOLBins vs. custom malware), and which tactics the actor
   favors. Recurring sub-technique choices are the actor's signature.
9. Convert gaps to detection requirements. For each priority gap, write a one-paragraph detection
   requirement: the data source needed, the behavior to alert on, the expected true-positive rate,
   and the tuning risks. Hand these to detection engineering as actionable intake, not as a
   technique list.
10. Write the intelligence product. Produce the technique profile: tactic-by-tactic table with
    technique IDs, names, observed/reported/inferred tags, evidence citations, and detection
    coverage. Include the gap list, the detection requirements, and recommended next collection
    priorities.

## Key tools & commands

- The ATT&CK website (attack.mitre.org) or the STIX/TAXII feed for technique definitions, procedure
  examples, and detection guidance per technique page.
- MITRE's `attack-stix-data` repository for programmatic access: query technique objects offline
  with a small script.
- The `attackcti` Python library for scripted lookups of techniques, tactics, and relationships from
  the STIX data.
- Your SIEM/EDR search for validating "observed" tags — map, then verify each technique against
  actual telemetry.
- A spreadsheet or the profile template from step 10 to keep mappings consistent across analysts.
- DeTT&CT (open-source) for formal detection-coverage scoring against the technique list.

## Expected outputs

- A version-pinned ATT&CK technique profile: tactic → technique/sub-technique →
  observed/reported/inferred → evidence citation.
- An ambiguity log: contested mappings with candidates, evidence, and chosen primaries.
- A kill-chain-ordered narrative of the actor's operation.
- A detection-coverage scorecard per technique (alerting / logged / no visibility).
- Detection requirements for priority gaps, written as engineering intake.
- An actor-preference summary: recurring techniques, tooling choices, favored tactics.
- Collection priorities: what telemetry to gain to close the remaining blind spots.

## Pitfalls

- Mapping to the tactic instead of the technique: "they did persistence" is not analysis; T1053.005
  is.
- Treating intel-report mentions as observed in your environment — keep the tags strict or your gap
  analysis lies to you.
- Using an outdated ATT&CK version where a technique was renamed or split; always version-pin and
  note it.
- Over-mapping: not every admin action is adversary behavior. Require evidence of malicious context
  before assigning a technique.
- Ignoring sub-techniques: T1053 alone tells the detection team far less than T1053.005 vs.
  T1053.003 (Cron).
- Letting the profile go stale: actors evolve tooling. Re-map on a schedule for tracked actors, not
  just after incidents.
- Handing detection engineering a technique list without requirements: techniques describe the
  adversary; requirements describe what to build.

## References

- MITRE ATT&CK Enterprise Matrix (attack.mitre.org) — technique and sub-technique definitions.
- MITRE `attack-stix-data` repository — machine-readable ATT&CK content.
- `attackcti` Python library documentation — scripted ATT&CK queries.
- "ATT&CK Design and Philosophy" (MITRE whitepaper) — how techniques, tactics, and procedures
  relate.
- DeTT&CT project documentation — detection coverage mapping methodology.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
