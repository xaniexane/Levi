---
skill_id: cyber_performing_alert_triage_with_elastic_siem
name: Performing Alert Triage with Elastic SIEM
description: Triage security alerts efficiently in Elastic SIEM with consistent analyst workflow.
risk: low
permissions: []
requires_confirmation: false
tags: [siem, soc-operations, elastic]
version: 1.0.0
---

## Purpose
This playbook standardizes alert triage in Elastic Security: how analysts work the queue, use timelines and cases, enrich efficiently, and disposition consistently — so triage is fast, complete, and measurable.

## When to use
- Standing up or maturing a SOC on the Elastic Stack.
- Triage quality varies wildly between analysts and shifts.
- Alert backlogs grow faster than the team can work them.

## Prerequisites
- Elastic Security with detection engine rules producing alerts, and data views covering the needed indices.
- Analyst roles and permissions configured; case assignment workflow agreed.
- Enrichment sources available: asset/CMDB data, identity context, threat intel indicators.

## Procedure
1. **Work the queue by risk.** Sort by rule severity and risk score; use alert grouping to collapse related alerts into single investigations instead of triaging duplicates.
2. **Open a timeline immediately.** Pivot from the alert into Timeline: add the host, user, and process entities; expand with surrounding events (process tree, network, authentication) before forming hypotheses.
3. **Enrich in one pass.** Check asset criticality, user role and risk, and threat-intel matches for involved indicators; record what you checked so the next analyst does not repeat it.
4. **Apply the disposition standard.** Use consistent statuses: true positive (escalate with severity), benign true positive (tune the rule), false positive (tune or disable), duplicate (link to parent). Every alert gets a disposition and a note.
5. **Escalate with context.** Escalations include the timeline, the evidence for maliciousness, affected assets/users, and recommended containment — not just the alert link.
6. **Create cases for incidents.** Promote multi-alert investigations to Cases with an owner, timeline, and response tasks; link all related alerts.
7. **Feed back to detection engineering.** Tag alerts that need rule tuning; review the tuning backlog weekly so triage pain actually improves detections.

8. **Use Osquery and endpoint data.** Pivot from alerts into Osquery results for live host state; the freshest evidence often beats the indexed log.
9. **Run triage drills.** Periodically inject synthetic alerts to measure triage time and disposition accuracy; you cannot improve what you do not measure.

## Expected outputs
- Documented triage workflow with disposition standards and escalation template.
- Consistent case records with timelines for escalated incidents.
- Tuning backlog driven by triage feedback with measured alert-volume impact.
- Example: three related alerts (suspicious PowerShell, anomalous logon, new service) are grouped into one investigation; the timeline shows the full chain in 10 minutes and the escalation includes containment recommendations.

## Pitfalls
- Triaging alerts without timelines: slow, shallow, and inconsistent.
- Closing alerts with no disposition note, making quality review impossible.
- Letting the tuning backlog rot, so analysts triage the same false positives forever.

- Analysts working alerts oldest-first instead of highest-risk-first; queue order is a policy decision with real consequences.
- Custom Kibana queries that bypass the Security solution's alert workflow; keep triage in the governed workflow so metrics stay honest.

## References
- Elastic Security documentation (elastic.co/docs/reference/security).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- Elastic detection rules repository (github.com/elastic/detection-rules) — rule examples.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
