---
skill_id: cyber_building_detection_rule_with_splunk_spl
name: Building Detection Rules with Splunk SPL
description: Practitioner guide to authoring, testing, and operationalizing Splunk detection rules in the Splunk Processing Language.
risk: info
permissions: []
requires_confirmation: false
tags: [detection, siem, engineering]
version: 1.0.0
---
## Purpose
This playbook covers the full lifecycle of a Splunk detection: translating a threat behavior into a Search Processing Language query, validating it against historical data, setting thresholds, and promoting it to a production alert with a response runbook. It focuses on behavior-based detections that survive better than signature-only rules.

## When to use
- Turning a threat-hunting hypothesis or incident lesson into a permanent detection.
- Migrating Sigma or vendor rules into a Splunk environment.
- Reviewing noisy or stale correlation searches for rewrite or retirement.
- Training new detection engineers in SPL authoring standards.

## Prerequisites
- Splunk access with rights to create and schedule saved searches.
- Understanding of the relevant data models (for example, Endpoint, Network Traffic) and sourcetypes.
- Baseline of normal activity for the environment to set thresholds.
- Change process for promoting searches from development to production.

## Procedure
1. Define the detection objective. Write one sentence stating the adversary behavior to catch, plus the ATT&CK technique and the data source that observes it.
2. Draft the SPL against a sample. Use a time-bounded search over known-good and known-bad periods; prefer data-model tstats or accelerated datasets for performance.
3. Validate true positives. Run the search over historical incident data; confirm it fires on real cases and inspect every field the analyst will need.
4. Measure the noise floor. Run over at least 14 days of production data; count alerts per day and per asset type. Rewrite or add suppressions until volume is triageable.
5. Build the alert action. Configure throttling, severity, and a description that tells the analyst exactly what to check first; link the response runbook.
6. Map and document. Record the ATT&CK technique, data-source dependencies, and known limitations in the rule description and a central detection catalog.
7. Promote and schedule. Deploy through your normal change process, schedule with appropriate cron and time ranges, and verify the first production firings.
8. Review on a cadence. Revisit every rule quarterly: check firing rates, true-positive ratios, and whether the technique is still relevant.

## Expected outputs
- Production SPL detection with documented objective, ATT&CK mapping, and runbook link.
- Baseline measurements and threshold justification.
- Entry in the detection catalog with ownership and review date.

## Pitfalls
- Overly broad wildcards that match half the fleet and bury analysts in noise.
- Hard-coded hostnames or usernames that rot within weeks; parameterize or generalize.
- Slow searches that never complete; use summary indexing or data models for heavy queries.
- Rules without runbooks produce inconsistent, untracked triage.

## References
- Splunk documentation: Search Processing Language (SPL) reference
- Splunk Enterprise Security content update (ESCU) methodology
- MITRE ATT&CK for technique mapping
- NIST SP 800-92, Guide to Computer Security Log Management
