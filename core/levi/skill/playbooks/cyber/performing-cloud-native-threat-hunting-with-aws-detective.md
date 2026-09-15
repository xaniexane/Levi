---
skill_id: cyber_performing_cloud_native_threat_hunting_with_aws_detective
name: Cloud-Native Threat Hunting with AWS Detective
description: Hunt for threats in AWS using Detective's entity graphs, findings aggregation, and behavior profiles.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, threat-hunting, aws]
version: 1.0.0
---

## Purpose

AWS Detective builds entity-behavior graphs from CloudTrail, VPC flow logs, and GuardDuty findings, letting hunters pivot from an IP to the EC2 instance to the IAM role to the S3 bucket in a single visual investigation. This playbook covers a threat-hunting methodology with Detective: forming hypotheses, using the graph to explore entity relationships, validating findings against raw logs, and converting confirmed hunts into durable detections.

## When to use

- Proactive threat hunting in AWS when you have a hypothesis but no alert.
- Triaging a GuardDuty finding and needing the full entity context around it.
- Investigating impossible-travel or anomalous API activity flagged by Detective's profiles.
- Mapping the blast radius of a compromised IAM principal or instance.
- Building cloud hunting tradecraft for an analyst team new to AWS.

## Prerequisites

- Amazon Detective enabled in the target Regions, with GuardDuty feeding it findings (Detective's value compounds with GuardDuty).
- Sufficient Detective data retention for your hunting window; confirm the behavior graph covers the period of interest.
- Read access to Detective, CloudTrail Lake/Athena, and VPC flow logs for validating graph-derived hypotheses against raw evidence.
- A hypothesis backlog: threat-intel-driven ideas (e.g., "attackers abusing STS from our CI roles") and baseline-deviation ideas (e.g., "instances talking to first-seen external IPs").
- Documented hunting time-boxes and a capture process for turning hunts into detections.

## Procedure

1. **Start from a hypothesis, not the console.** Write the hypothesis explicitly: the adversary behavior you expect, the entities involved, and what evidence would confirm or refute it. Example: "Compromised CI role assumes admin role then touches KMS keys it never used before."
2. **Seed the investigation from a finding or entity.** Open Detective from a GuardDuty finding, an IAM principal, an IP address, or an instance. Use the entity profile to review its baseline: normal API call volume, usual geolocations, typical network peers.
3. **Pivot along relationships.** Follow the graph: IP → instances it talked to → roles those instances assumed → S3 buckets those roles accessed. At each hop, ask whether the relationship is expected. Detective's timeline view shows when each relationship was active — focus on new or unusual edges.
4. **Check for role-session chaining.** Hunt specifically for `AssumeRole` sequences that deviate from baseline: long chains, roles assumed from unexpected source IPs, or session durations inconsistent with the workload. Cross-account assumptions deserve extra scrutiny.
5. **Validate against raw logs.** Detective summarizes; it does not replace evidence. For every candidate finding, pull the underlying CloudTrail events (exact API calls, request parameters, error codes) and flow logs (bytes, ports) to confirm the behavior is real and malicious rather than a graph artifact.
6. **Rule out benign explanations.** New automation, region expansions, and vendor integrations create novel-but-legitimate graph edges constantly. Check change records and deployment timelines before declaring a hunt successful.
7. **Scope confirmed activity.** When a hunt confirms malicious behavior, use the graph to enumerate the full blast radius: every entity the compromised principal touched, every resource those entities can reach. Export the subgraph as the incident scoping input.
8. **Convert the hunt to detection.** Encode the validated pattern as a durable detection: a GuardDuty-adjacent custom finding, a scheduled Athena query, or a SIEM rule — with the Detective investigation linked as the reference case.

## Expected outputs

- Documented hypotheses with confirm/refute outcomes and supporting evidence.
- Investigation records: entity graphs explored, pivots taken, and raw-log validation for each candidate finding.
- Blast-radius scoping for confirmed compromises, exported from the graph.
- New or tuned detections derived from successful hunts, with reference investigations.
- A hunting log that builds institutional knowledge across the analyst team.

## Pitfalls

- Hunting without hypotheses — clicking through the graph aimlessly burns hours and produces nothing defensible.
- Treating Detective's summaries as evidence; always validate against CloudTrail and flow logs before acting.
- Regions without Detective enabled create blind spots that look like "no activity" — verify coverage, not just results.
- Ignoring the data-retention boundary; hunts reaching past retention produce misleadingly clean graphs.
- Failing to convert hunts into detections, which means the same hunt must be repeated manually forever.

## References

- Amazon Detective documentation (entity profiles, investigation process)
- Amazon GuardDuty finding types reference
- MITRE ATT&CK cloud techniques (T1078, T1550, T1580 — cloud infrastructure discovery)
- "The Threat Hunting Playbook" concepts (Sqrrl/David Bianco's hunting maturity model)
- AWS documentation on CloudTrail Lake for raw-log validation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
