---
skill_id: red_credential_phishing_page
name: Credential Phishing Page Test
description: Stand up a cloned login page in a controlled test to measure credential-submit rates and MFA resilience.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, phishing, credentials]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_email_headers_for_phishing_investigation
---
# Credential Phishing Page Test

## Purpose

Find out what happens after the click: do users enter credentials, does MFA stop the
test, does the SOC notice the lookalike domain? The cloned page captures nothing real —
submissions are hashed or discarded — but the submit rate and MFA-bypass rate are the
metrics that matter.

## When to use

- After a phishing simulation shows high click rates, to test the next layer.
- To validate MFA enrollment coverage and phishing-resistant MFA rollout.
- When the threat model includes credential harvesting against SSO portals.

## Prerequisites

- Authorization for credential-phishing specifically; some orgs allow click-tracking but
  not submit-tracking — honor the distinction.
- Lookalike domain approved and registered; certificate obtained legitimately.
- Agreement that submitted credentials are never stored in recoverable form.

## Procedure

1. Clone the target login page's look (public assets only) on the approved lookalike domain
   with TLS.
2. Implement submit handling that hashes or immediately discards credentials and logs only
   the submit event + timestamp.
3. Drive traffic via the approved phishing wave; record delivered → visited → submitted
   funnel metrics.
4. For submitters, test the MFA layer: does the org use phishing-resistant MFA (FIDO2), or
   would a real-time relay have succeeded? Report, don't relay, unless relay testing is
   explicitly authorized.
5. Monitor for blue-team detection: was the lookalike domain reported, blocklisted, or
   taken down, and how fast?
6. Debrief: submit rate, MFA coverage gaps, and detection timeline become the awareness and
   identity findings.

## Expected outputs

- Visit/submit funnel metrics per wave.
- MFA posture assessment: coverage and phishing-resistance of enrolled methods.
- Lookalike-domain detection timeline.

## Pitfalls

- Storing submitted credentials in plaintext 'for the report' — never; hash-or-discard
  is the rule.
- Cloning pages with copyrighted assets beyond fair-use test scope — keep it minimal and
  client-approved.
- Letting the lookalike domain linger after the test — tear it down and document the
  teardown.

## References

- MITRE ATT&CK: Phishing — Spearphishing Link (T1566.002).
- NIST SP 800-63B: MFA phishing resistance.

## Blue-team control under test

This playbook validates their MFA rollout and lookalike-domain monitoring get tested end
to end — every submitter without phishing-resistant MFA is an identity-program gap.
Paired blue-team counterpart:
`cyber_analyzing_email_headers_for_phishing_investigation`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
