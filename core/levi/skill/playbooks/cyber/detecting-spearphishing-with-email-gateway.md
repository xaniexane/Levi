---
skill_id: cyber_detecting_spearphishing_with_email_gateway
name: Detecting Spearphishing with Email Gateway
description: Tune email gateway defenses to catch targeted spearphishing campaigns.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, email-security, detection]
version: 1.0.0
---
## Purpose

Spearphishing — targeted, researched, often low-volume — defeats generic spam filters because each message is crafted to look legitimate. This playbook focuses the email gateway on targeted-phishing signals: sender anomalies, content analysis tuned for lures, and the BEC patterns that cost organizations the most.

## When to use

- Executives or finance staff are being targeted with tailored lures.
- BEC attempts (invoice fraud, executive impersonation) are getting through.
- Gateway phishing detections need tuning for targeted vs. bulk phishing.
- Post-incident: a spearphish succeeded and you need gateway improvements.

## Prerequisites

- Email gateway with advanced threat protection (URL detonation, attachment sandboxing, impersonation detection).
- DMARC/DKIM/SPF deployed (or deployment in progress) with aggregate reporting.
- Executive and VIP list: names, titles, and known external correspondents.
- User-reported phishing feed integrated into gateway/SOC workflow.

## Procedure

1. Harden sender authentication and impersonation detection. Enforce DMARC quarantine/reject, enable gateway display-name and lookalike-domain detection for executives and key vendors, flag external mail using internal executive names, and alert on first-time sender + executive-impersonation combinations. Most BEC needs no malware — impersonation controls are the primary defense.
2. Tune content analysis for targeted lures. Beyond bulk-phishing signatures, detect: urgency + financial-action language (wire instructions, gift cards, invoice changes), conversation hijacking (replies to old threads from spoofed senders), QR codes and image-based lures, and HTML smuggling / unusual attachment types. Weight detections by recipient risk — finance and executive assistants deserve stricter policies.
3. Build the vendor/email-account-compromise use case. Alert on: established vendor senders with sudden behavior changes (new bank details, urgency), reply-chain injections from compromised accounts, and internal-to-internal phishing (a compromised mailbox phishing colleagues — gateway rules that trust 'internal' mail miss this). Verify payment-change requests via out-of-band channels as policy, not just detection.
4. Operationalize user reporting. A well-used report button beats gateway tuning alone: ensure reports reach the SOC in minutes, auto-quarantine identical messages tenant-wide on analyst confirmation, and feed reported samples back into gateway rules. Track report-to-quarantine time as a key metric — targeted campaigns hit few users, so each report matters.
5. Respond to delivered spearphish as potential compromise. For users who clicked/engaged: reset credentials, revoke sessions, check mail rules/forwarding the attacker may have set, review sent-mail for lateral phishing, and hunt for additional targets of the same campaign. A BEC attempt that failed still yields infrastructure to block and TTPs to detect.
6. Measure and improve: track gateway catch rate on reported phish, BEC attempt volume, user report rate, and mean time to tenant-wide quarantine. Run targeted phishing simulations against high-risk groups and feed results into both training and gateway tuning.

## Expected outputs

- Impersonation and sender-auth controls: DMARC enforcement, lookalike-domain, display-name rules.
- Targeted-lure content detections weighted by recipient risk.
- User-report → auto-quarantine workflow with time metrics.
- BEC/vendor-compromise response procedure including out-of-band verification policy.

## Pitfalls

- Gateways that trust internal mail miss compromised-mailbox lateral phishing — inspect internal mail too.
- Display-name impersonation defeats users even with DMARC enforced — gateway UX warnings matter.
- Tuning only for bulk phishing misses low-volume targeted campaigns — separate the use cases.
- Blocking on lure keywords alone creates false positives on legitimate finance mail — combine signals.
- Awareness training without a fast reporting-to-quarantine pipeline wastes the reports.

## References

- NIST SP 800-177 (email security); CISA BEC guidance; MITRE ATT&CK T1566 (Phishing) — https://attack.mitre.org/techniques/T1566/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
