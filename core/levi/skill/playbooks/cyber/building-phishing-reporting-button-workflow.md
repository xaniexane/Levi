---
skill_id: cyber_building_phishing_reporting_button_workflow
name: Building a Phishing Reporting Button Workflow
description: Practitioner guide to deploying a report-phishing button and the triage workflow that turns user reports into rapid containment.
risk: info
permissions: []
requires_confirmation: false
tags: [phishing, detection, awareness]
version: 1.0.0
---
## Purpose
Users are the fastest phishing sensors an organization has -- if reporting is one click away. This playbook deploys a report-phishing button in the mail client and builds the backend workflow: automated triage, detonation, indicator extraction, and containment, so user reports become detections instead of tickets that rot.

## When to use
- Standing up a user-driven phishing detection capability.
- Reducing time from phishing delivery to containment.
- Replacing forwarded-to-abuse-mailbox workflows that lose metadata.
- Measuring and improving security-awareness program effectiveness.

## Prerequisites
- Mail platform that supports add-ins or native report buttons.
- Triage capacity: analysts or automation to handle report volume.
- Sandbox or detonation capability for reported messages and attachments.
- Defined containment actions (block sender, purge mailbox, reset credentials).

## Procedure
1. Deploy the button. Roll out the report-phishing add-in to mail clients; verify it preserves full message headers and attachments when submitting.
2. Build the intake queue. Route reports into a dedicated triage queue with metadata: reporter, timestamp, original headers, and attachments intact.
3. Automate initial triage. Auto-close obvious benign reports (newsletters, internal mail) using allowlists and sender reputation; escalate the rest.
4. Detonate suspicious samples. Send URLs and attachments to the sandbox; extract indicators automatically on malicious verdicts.
5. Hunt for wider delivery. Search mail logs for other recipients of the same campaign; purge malicious messages from all mailboxes.
6. Contain and remediate. Block sender domains and URLs, force password resets for users who clicked, and open an incident for successful compromises.
7. Close the loop with reporters. Send feedback to users who reported real phish; positive reinforcement sustains reporting rates.
8. Measure the program. Track report volume, true-positive rate, time to containment, and repeat-reporter rates; report trends quarterly.

## Expected outputs
- Deployed reporting button with metadata-preserving submission.
- Automated triage and containment workflow with defined SLAs.
- Program metrics: reports, true positives, time to purge.

## Pitfalls
- A button without triage capacity just creates a new backlog; staff the workflow first.
- Forwarding as attachments by hand strips headers; the button must capture originals.
- No reporter feedback kills participation within months.
- Auto-purging without verification can delete legitimate business mail.

## References
- CISA phishing guidance and reporting resources
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- Anti-Phishing Working Group (APWG) reporting best practices
