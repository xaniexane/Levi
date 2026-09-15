---
skill_id: cyber_implementing_soar_playbook_for_phishing
name: Implementing a SOAR Playbook for Phishing Response
description: Automate the phishing triage pipeline from user report to containment and lessons learned.
risk: low
permissions: []
requires_confirmation: false
tags: [soar, phishing, incident-response]
version: 1.0.0
---
## Purpose
This playbook defines a SOAR-driven workflow for reported phishing emails: automated analysis, verdict, containment of the campaign, and victim follow-up. It is platform-agnostic (Splunk SOAR, Cortex XSOAR, Tines, or similar).

## When to use
- Phishing reports overwhelm manual triage capacity.
- You need consistent verdicts and SLAs across every reported message.
- Post-incident reviews show slow removal of malicious messages from mailboxes.

## Prerequisites
- A user-facing report-phishing mechanism (button or mailbox) feeding the SOAR platform.
- Mail gateway / mail platform API access for message search, purge, and block actions.
- Sandbox detonation capability and threat-intel enrichment sources.

## Procedure
1. **Ingest and normalize.** Convert each user report into a case with the raw message, headers, URLs, and attachments preserved as artifacts.
2. **Automate static analysis.** Extract authentication results (SPF/DKIM/DMARC), sender reputation, URL lexical features, and attachment hashes; enrich against threat intelligence.
3. **Detonate safely.** Submit URLs and attachments to a sandbox; record the verdict and behavioral indicators back into the case.
4. **Score and branch.** Apply a verdict model: benign (auto-close with user feedback), suspicious (analyst review), malicious (auto-contain).
5. **Contain the campaign.** On a malicious verdict: purge matching messages tenant-wide, block sender domains and URLs at the gateway, and quarantine attachments.
6. **Identify victims.** Search mail logs for recipients who received or clicked before containment; open follow-up tasks for credential resets and endpoint checks.
7. **Close the loop.** Notify the reporter of the outcome, update detection rules (e.g., new blocklist entries, SIEM detections for the IOCs), and record metrics.

## Expected outputs
- End-to-end phishing playbook with verdict branching and approval gates.
- Metrics: report-to-verdict time, report-to-purge time, victim identification coverage.
- Feedback loop into email security controls and user awareness training.

## Pitfalls
- Auto-purging without a tested verdict model risks deleting legitimate business email.
- Ignoring the reporter: if users never hear outcomes, reporting rates collapse.
- Forgetting mobile and third-party mail paths when purging; verify tenant-wide coverage.

## References
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- CISA Phishing Guidance (cisa.gov) — reporting and mitigation practices.
