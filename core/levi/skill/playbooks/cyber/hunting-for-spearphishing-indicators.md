---
skill_id: cyber_hunting_for_spearphishing_indicators
name: Hunting for Spearphishing Indicators
description: Hunt spearphishing campaigns across email telemetry: malicious attachments, URLs, sender anomalies, and targeted lures.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, phishing, email]
version: 1.0.0
---
## Purpose

Spearphishing — targeted phishing with researched lures — is the dominant
initial-access vector. This playbook covers hunting for spearphishing
indicators across email telemetry: malicious attachments and URLs, sender
spoofing and lookalike domains, and the targeting patterns that
distinguish spearphishing from commodity spam.

## When to use

- After a user reports a suspicious email: hunt for other recipients
  of the same campaign.
- Proactive hunting for phishing that evaded email gateways.
- Investigating initial access in an intrusion (find the phish that
  started it).
- Measuring email-security control effectiveness.

## Prerequisites

- Email telemetry: gateway logs, message metadata (headers, envelope),
  attachment hashes, and URL rewrite/click logs.
- Threat intel on phishing infrastructure and TTPs.
- User-reporting pipeline (phish-alert button) — reports seed hunts.
- Sandbox detonation capability for suspicious attachments/URLs.

## Procedure

1. **Start from the seed.** A user report, a gateway alert, or an
   incident's initial-access hypothesis gives you the first sample.
   Extract: sender address and infrastructure, subject patterns,
   attachment hashes, URLs, and lure theme.
2. **Hunt by infrastructure.** Search email logs for other messages from
   the same sending IPs/domains, lookalike domains of your
   organization, and newly registered domains mimicking executives or
   partners. Check SPF/DKIM/DMARC results — failures on supposed
   internal senders are strong signals.
3. **Hunt by payload.** Sweep for the attachment hashes (and fuzzy
   variants) and URLs across all mailboxes, including delivered mail
   that predates gateway rule updates. Check URL-click logs for who
   already clicked.
4. **Hunt by lure and targeting.** Spearphishing is targeted: look for
   recipient patterns (finance staff, executives, IT admins), lure
   themes tied to current events or internal projects (indicating
   reconnaissance), and timing (sent to catch recipients off-guard).
5. **Analyze headers deeply.** Examine Received chains for
   inconsistencies, compare envelope-from with header-from, check for
   display-name spoofing of executives, and look for reply-to
   redirection to attacker-controlled addresses.
6. **Detonate safely.** Submit attachments and URLs to the sandbox;
   extract IOCs (C2, credential-harvesting domains, macro behaviors)
   and feed them into the campaign hunt and blocklists.
7. **Scope the impact.** Identify all recipients, who opened/clicked/
   submitted credentials, and what followed (malware execution,
   credential use). Credential-submission victims need immediate
   password resets and session revocation.
8. **Respond and improve.** Remove malicious messages from mailboxes
   (mailbox-wide purge where supported), block infrastructure,
   notify and train targeted users, and tune gateway rules from the
   campaign's evasion techniques.

## Expected outputs

- Campaign characterization: infrastructure, lures, targeting, and
  timeline.
- Full recipient list with interaction dispositions
  (delivered/opened/clicked/submitted).
- Extracted IOCs with blocks deployed.
- Victim remediation records (resets, revocations).
- Gateway-tuning improvements from evasion analysis.

## Pitfalls

- Stopping at the reported mailbox — spearphishing is a campaign;
   always hunt for other recipients.
- URL rewriting by the gateway changes the clicked URL — correlate
   with the original malicious URL, not just the rewritten form.
- Attachment hash-only hunting misses polymorphic variants — pair
   with infrastructure and lure hunting.
- Delayed detonation: time-bombed payloads look benign in the
   sandbox — allow sufficient detonation time and check for
   environment checks.
- Blaming the clicker — focus on control improvement, not user
   punishment; reporting culture depends on it.

## References

- MITRE ATT&CK: T1566 (Phishing) sub-techniques
- CISA: phishing guidance and #StopRansomware phishing advisories
- NIST SP 800-177: Trustworthy Email (SPF/DKIM/DMARC)
- Email gateway vendor documentation for hunt-query syntax
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
