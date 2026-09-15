---
skill_id: cyber_performing_active_directory_penetration_test
name: Active Directory Penetration Test — Defender's Engagement Guide
description: Scope, oversee, and extract maximum defensive value from an authorized AD pentest.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, penetration-testing, governance]
version: 1.0.0
---

## Purpose
This playbook is written for the defending organization commissioning an Active Directory penetration test: how to scope it, what rules of engagement to set, how to monitor it safely, and — most importantly — how to convert findings into prioritized hardening. It does not provide offensive techniques.

## When to use
- Commissioning an external or internal red-team assessment of AD.
- Leadership wants an adversary's-eye validation of AD hardening.
- Post-incident: verifying that the exploited paths are truly closed.

## Prerequisites
- Written authorization with explicit scope: domains, OUs, accounts, allowed techniques, and forbidden actions (e.g., no production outages, no actual data exfiltration).
- Emergency contacts and a kill-switch: who can halt the test instantly.
- Blue-team monitoring in place to observe the test (this doubles as a detection validation exercise).

## Procedure
1. **Define objectives, not just scope.** State what questions the test must answer (e.g., "can a standard user reach Domain Admins?") so the report is useful, not just a finding list.
2. **Set rules of engagement.** Document allowed techniques, blackout windows, data-handling rules for any accessed data, and the escalation path for unintended impact.
3. **Brief stakeholders.** Notify SOC leadership (without necessarily telling all analysts, if you want a blind detection test), AD admins, and helpdesk of the window and the kill-switch.
4. **Monitor as a purple-team exercise.** Have the blue team detect and log the testers' activity in real time; record which techniques were caught, missed, or caught late.
5. **Require evidence-grade reporting.** Each finding needs: attack path demonstrated, business impact, and specific remediation — not generic "weak password policy" prose.
6. **Drive remediation.** Convert findings into tickets with owners and deadlines; re-test critical paths after fixes to confirm closure.
7. **Conduct the joint debrief.** Walk through the full attack chain with AD admins and the SOC; update detections for every technique the testers used, caught or not.

8. **Protect test data.** Any credentials or data the testers touch are handled under the engagement's data-handling rules; pentest reports are sensitive documents with restricted distribution.
9. **Track retest SLAs.** Findings that remain open past their SLA escalate like any vulnerability; a pentest without retest tracking is just an expensive PDF.

## Expected outputs
- Signed rules of engagement and scoping document.
- Findings report mapped to remediation tickets with retest evidence.
- Detection-gap analysis from the purple-team observation log.
- Example: testers demonstrate a Kerberoasting-to-Domain-Admins path in 3 days; the blue team caught the initial access but missed the lateral movement, producing both a hardening ticket and two new SIEM detections.

## Pitfalls
- Scope so narrow the test cannot answer the real question, or so broad it disrupts production.
- Filing the report without remediation ownership: the most common pentest failure.
- Telling the entire SOC in advance, then claiming "we would have caught it."

- Testers provided with domain-admin credentials "to save time"; the test then proves nothing about real attack paths.
- No defined handling for vulnerabilities found in out-of-scope systems during the test; agree the process in the rules of engagement.

## References
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment.
- PTES (Penetration Testing Execution Standard) for engagement structure (pentest-standard.org).
- CREST penetration testing guidance (crest-approved.org) — engagement standards.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
