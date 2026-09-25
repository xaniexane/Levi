---
skill_id: cyber_deploying_decoy_files_for_ransomware_detection
name: Deploying Decoy Files for Ransomware Detection
description: Plant monitored decoy files across endpoints and shares that trigger instant alerts when ransomware encrypts them.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, deception, detection]
version: 1.0.0
---
## Purpose

Seed files that no legitimate user or process ever modifies — and alert the instant anything touches them. Ransomware encrypts indiscriminately, so well-placed decoy files are among the fastest ransomware tripwires available, often firing before the ransom note appears.

## When to use

- Adding a last-line ransomware detection layer on file servers and high-value endpoints.
- Environments where EDR coverage is partial and you need cheap, high-confidence signals.
- Validating backup and IR readiness with realistic early-warning triggers.
- Post-incident hardening after a ransomware event.

## Prerequisites

- Administrative access to target file shares and endpoints; a file-integrity or EDR capability that can alert on file modification.
- A SIEM/alerting path with a sub-minute SLA for these alerts — speed is the entire value.
- An inventory of critical shares and endpoint types to prioritize placement.
- Written authorization: you're placing files in production file systems.

## Procedure

1. **Choose decoy names ransomware can't resist.** Use names that sort early and look valuable: `aaa_financials_2026.xlsx`, `passwords_backup.docx`, `!_important_readme.txt` in each target directory. Match your organization's real naming conventions — decoys that look out of place are skipped by no one, because ransomware doesn't discriminate, but plausibility matters for targeted variants that prioritize certain paths.
2. **Place decoys at every level that matters.** Drop decoys in: root of critical shares, user home directories, and the folders ransomware hits first (Documents, Desktop, mapped drives). On servers, place them in application data directories and backup staging areas. Cover both Windows (via GPO/logon script or EDR deployment) and the shares themselves.
3. **Make them realistic but inert.** Give decoys plausible sizes, recent timestamps, and real file headers (a valid DOCX/XLSX structure, not a renamed .txt). Content should be synthetic — lorem ipsum or generated financial-looking data — never real sensitive data. Set them read-only for users where possible; ransomware typically removes read-only flags, which is itself detectable.
4. **Instrument with multiple tripwires.** Alert on: file modification or rename (file-integrity monitoring / Sysmon Event ID 11 / EDR file events), mass attribute changes, and — most powerfully — canary-token URLs embedded in the decoy documents that beacon when opened externally. Any single decoy modification is a high-severity alert, not a low one.
5. **Automate the response, not just the alert.** Pre-authorize the playbook: on decoy trigger, automatically isolate the host via EDR, snapshot the alert context (process tree, user, parent process), and page the on-call. The goal is containment within minutes — ransomware encrypts thousands of files per minute, so human-only response is too slow.
6. **Test with safe simulations.** Use a benign script that modifies a decoy file to verify the full chain: modification → alert → auto-isolation → page. Test quarterly and after any EDR/SIEM change. Never test with real ransomware, even in "controlled" conditions.
7. **Maintain and rotate.** Refresh decoy timestamps and content quarterly so they don't look abandoned, verify they haven't been deleted by cleanup scripts or users (monitor decoy existence, not just modification), and expand placement to new shares as they're created.

## Expected outputs

- Plausible, monitored decoy files on critical shares and endpoints with sub-minute alerting.
- An automated containment playbook (isolate + snapshot + page) pre-authorized for decoy triggers.
- Quarterly end-to-end tests with benign modifications; decoy-existence monitoring.

## Pitfalls

- Decoy alerts routed to a low-priority queue — by the time anyone looks, encryption is done.
- Real data in decoy files — a decoy that leaks actual PII is a breach, not a control.
- Cleanup scripts or users deleting the decoys — monitor for disappearance, not just modification.
- Testing with actual ransomware samples — unjustifiable risk; benign modification tests prove the same chain.
- Placing decoys but never automating the response — detection without containment is just a notification of loss.

## References

- CISA ransomware guidance (cisa.gov/stopransomware) — detection and response
- NIST SP 800-61 Rev. 2 — incident handling for malware events
- MITRE ATT&CK T1486 (Data Encrypted for Impact) — ransomware behavior context
- SANS / DFIR community guidance on canary-file deployments
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
