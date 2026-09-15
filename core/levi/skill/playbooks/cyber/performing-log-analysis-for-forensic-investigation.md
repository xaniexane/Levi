---
skill_id: cyber_performing_log_analysis_for_forensic_investigation
name: Log Analysis for Forensic Investigation
description: Correlate multi-source logs into an evidence-backed incident timeline.
risk: info
permissions: []
requires_confirmation: false
tags: [forensics, logs, investigation]
version: 1.0.0
---
# Log Analysis for Forensic Investigation

## Purpose

Incidents leave traces across dozens of log sources — endpoints,
firewalls, proxies, identity providers, applications — and the truth
emerges only when they are correlated into one timeline. This playbook
provides a methodical approach to multi-source log analysis for
forensic investigations.

## When to use

- Any incident requiring a defensible timeline of attacker activity.
- Scoping which systems and accounts were affected.
- Validating or refuting an initial compromise hypothesis.
- Preparing evidence for legal, HR, or regulatory proceedings.

## Prerequisites

- Access to the relevant log sources or their SIEM copies, with
  retention covering the suspected incident window.
- Verified time synchronization across sources, or documented offsets.
- A working hypothesis and a list of known indicators (IPs, users,
  hashes, time ranges) to pivot on.

## Procedure

1. Define the window generously: start at least a week before the
   earliest known indicator — attackers dwell, and tight windows
   miss the initial access.
2. Normalize time: convert all timestamps to UTC, document each
   source's offset and any skew discovered, and note it in the case
   file.
3. Pivot systematically: for each known indicator, search every
   source — the same IP in firewall, proxy, and VPN logs; the same
   user in identity, endpoint, and application logs.
4. Build the master timeline: merge events chronologically with
   source citations; mark confidence per event (direct evidence vs.
   inference).
5. Fill the gaps deliberately: for each unexplained period, ask which
   source should have recorded activity and whether its absence means
   nothing happened or the log is missing/tampered.
6. Corroborate key events: initial access, privilege escalation,
   lateral movement, and exfiltration each need at least two
   independent sources before they are stated as fact.
7. Challenge the hypothesis: actively search for evidence that
   contradicts the current theory — a second intrusion vector, an
   earlier start date, a wider scope.
8. Write the narrative: a clear, cited account of what happened, when,
   and how you know — suitable for stakeholders and, if needed, legal
   proceedings.

## Expected outputs

- A master timeline with per-event source citations and confidence
  levels.
- Corroborated findings for each incident phase.
- Documented gaps and their implications.
- A written narrative for stakeholders.

## Pitfalls

- Tunnel vision on one source: the firewall log alone never tells
   the whole story.
- Ignoring time-zone and skew issues: misaligned timelines create
   false sequences.
- Presenting inference as fact: label confidence honestly.
- Stopping when the timeline "looks complete": run the
   contradiction check before closing.

## References

- NIST SP 800-61, Computer Security Incident Handling Guide
- NIST SP 800-92, Guide to Computer Security Log Management
- SANS FOR508 forensic analysis methodology references
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
