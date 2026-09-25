---
skill_id: cyber_analyzing_email_headers_for_phishing_investigation
name: Analyzing Email Headers for Phishing Investigations
description: Trace phishing email origins: authentication results, received chains, and header anomalies.
risk: low
permissions: []
requires_confirmation: false
tags: [email, threat-intel]
version: 1.0.0
---
# Analyzing Email Headers for Phishing Investigations

## Purpose

Email headers record the path a message took from sender to recipient and the
results of authentication checks (SPF, DKIM, DMARC). This playbook shows how to
read those headers to determine whether a suspicious message is authentic,
spoofed, or relayed through a compromised account — the first triage step in any
phishing investigation.

## When to use

- A user reports a suspicious email (credential harvesting, invoice fraud,
  malicious attachment or link).
- You need to decide whether the sender address is spoofed or the account itself
  is compromised.
- You are building the IOC set (sender IPs, domains, URLs) for a phishing wave.

See also: analyzing-outlook-pst-for-email-forensics.md,
analyzing-malicious-url-with-urlscan.md

## Prerequisites

- Written authorization to handle the reported mailbox content; treat message
  bodies as sensitive and minimize exposure.
- The full original message with intact headers — forwarded inline copies lose
  them. Ask the reporter to forward **as attachment** (Outlook) or use
  "Show original" (Gmail) and save the `.eml`.
- Chain of custody: hash the `.eml` file and record who provided it and when.

## Procedure

1. Obtain the raw message: save the complete original (headers + body) as
   `report-<id>.eml` and record its SHA-256.
2. Read the headers bottom-up: the lowest `Received:` header is closest to the
   true origin. Trace each hop and note IPs, hostnames, and timestamps.
3. Compare envelope vs. display identity:
   - `Return-Path` / `From` / `Reply-To` — do they agree, or does `Reply-To`
     point somewhere the `From` does not?
   - `Message-ID` domain — a Gmail-sent message has a `mail.gmail.com`-style ID;
     a mismatch with the claimed sender is a red flag.
4. Check `Authentication-Results` for SPF, DKIM, and DMARC verdicts:
   `dkim=pass/fail`, `spf=pass/fail`, `dmarc=pass/fail`, and the `header.from`
   domain each result was evaluated against. `compauth`/`auth=pass` alone is
   not enough — verify alignment with the visible From domain.
5. Look at `X-Originating-IP`, `X-Sender-IP`, or similar MTA-added headers for
   the true client IP, then check it against blocklists and your SIEM.
6. Inspect routing anomalies: multiple `Received` hops in unrelated countries
   within seconds, timestamps out of order, or a first hop from a residential
   ISP / VPN exit rather than the claimed organization's mail server.
7. Decode and inspect MIME structure: boundary parts, `Content-Type` mismatches
   (e.g., an "invoice.pdf" part that is actually `application/octet-stream`),
   and double extensions in `Content-Disposition: attachment` filenames.
8. Extract URLs from the body and HTML parts; compare displayed link text with
   the actual `href` target. Note URL shorteners, punycode (xn--) domains, and
   lookalike domains.
9. Extract attachment hashes (SHA-256) and submit to your sandbox or
   VirusTotal — do not open the attachment on an analyst workstation.
10. Correlate: search the mail gateway / SIEM for the sender IP, Message-ID
    pattern, and subject to find other recipients; record all IOCs.

## Key tools & commands

- Python `email` library for scripted parsing:
  `python3 -c "import email; m=email.message_from_file(open('r.eml')); print(m['Authentication-Results'])"`
- `openssl` / `dig` for manual verification: `dig TXT <domain>` (SPF),
  `dig TXT <selector>._domainkey.<domain>` (DKIM).
- Google Admin Toolbox "Messageheader" analyzer (paste raw headers).
- MXToolbox header analyzer (mxtoolbox.com/EmailHeaders.aspx).
- `urlscan.io` for safe detonation of extracted URLs.
- SIEM / mail gateway search for recipient blast-radius enumeration.

## Expected outputs

- Verdict: spoofed / compromised-account / legitimate-but-suspicious, with the
  header evidence cited for each claim.
- An IOC list: sender IPs, envelope domains, URLs, attachment hashes.
- Blast-radius list: other recipients of the same campaign.
- A containment note: block sender/domain at gateway, force password reset if a
  real account was abused, submit IOCs to threat intel.

## Pitfalls

- Headers can be forged by the sender — only trust headers added by **your**
  infrastructure (the topmost `Received` and `Authentication-Results` stamped
  by your gateway).
- A `spf=pass` on a lookalike domain still means phishing; authentication
  proves the domain owner sent it, not that the domain is trustworthy.
- Forwarded-as-inline copies and screenshots destroy headers; always re-request
  the original if they are missing.
- DKIM `fail` can be caused by legitimate mailing-list rewriting — correlate
  with DMARC policy and sending history before concluding spoofing.
- Timezone-naive reading of `Received` timestamps creates false "impossible
  travel" conclusions; convert to UTC first.

## References

- RFC 5322 (Internet Message Format), RFC 7208 (SPF), RFC 6376 (DKIM),
  RFC 7489 (DMARC)
- MITRE ATT&CK: T1566 (Phishing), T1134-adjacent display-name deception
- Google / Microsoft documentation on reading message headers in Gmail/Outlook

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
