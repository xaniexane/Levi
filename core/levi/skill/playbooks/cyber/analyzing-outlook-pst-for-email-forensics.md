---
skill_id: cyber_analyzing_outlook_pst_for_email_forensics
name: Analyzing Outlook PST Files for Email Forensics
description: Extract email evidence from PST files: messages, attachments, and metadata.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, email]
version: 1.0.0
---
# Analyzing Outlook PST Files for Email Forensics

## Purpose

Extract and analyze mailbox content from Outlook PST/OST files — messages, attachments, deleted items, and metadata — to support phishing investigations, data-loss cases, and internal inquiries.

## When to use

- A user's mailbox is relevant to an incident (phishing victim, suspected insider) and you hold a PST export or OST copy.
- Reconstructing what a phishing email contained and who else received it.
- Recovering deleted messages that still reside in the PST's unallocated areas.

## Prerequisites

- Written authorization; privacy/legal review for mailbox content access — email is sensitive even in corporate investigations.
- Chain-of-custody: hash the PST at acquisition; work on a forensic copy.
- Tools: `pffexport`/`libpff` (CLI), or a forensic suite; Python with `libpff` bindings for scripting.
- Do not open the PST in Outlook on a networked host — preview can trigger remote content loads and read receipts.

## Procedure

1. Hash the PST/OST at acquisition and record size, source mailbox, and export method.
2. Verify structural integrity: `pffinfo evidence.pst` — note folder hierarchy, message counts, and any encryption flags.
3. Export the full folder tree to a working directory:
   `pffexport -m all evidence.pst`
   This yields messages (with headers), attachments, and calendar items in a browsable layout.
4. Reconstruct the phishing email: locate it by subject/sender/date, then read the full RFC 5322 headers from the exported message — never trust the displayed From: line.
5. Analyze headers per the email-header playbook: Received chain, SPF/DKIM/DMARC results, Return-Path vs. From vs. Reply-To mismatches, and originating IP.
6. Extract attachments: hash each (SHA-256), submit to the malware lab, and record filenames, sizes, and MIME types. Check for double extensions and mismatched magic bytes.
7. Extract URLs from the message body (including HTML href vs. display-text mismatches) and expand shortened links in the isolated lab only.
8. Search the mailbox for related messages: same sender domain, same subject patterns, or the same attachment hash — scope who else was targeted.
9. Check Deleted Items and recoverable space: `pffexport` recovers deleted items still present; compare message counts against the mailbox's reported totals to spot wiped items.
10. Review calendar items and contacts for social-engineering context (meeting invites used as lures).
11. Check for embedded OLE objects and macros in attachments: Office documents inside the PST get the same static triage as email attachments — hash and lab-review before any open.
12. Review Sent Items and Drafts for attacker activity: in a compromised mailbox, look for phishing lures or exfiltration emails the legitimate user didn't write.
13. Verify message integrity: compare the PST's per-folder message counts against server-side counts to detect selective deletion.
14. Extract message rules stored in the PST: client-side rules that auto-forward or delete mail are an attacker persistence mechanism inside the mailbox.
15. Check for hidden attachments: embedded images and OLE objects that never render in the body can still carry payloads — enumerate all attachment parts, not just visible ones.
16. Correlate attachment hashes with the email-header investigation to link the lure to its delivery infrastructure.
17. Carve unallocated PST space for wiped messages: deleted items often remain recoverable with forensic tools.
18. Check the RSS Feeds folder — it has been abused to hide auto-forwarded content.
19. Review contacts for attacker-added entries: new external contacts support follow-on social engineering.
20. Compare per-folder counts before and after export to catch items the export skipped.
21. Build a timeline: received timestamps vs. user open/reply actions (read flags) to determine whether the payload was triggered.
22. Preserve exports with hashes; document every search term used so the review is reproducible and defensible.

## Key tools & commands

- `pffinfo evidence.pst` — PST metadata and folder overview.
- `pffexport -m all evidence.pst` — full export of messages, attachments, calendar.
- `pffexport -m <mode>` modes: `all`, `item`, etc. — targeted exports.
- Python `libpff` — scripted parsing for bulk mailbox triage.
- `sha256sum` on every extracted attachment.
- `readpst -o out evidence.pst` — convert PST to mbox/maildir for text processing.
- `oledump.py` — triage of OLE-based attachments extracted from messages.
- `grep -r` over exported mbox — bulk keyword search across the mailbox.
- Forensic suites (Autopsy, X-Ways) — GUI review with deleted-item recovery.

## Expected outputs

- Hashed PST with acquisition record.
- Full export tree with message/header inventory.
- Phishing email reconstruction: headers, URLs, attachments with hashes and lab verdicts.
- Scope list: other recipients of the same lure.
- Sent/Draft anomaly list (attacker-written messages).
- Message-count integrity check: PST vs. server-side counts.
- Deleted-item recovery notes and open/reply timeline.

## Pitfalls

- Opening the PST in Outlook: triggers web beacons, read receipts, and add-in execution.
- Trusting displayed sender names; always read raw headers.
- Missing URL obfuscation in HTML bodies — compare href against anchor text.
- Overlooking calendar invites as attack vectors.
- Accessing mailbox content without documented authorization — a privacy and legal risk.
- OST files may hold unsynced items the server copy lacks — check both when available.
- Password-protected PSTs — document how access was obtained for the case record.
- Confusing internal client timestamps with actual delivery timestamps.
- `pffexport` silently skipping corrupt items — compare exported counts against `pffinfo`.
- Timezone-naive analysis of internal timestamps — normalize before timeline building.
- Missing embedded message/rfc822 attachments — they're separate messages; triage them too.
- Assuming the PST is complete — compare against server-side retention and journaling.
- Forensic-suite preview panes fetching remote content — disable network first.
- Exporting with the wrong codepage — garbled non-ASCII subjects.
- Forgetting the Sync Issues folder — it reveals mailbox sync anomalies.
- Not recording the PST format (ANSI vs. Unicode) — affects parsing.
- Overlooking embedded voting buttons — they can carry tracking URLs.
- Assuming folder names are in English — localized Outlook uses localized names.
- Skipping transport-header analysis for internal relays — spoofing happens inside too.
- Opening the original PST in Outlook mutates metadata — work on a hashed copy.
- Deleted items are recoverable only until compaction — image quickly.
- MAPI property timezones need careful conversion for timelines.
- Embedded attachments can nest — recurse fully through each layer.
- S/MIME-encrypted messages are unreadable without the key — document the gap.
- Large PSTs corrupting mid-parse — validate parser counts against item totals.

See also: analyzing-email-headers-for-phishing-investigation.md

## References

- libpff / pffexport documentation: https://github.com/libyal/libpff
- Microsoft — PST file format documentation (MS-PST)
- MITRE ATT&CK T1566 (Phishing), T1114.002 (Remote Email Collection)
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
