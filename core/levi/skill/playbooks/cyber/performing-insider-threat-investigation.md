---
skill_id: cyber_performing_insider_threat_investigation
name: Insider Threat Investigation
description: Investigate suspected malicious insider activity with legal and HR coordination.
risk: low
permissions: []
requires_confirmation: false
tags: [insider-threat, investigation, forensics]
version: 1.0.0
---
# Insider Threat Investigation

## Purpose

Insider cases combine technical evidence with employment law, privacy
rights, and HR process — mishandle any of them and the investigation
fails in court or destroys trust. This playbook structures a defensible
insider-threat investigation: evidence preservation, discreet collection,
and coordination with legal and HR from the start.

## When to use

- A tip or alert suggests data theft, sabotage, or fraud by an
  employee or contractor.
- Anomalous DLP or UEBA alerts cluster around one identity.
- Exit-risk reviews for departing privileged staff.
- Validating or clearing a suspected insider.

## Prerequisites

- Legal counsel engaged before collection begins: employee monitoring
  laws, works-council agreements, and consent requirements vary by
  jurisdiction.
- HR partnership: a defined process for interviews, suspension, and
  evidence holds.
- Authorization to collect the specific data sources in scope, in
  writing.

## Procedure

1. Engage legal and HR first: confirm what monitoring is permitted,
   whether the subject may be interviewed, and how evidence must be
   handled for potential employment or criminal action.
2. Preserve evidence quietly: place legal holds on mailbox, file shares,
   and endpoint data before the subject can delete anything — without
   tipping them off.
3. Build the behavioral baseline: the subject's normal access patterns,
   working hours, and data volumes over 60–90 days, so anomalies are
   measured, not assumed.
4. Collect discreetly: DLP alerts, file-access logs, email exfiltration
   indicators, USB and print logs, badge records, and cloud-app audit
   trails — correlate into a single timeline.
5. Distinguish malice from sloppiness: compare against peers doing
   similar work; bulk downloads before resignation look different from
   bulk downloads for a legitimate migration.
6. Interview with HR present: follow the organization's process, avoid
   leading the subject, and document everything — or defer the
   interview to HR/legal if policy requires.
7. Decide on facts, not suspicion: exonerate clearly when evidence
   does not support the allegation, and document the reasoning either
   way.
8. Close the loop: revoke access promptly on termination, review what
   data left and whether notification is required, and feed lessons
   into DLP and offboarding controls.

## Expected outputs

- A legal-hold and evidence-preservation record.
- A correlated timeline of the subject's anomalous activity.
- A findings memo: substantiated, unsubstantiated, or inconclusive,
  with evidence citations.
- Remediation: access changes, control improvements, notifications.

## Pitfalls

- Collecting before legal clears it: illegally obtained evidence is
   useless and creates liability.
- Alerting the subject through careless collection (unexpected MFA
   prompts, visible agents).
- Confirmation bias: deciding guilt first and reading logs to match.
- Neglecting the exoneration path: a cleared employee deserves a
   clean, documented record.

## References

- CISA Insider Threat Mitigation Guide (cisa.gov)
- CERT Insider Threat Center research (Carnegie Mellon SEI)
- NIST SP 800-53, personnel security and audit controls (PS, AU families)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
