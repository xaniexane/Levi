---
skill_id: cyber_performing_log_source_onboarding_in_siem
name: Log Source Onboarding in SIEM
description: Onboard new log sources with parsing, normalization, and validation.
risk: info
permissions: []
requires_confirmation: false
tags: [siem, logging, engineering]
version: 1.0.0
---
# Log Source Onboarding in SIEM

## Purpose

A log source that is not parsed, normalized, and validated is just
expensive storage. This playbook onboards new sources into the SIEM
properly: transport, parsing, field normalization, and verification that
detections can actually use the data.

## When to use

- Adding a new application, appliance, or cloud service to the SIEM.
- Migrating log transport (syslog to agent, agent to API poll).
- Fixing a source whose events arrive but are unusable.
- Expanding coverage to meet a compliance logging requirement.

## Prerequisites

- Network and authentication path from the source to the SIEM
  (syslog receiver, agent, or API credentials) approved by change
  management.
- Sample log data and documentation of the log format.
- Knowledge of the SIEM's parsing/normalization model (CIM, ECS,
  or vendor schema).

## Procedure

1. Define the use case first: which detections, hunts, or compliance
   requirements need this source — this determines which fields must
   be parsed, not just shipped.
2. Establish reliable transport: syslog over TLS, an agent, or API
   polling with checkpointing; verify no loss during restarts and
   that timestamps arrive intact.
3. Build and test parsing: write the parser against real samples,
   covering the full variety of event types the source emits — not
   just the common ones.
4. Normalize to the common schema: map source fields to the SIEM's
   standard fields (user, src_ip, action, outcome) so existing
   detections and dashboards work without custom logic.
5. Validate end to end: generate known test events at the source and
   confirm they appear in the SIEM correctly parsed, timestamped,
   and searchable within the expected latency.
6. Set health monitoring: alert on volume drops, parsing failures,
   and transport errors — a silent source is a blind spot.
7. Document the source: owner, transport method, parser version,
   retention, and the detections that depend on it.
8. Review after 30 days: check parsing-failure rates, confirm the
   intended detections fire on real data, and tune as needed.

## Expected outputs

- A fully parsed, normalized log source searchable in the SIEM.
- End-to-end validation evidence with test events.
- Health monitoring for volume and parsing failures.
- Source documentation with ownership and dependencies.

## Pitfalls

- Shipping logs without parsing: unparsed events are invisible to
   detections.
- Testing with one sample event type: rare event types break parsers
   in production.
- No health monitoring: the source dies silently and nobody notices
   for months.
- Skipping normalization: every detection becomes a custom query and
   maintenance collapses.

## References

- NIST SP 800-92, Guide to Computer Security Log Management
- SIEM vendor documentation on parsing and CIM/ECS normalization
- CIS Critical Security Controls v8, Control 8 (Audit Log Management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
