---
skill_id: cyber_detecting_email_account_compromise
name: Detecting Email Account Compromise
description: Detect compromised mailboxes with logon-anomaly, rule-creation, and mail-flow monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [email, identity, detection]
version: 1.0.0
---
## Purpose

Detect compromised email accounts — the foothold behind BEC, internal phishing, and data theft — through the signals compromise creates: anomalous logons, malicious inbox rules, and abnormal mail flow. Mailbox compromise is often the first detectable stage of a larger intrusion.

## When to use

- Building email-threat detection for Exchange Online / Google Workspace.
- Investigating suspected mailbox takeover (user reports, phishing from internal accounts).
- Hunting for dormant compromises (attackers read mail for weeks before acting).
- Validating that mailbox audit logging captures what the SOC needs.

## Prerequisites

- Mailbox audit logging enabled (unified audit log) with SIEM/Log Analytics access.
- Baseline of normal mailbox access: locations, devices, protocols per user.
- Alerting path with account-disable and session-revocation authority.
- User communication channel for verification (is this travel or compromise?).

## Procedure

1. **Verify audit logging is complete.** Confirm unified audit logging is enabled tenant-wide and that mailbox actions (logons, rule creation, mail access) are recorded. Test with a controlled action and verify it appears in the logs within the expected latency. Gaps here blind every detection below.
2. **Detect anomalous mailbox access.** Alert on: logons from new geographies or ASNs, impossible-travel between mailbox accesses, new devices or protocols (a user who only uses Outlook suddenly on IMAP/POP — legacy protocols are attacker favorites), and access at unusual hours. Correlate with the identity signals — the mailbox anomaly plus an Entra risky sign-in is high confidence.
3. **Detect malicious inbox rules.** Alert on any rule that: forwards or redirects to external addresses, deletes or moves incoming mail (hiding the attacker's activity), or marks mail as read automatically. These rules are the attacker's invisibility cloak — their creation is often the most detectable action in the whole compromise.
4. **Monitor mail-flow anomalies.** Alert on: send-volume spikes from a mailbox (internal phishing campaigns), sends to unusual external recipient sets, auto-forwarding configuration changes, and delegate/permission grants on the mailbox (attackers grant themselves persistent access). Compare against the user's normal sending patterns.
5. **Detect OAuth and app-based persistence.** Alert on: new OAuth grants to mail-reading applications, app passwords created (bypass MFA), and Exchange Web Services / API access from new clients. Attackers increasingly persist via API rather than interactive logon — the mailbox stays compromised after the password changes.
6. **Hunt for dormant and historical compromise.** Periodically review: mailboxes with rules created by non-owners, mailboxes accessed via legacy protocols, and accounts with logon anomalies that were never investigated. Attackers dwell in mailboxes for weeks reading for intelligence — historical hunts catch what real-time alerting missed.
7. **Respond with full session kill.** On confirmation: revoke all sessions and tokens (password reset alone leaves API sessions alive), remove malicious rules and delegates, revoke OAuth grants and app passwords, reset the password, enforce MFA re-registration if MFA was tampered with, and scope: what mail was read, what was sent, were other accounts phished from this mailbox? Each answer expands the incident.

## Expected outputs

- Complete mailbox audit logging with anomaly detections for access, rules, mail flow, and OAuth persistence.
- Periodic dormant-compromise hunts catching what real-time alerting missed.
- Full session-kill response runbooks with mail-read/send scoping.

## Pitfalls

- Audit logging disabled or partial — the most common gap; verify, don't assume.
- Password reset without session/token revocation — the attacker's API session survives.
- Ignoring delegate grants — the attacker keeps access through delegation after the password changes.
- No baseline per user — global thresholds miss the quiet compromise of a low-volume user.
- Treating the mailbox as the whole incident — check what the attacker learned and where they went next.

## References

- Microsoft Learn — Exchange Online mailbox auditing and alert policies
- MITRE ATT&CK T1137 (Office Application Startup) and T1114 (Email Collection)
- CISA guidance on email account compromise response
- NIST SP 800-177 (Trustworthy Email)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
