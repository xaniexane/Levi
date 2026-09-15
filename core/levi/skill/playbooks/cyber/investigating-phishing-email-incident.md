---
skill_id: cyber_investigating_phishing_email_incident
name: Investigating a Phishing Email Incident
description: Forensically investigate a reported phishing email from headers to campaign scope.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, investigations, email-forensics]
version: 1.0.0
---
## Purpose
This playbook is the analyst's guide to investigating a single reported phishing email: authenticating the message, analyzing payloads safely, determining campaign scope, and identifying victims — producing a complete, defensible case record.

## When to use
- A user reports a suspicious email or the gateway flags a phish that reached inboxes.
- You need to determine whether a phish is opportunistic or targeted.
- Post-incident review requires the full scope: who got it, who clicked, what happened next.

## Prerequisites
- Access to the original message with full headers (EML/MSG preserved, not forwarded inline).
- Mail gateway logs, mail platform message trace, and sandbox detonation capability.
- Endpoint and identity telemetry to check for victim follow-on activity.

## Procedure
1. **Preserve the original.** Obtain the message as EML/MSG with intact headers; work from a copy in the analysis environment, never from a live inbox.
2. **Analyze headers.** Trace the Received chain, verify SPF/DKIM/DMARC results, compare envelope-from vs. header-from vs. reply-to, and check for lookalike domains and display-name spoofing.
3. **Extract and enrich IOCs.** Pull URLs, attachment hashes, sender infrastructure; check reputation and passive DNS, and note newly-registered or fast-flux infrastructure.
4. **Detonate safely.** Submit URLs and attachments to a sandbox; capture the full behavior chain (redirects, credential-harvesting pages, droppers) without touching it from a corporate host.
5. **Determine scope.** Search mail logs for all recipients of the same campaign (subject, sender, hash, URL patterns); build the recipient list.
6. **Identify victims.** Correlate clicks, attachment opens, and credential submissions; for each victim, check for subsequent anomalous logons, MFA changes, or mailbox rules.
7. **Contain and document.** Ensure purge/blocks are in place, victims are remediated (password resets, session revocation, endpoint checks), and the case record captures the full timeline.

8. **Check for lateral phishing.** Look for internal-to-internal sends of the same lure, indicating a compromised mailbox is now the sender; these bypass most gateway controls.
9. **Update awareness training.** Feed anonymized real examples into the security awareness program; nothing trains users like the phish that almost got their team.

## Expected outputs
- Case file: original message, header analysis, IOC list, sandbox report.
- Campaign scope: recipient list with victim/non-victim disposition.
- Remediation checklist per victim and detection improvements filed.
- Example: header analysis shows SPF fail with a lookalike domain registered 2 days ago; sandbox detonation reveals a credential harvester, and the campaign scope identifies 45 recipients with 4 confirmed credential submissions.

## Pitfalls
- Analyzing a forwarded copy with mangled headers; always get the original.
- Clicking links from a workstation instead of detonating in a sandbox.
- Closing the case at "email deleted" without checking for victims who already acted.

- Declaring the message benign because the link is currently dead; phishing infrastructure is often short-lived, so analyze cached and sandbox captures instead.
- Forgetting to check URL shorteners and redirectors in the message body; the visible link text is not the destination.

## References
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- CISA phishing guidance (cisa.gov) — analysis and reporting practices.
- SANS FOR508 (sans.org) — email forensics and phishing investigation techniques.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
