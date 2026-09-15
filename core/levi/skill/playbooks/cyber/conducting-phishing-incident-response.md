---
skill_id: cyber_conducting_phishing_incident_response
name: Conducting Phishing Incident Response
description: Practitioner guide to triaging phishing reports, scoping campaigns, containing impact, and eradicating phishing infrastructure.
risk: low
permissions: []
requires_confirmation: false
tags: [incident-response, phishing, operations]
version: 1.0.0
---
## Purpose
Phishing is the most common initial-access vector, and speed matters: every hour a campaign runs, more users click. This playbook provides the rapid-response workflow -- report triage, campaign scoping, mailbox purge, credential reset, infrastructure blocking, and victim follow-up -- that turns user reports into contained incidents.

## When to use
- Responding to user-reported phishing or phishing alerts from email security.
- Handling a phishing campaign targeting the organization.
- Following up on users who clicked or submitted credentials.
- Standardizing the team's phishing response procedure.

## Prerequisites
- Phishing reporting channel (button or mailbox) with triage workflow.
- Email security and mail-log access for campaign scoping and purging.
- Sandbox for detonating URLs and attachments.
- Pre-authorized containment actions: block, purge, credential reset.

## Procedure
1. Triage the report. Confirm the message is malicious via headers, URLs, and sandbox detonation; classify as generic phish, spearphish, or credential harvester.
2. Scope the campaign. Search mail logs for all recipients of the same sender, subject, or indicators; identify who received, who opened, and who clicked.
3. Purge malicious messages. Remove the phishing emails from all mailboxes, including deleted-items recovery where the platform allows.
4. Block the infrastructure. Block sender domains, URLs, and IPs at email gateway, web proxy, and DNS filtering layers.
5. Handle credential compromise. For users who submitted credentials, force password resets, revoke sessions and tokens, and review their account activity.
6. Check for malware. For users who opened attachments or enabled macros, run EDR scans and investigate for follow-on compromise.
7. Extract and share IOCs. Pull indicators from the campaign for hunting and sharing with the community.
8. Close the loop. Notify affected users, brief their managers if policy requires, and feed lessons into awareness training.

## Expected outputs
- Incident record with campaign scope: recipients, clicks, compromises.
- Containment verification: purged mailboxes, blocked infrastructure, reset credentials.
- IOCs distributed to detection controls.

## Pitfalls
- Purging without scoping first misses recipients and leaves live phish in inboxes.
- Resetting passwords without revoking sessions leaves attackers logged in.
- Treating clicks as harmless; investigate every click for follow-on activity.
- Slow triage lets the campaign spread; automate the initial steps.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- CISA phishing guidance and reporting resources
- MITRE ATT&CK: T1566 (Phishing)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
