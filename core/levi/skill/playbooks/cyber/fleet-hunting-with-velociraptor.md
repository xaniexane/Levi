---
skill_id: cyber_fleet_hunting_with_velociraptor
name: Fleet Hunting with Velociraptor
description: Run enterprise-wide threat hunts with Velociraptor: VQL hunts, artifact collection, and safe handling of live-endpoint queries.
risk: moderate
permissions: []
requires_confirmation: true
tags: [hunting, edr, dfir]
version: 1.0.0
---
## Purpose

Velociraptor is an open-source endpoint visibility and collection tool
that lets defenders query and collect from thousands of endpoints using
VQL (Velociraptor Query Language) and prebuilt artifacts. This playbook
covers planning and executing fleet-wide hunts — IOC sweeps, anomaly
hunts, and forensic collections — while respecting that every hunt touches
live production endpoints.

## When to use

- An IOC (hash, domain, registry key) must be swept across the entire
  fleet quickly.
- Hunting hypotheses need fleet-wide validation (e.g. "which hosts ran
  this LOLBin with these arguments in the last 7 days").
- Incident response requires targeted forensic collection (MFT,
  event logs, memory) from a subset of hosts.
- Proactive threat hunting campaigns on a recurring schedule.

## Prerequisites

- Authorization for fleet-wide querying, including what data may be
  collected and retention limits — hunts touch live user endpoints.
- A deployed, healthy Velociraptor server and enrolled clients with
  current versions.
- Familiarity with VQL and the artifact exchange; test every hunt in the
  lab or on a pilot group before fleet-wide execution.
- A hunt-intake process: hypothesis, scope, data minimization, and
  defined outputs.

## Procedure

1. **Write the hypothesis first.** Define what you are hunting, the
   expected telemetry, and what a positive looks like — e.g. "hosts
   with WMI event subscriptions created outside our software-
   deployment tooling." A hunt without a hypothesis is a fishing trip.
2. **Select or write the artifact.** Prefer vetted artifacts from the
   artifact exchange; when writing custom VQL, keep queries selective
   (targeted paths, time bounds) to limit endpoint and server load.
3. **Pilot before fleet-wide.** Run the hunt against a small pilot group
   (lab hosts, then a production sample). Measure client CPU/IO impact,
   result volume, and false positives. Tune the VQL before scaling.
4. **Execute with data minimization.** Scope hunts by OS, label, or
   organizational unit; collect only the fields the hypothesis needs;
   set result-size limits and timeouts. Avoid full-disk or full-memory
   collection unless the incident justifies it.
5. **Triage results systematically.** Deduplicate, baseline against known-
   good (software inventory, admin tooling), and prioritize unexplained
   positives. Correlate hits with EDR/SIEM telemetry before declaring
   compromise.
6. **Escalate with evidence.** For confirmed hits, pivot to targeted
   forensic collection (timeline, relevant logs) from the affected hosts
   and open incident-response scoping per your IR plan.
7. **Handle the data responsibly.** Hunt results contain user and system
   data — apply retention limits, restrict access to the investigation
   team, and purge collections when the hunt closes.
8. **Operationalize recurring hunts.** Convert validated hunts into
   scheduled hunts or monitoring artifacts with alerting, and review
   their precision periodically to prevent alert decay.

## Expected outputs

- A hunt plan: hypothesis, artifact/VQL, scope, and success criteria.
- Pilot results with performance and false-positive measurements.
- Fleet-wide results: hit list with triage dispositions.
- Incident escalations for confirmed positives with collected evidence.
- Scheduled/recurring hunt definitions for durable coverage.

## Pitfalls

- Fleet-wide hunts on unscoped queries can degrade endpoint performance
  or overwhelm the server — always pilot and bound.
- Collecting more than the hypothesis needs creates privacy and
  retention liability — minimize by default.
- Stale artifacts from the exchange may not match your client versions —
  test, do not assume.
- Positive hits still need corroboration: a hash match alone does not
  prove compromise — check execution context.
- Forgetting to purge hunt collections turns the Velociraptor server
  into an unmanaged data store — build cleanup into the workflow.

## References

- Velociraptor official documentation (VQL reference, artifact
  exchange)
- MITRE ATT&CK (hypothesis and technique mapping)
- NIST SP 800-86: forensic techniques in incident response
- CISA: threat-hunting guidance publications
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
