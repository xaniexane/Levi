---
skill_id: cyber_building_detection_rules_with_sigma
name: Building Detection Rules with Sigma
description: Practitioner guide to writing portable Sigma detection rules and converting them for SIEM deployment.
risk: info
permissions: []
requires_confirmation: false
tags: [detection, siem, engineering]
version: 1.0.0
---
## Purpose
Sigma is a generic, vendor-neutral format for describing log-based detections. This playbook teaches defenders to author Sigma rules -- from logsource selection to condition logic -- test them, and convert them into platform-specific queries (Splunk, Elastic, Sentinel) for deployment. Portable rules reduce lock-in and make threat-intel sharing practical.

## When to use
- Writing a detection once and deploying it across multiple SIEM platforms.
- Contributing to or consuming community detection repositories.
- Standardizing detection-as-code practices in your detection engineering team.
- Translating a published Sigma rule to your local field names and data sources.

## Prerequisites
- Familiarity with the target log schema (for example, Sysmon event IDs, Windows Security events).
- Sigma specification knowledge and a converter (pySigma or the legacy sigmac toolset).
- Test environment with representative log data.
- Source control for the rule repository.

## Procedure
1. Identify the behavior and data source. Pick one ATT&CK technique and the log source that best observes it; write the objective in one sentence.
2. Choose the logsource. Set product, category, and service fields so the rule matches the intended telemetry (for example, Windows process_creation).
3. Write the selection logic. Use selections for known-bad indicators and filters to exclude known-good noise; keep conditions readable with named selections.
4. Add metadata. Fill in title, id (UUID), status, level, author, date, references, and tags including ATT&CK technique IDs.
5. Validate the syntax. Lint the rule against the Sigma schema; fix logsource mismatches and deprecated fields.
6. Convert for your platform. Run the rule through pySigma with the appropriate backend, then adapt field mappings to your local index and sourcetype names.
7. Test against real data. Execute the converted query over historical logs containing both benign and malicious samples; tune before production.
8. Maintain the rule. Track status (experimental to stable), review false positives quarterly, and contribute improvements back to the community repository if the rule is shareable.

## Expected outputs
- Validated Sigma rule YAML with complete metadata and ATT&CK tags.
- Platform-specific converted queries tested against production data.
- Rule entry in the detection catalog with review schedule.

## Pitfalls
- Generic logsource values that match unintended data and cause conversion failures.
- Rules written against field names your SIEM does not actually collect.
- Community rules imported without local tuning generate noise.
- Skipping the status field leaves experimental rules indistinguishable from vetted ones.

## References
- Sigma specification (SigmaHQ) and pySigma documentation
- MITRE ATT&CK for technique tagging
- NIST SP 800-92, Guide to Computer Security Log Management
- SANS guidance on detection engineering practices
