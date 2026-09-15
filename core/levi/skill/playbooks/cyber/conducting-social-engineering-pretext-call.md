---
skill_id: cyber_conducting_social_engineering_pretext_call
name: Defending Against Malicious Pretext Calls (Vishing)
description: Defensive playbook for recognizing, analyzing, and hardening against vishing and pretext-call social engineering.
risk: info
permissions: []
requires_confirmation: false
tags: [social-engineering, awareness, defense]
version: 1.0.0
---
## Purpose
Attackers call help desks and employees posing as executives, IT staff, or vendors to extract credentials or authorize changes. This playbook is defensive: training staff to recognize pretext calls, building verification procedures that defeat them, and analyzing real attempts to improve defenses. It does not teach how to conduct deceptive calls.

## When to use
- After a vishing attempt targeting the help desk or employees.
- Building call-verification procedures for sensitive requests.
- Training staff to recognize social-engineering calls.
- Analyzing a successful pretext call as part of incident response.

## Prerequisites
- Call-handling procedures for password resets and sensitive changes.
- Defined verification methods (call-back to known numbers, manager approval).
- Reporting channel for suspicious calls.
- Training program that includes voice-based scenarios.

## Procedure
1. Recognize the patterns. Train staff on common pretexts: urgent executive requests, IT support needing credentials, vendor verification calls, and authority-pressure tactics.
2. Establish verification procedures. Require call-back to known numbers for sensitive requests; never act on caller-provided contact details alone.
3. Define what is never done by phone. Publish a clear list: passwords are never requested or reset without verification, wire changes need dual approval, and so on.
4. Build the reporting habit. Make reporting suspicious calls fast and blameless; log every attempt with the pretext used and information sought.
5. Analyze real attempts. Review reported calls for the pretext, target role, and requested action; identify which procedures held and which failed.
6. Harden the help desk. Implement identity-verification steps for callers requesting resets or changes; audit compliance with mystery-call testing done ethically.
7. Limit information leakage. Reduce what public sources reveal about org charts, internal tools, and processes that callers weaponize.
8. Rehearse regularly. Include vishing scenarios in awareness training and tabletop exercises; update procedures after each real attempt.

## Expected outputs
- Call-verification procedures for sensitive requests.
- Trained staff with a practiced reporting habit.
- Analysis of real attempts feeding procedure improvements.

## Pitfalls
- Procedures that exist on paper but are skipped under urgency; rehearse under pressure.
- Punishing employees who report failed verification attempts kills future reports.
- Verification via caller-provided numbers is not verification.
- Focusing only on the help desk while executives and finance are also targeted.

## References
- CISA social-engineering and phishing guidance
- NIST SP 800-50, Building an Information Technology Security Awareness and Training Program
- FBI IC3 guidance on business email compromise and vishing trends
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
