---
skill_id: cyber_detecting_email_forwarding_rules_attack
name: Detecting Email Forwarding Rules Attack
description: Detect malicious inbox forwarding and transport-rule abuse used to hide compromise and exfiltrate mail.
risk: info
permissions: []
requires_confirmation: false
tags: [email, detection, persistence]
version: 1.0.0
---
## Purpose

Detect the forwarding-rule attacks that make mailbox compromise invisible and exfiltrate mail silently: client-side inbox rules forwarding to external addresses, and server-side transport rules attackers create with elevated access. The rule is the persistence; detecting it breaks the attacker's cover.

## When to use

- Hunting for hidden mailbox compromise (the rules attackers use to stay invisible).
- Building email-persistence detection for the SOC.
- Investigating a compromise where the attacker may have established mail collection.
- Auditing transport rules for attacker-created exfiltration paths.

## Prerequisites

- Mailbox audit logging (rule creation/deletion events) and Exchange admin audit logging (transport rule changes).
- Baseline of legitimate forwarding: which users legitimately auto-forward, to where.
- Authority to remove malicious rules and disable forwarding on confirmation.
- Alerting path with high priority — forwarding-rule creation is a top-tier signal.

## Procedure

1. **Alert on every new inbox forwarding rule.** Any rule that forwards, redirects, or sends-to-external is a high-severity alert until triaged. Include in the alert: rule name, creator, creation time, destination address, and conditions. Attackers name rules innocuously (".", "archive") — the destination and conditions matter, not the name.
2. **Distinguish legitimate from malicious forwarding.** Maintain an allowlist of approved forwarding (documented business need, approved destination). Everything else gets investigated. Key discriminators: forwarding to external/free-webmail addresses (rarely legitimate), rules created at unusual hours, rules created shortly after a password reset or logon anomaly, and rules with delete-after-forward actions (hiding the evidence).
3. **Detect rule-tampering and hiding techniques.** Alert on: rules modified to add forwarding to existing legitimate rules, rules created then the audit log entry deleted (where possible), and multiple rules created in sequence (attackers create backups). Also monitor for rules that mark forwarded mail as read — the stealth variant.
4. **Audit transport rules for attacker abuse.** With elevated access, attackers create organization-wide transport rules (redirecting mail, BCC'ing external addresses, bypassing DLP). Alert on: new transport rules, modifications to existing rules, rules with external recipients, and rules that exempt senders from filtering. Review the full transport-rule set quarterly — attacker rules hide among legitimate ones.
5. **Correlate with the compromise timeline.** Join rule creation with: the creating account's logon history (was it anomalous?), recent password changes, and MFA events. A forwarding rule created two hours after an impossible-travel logon is the compromise confirmation. The rule tells you when the attacker arrived; the logons tell you how.
6. **Hunt historically.** Periodically scan all mailboxes for: forwarding rules to external addresses, rules created by someone other than the mailbox owner, and disabled-but-present suspicious rules (attackers sometimes disable rather than delete). Scan transport rules for external recipients and overly broad conditions. Historical hunts catch the compromises that predated your alerting.
7. **Respond by removing and scoping.** On confirmation: delete the malicious rules (document them first — screenshots and exports for forensics), disable external auto-forwarding tenant-wide if policy allows, revoke the attacker's access (session kill, password reset, MFA review), and scope: what mail was forwarded, for how long, to where? The forwarded mail defines the data-breach scope.

## Expected outputs

- High-severity alerting on all new external-forwarding rules with full rule context.
- Transport-rule change monitoring and quarterly full-set reviews.
- Historical forwarding hunts and a remove-and-scope response procedure.

## Pitfalls

- Alerting without an allowlist — legitimate forwarding drowns the signal; document and allowlist it.
- Only monitoring inbox rules — transport rules are the higher-privilege, harder-to-spot variant.
- Deleting the rule before documenting it — you destroy the forensic evidence of the attacker's methods.
- Allowing external auto-forwarding by default — the policy decision that makes this attack trivial; restrict it.
- Treating rule removal as incident closure — scope what was forwarded first.

## References

- Microsoft Learn — mail flow rules (transport rules) and inbox rule auditing
- MITRE ATT&CK T1137 (Office Application Startup) / T1205 (Traffic Signaling) in email-persistence context
- CISA guidance on email security and forwarding-rule abuse
- FBI IC3 — BEC reports highlighting forwarding-rule persistence
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
