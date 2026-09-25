---
skill_id: cyber_implementing_security_monitoring_with_datadog
name: Implementing Security Monitoring with Datadog
description: Build security monitoring on Datadog: log pipelines, security signals, cloud SIEM content, and alert routing for the SOC.
risk: low
permissions: []
requires_confirmation: false
tags: [siem, monitoring, cloud]
version: 1.0.0
---
## Purpose

Datadog's log management, Cloud SIEM, and observability data can serve
as a security-monitoring platform when configured deliberately. This
playbook covers building SOC-ready security monitoring on Datadog:
ingestion pipelines, detection rules, signal triage, and integration
with response workflows.

## When to use

- Organizations standardized on Datadog expanding into security
  monitoring.
- Consolidating observability and security telemetry in one platform.
- Building cloud-focused detection content.
- Evaluating Datadog Cloud SIEM coverage for your threat model.

## Prerequisites

- Datadog organization with Log Management and Cloud SIEM enabled.
- Log sources: cloud audit logs, application logs, WAF/CDN, identity
  provider, and endpoint telemetry forwarded to Datadog.
- Defined SOC roles, triage queues, and escalation paths.
- Cost awareness: Datadog pricing is volume-driven — plan ingestion
  filtering deliberately.

## Procedure

1. **Design the ingestion pipeline.** Route security-relevant logs to
   Datadog with parsing pipelines that extract key fields (user,
   source IP, action, resource, result). Filter noise at ingestion
   (health checks, debug logs) to control cost without losing
   security value — document every exclusion.
2. **Standardize attributes.** Use consistent facet attributes across
   sources (e.g. `usr.name`, `network.client.ip`) so detection rules
   and investigations work uniformly. Attribute inconsistency is the
   top cause of broken Datadog detections.
3. **Deploy Cloud SIEM content.** Enable and tune Datadog's out-of-
   the-box detection rules for your environment; write custom rules
   for organization-specific threats (see the SIEM correlation-rules
   playbook for rule-design methodology). Test each rule against
   historical logs before enabling notifications.
4. **Build signal triage workflows.** Configure severities, notification
   routing (PagerDuty/Opsgenie/Slack per severity), and investigation
   dashboards per signal type. Every signal should have a documented
   triage procedure — signals without runbooks become ignored signals.
5. **Correlate with observability data.** Use Datadog's strength:
   pivot from a security signal into APM traces, infrastructure
   metrics, and RUM data for context no pure-SIEM platform provides.
   Build combined dashboards for incident response.
6. **Monitor the monitors.** Alert on pipeline health: ingestion
   drops, parsing failures, and rule-evaluation errors. A silent
   pipeline gap is a blind spot — treat monitoring health as a
   security control.
7. **Manage cost and retention.** Balance retention (security
   investigations need months) against volume cost: use archives to
   cheap storage with rehydration capability, and right-size
   ingestion with exclusion filters reviewed quarterly.
8. **Integrate response.** Connect signals to SOAR/case management:
   automated enrichment, case creation for high-severity signals, and
   bidirectional status sync so analysts work in one queue.

## Expected outputs

- Ingestion pipelines with parsing, filtering, and exclusion docs.
- Standardized attribute schema across sources.
- Tuned detection-rule set with test records.
- Triage runbooks per signal type and routing configuration.
- Pipeline-health monitoring and cost/retention policy.

## Pitfalls

- Volume-driven cost surprises — model ingestion cost before
   enabling broad log sources; exclusions need security review.
- Out-of-the-box rules without tuning — generic rules false-positive
   on every environment; tune before routing to humans.
- Attribute inconsistency across pipelines breaking rules silently —
   validate facets after every pipeline change.
- Treating Datadog as a full SIEM replacement without gap analysis —
   assess coverage against your detection requirements explicitly.
- Retention too short for investigations — align retention with
   incident-response needs, not just cost.

## References

- Datadog documentation: Log Management, Cloud SIEM, detection rules
- NIST SP 800-92: Guide to Computer Security Log Management
- MITRE ATT&CK (rule-to-technique coverage mapping)
- Cloud provider audit-log documentation for source configuration
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
