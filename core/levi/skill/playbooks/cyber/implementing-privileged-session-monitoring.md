---
skill_id: cyber_implementing_privileged_session_monitoring
name: Implementing Privileged Session Monitoring
description: Implement privileged session monitoring — proxied/recorded admin sessions, real-time alerting on risky commands, and forensic session review workflows.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, monitoring, detection, forensics]
version: 1.0.0
---
## Purpose

Make privileged sessions observable: every administrative session proxied through a session manager, recorded for forensics, and monitored in real time for risky behavior — so that malicious or mistaken admin actions are detected as they happen, not reconstructed from fragments after the damage. Session monitoring is the detective control that makes privileged access accountable.

## When to use

- Gaining visibility into what administrators and vendors actually do with privileged access.
- Meeting session-recording expectations (PCI DSS 4.0, SOX, ISO 27001 A.8.15 logging).
- Detecting insider misuse or compromised admin sessions in real time.
- Providing forensic evidence for investigations involving privileged actions.
- Complementing PAM vaulting: the vault controls the credential, session monitoring watches its use.

## Prerequisites

- PAM session proxy infrastructure (CyberArk PSM, Delinea, BeyondTrust, Teleport, or SSH bastion with recording) deployed and enforced as the admin access path.
- Defined risky-command/action catalog per platform (e.g., user/permission changes, security tool disabling, mass deletion, firewall changes, database privilege grants).
- SIEM ingestion for session metadata and alert pipeline for real-time detections.
- Legal/HR notice: admin session monitoring policy communicated and acknowledged — monitoring without notice creates legal and trust problems.
- Storage and retention planning: session recordings are large; define retention by risk tier.

## Procedure

1. **Enforce the proxied path.** All interactive privileged sessions (SSH, RDP, database clients, cloud consoles where feasible) must traverse the session manager. Block direct admin protocol access at the network layer for managed targets; any privileged session not through the proxy is a policy violation and a detection in itself.
2. **Record everything, tier the retention.** Capture full session recordings (video/keystroke for RDP/SSH) for Tier 0 and production systems; metadata-only (commands, timing, file transfers) for lower tiers if storage demands it. Encrypt recordings at rest, restrict playback access to investigators with approval workflows — recordings contain credentials and sensitive data.
3. **Build real-time command alerting.** Define per-platform risky patterns: disabling EDR/AV, clearing logs, creating privileged accounts, dumping credential stores (ntdsutil, secretsdump patterns), mass file deletion, firewall rule changes, and database privilege grants. Alert in real time with session context (who, from where, approved ticket?) — the goal is to interrupt, not just to record.
4. **Correlate sessions with approvals.** Join session data with PAM checkout records and change tickets: a privileged session with no corresponding approval or ticket is the highest-priority anomaly. Automate the join — analysts cannot manually correlate thousands of sessions.
5. **Enable live session monitoring for the highest risk.** For Tier 0 sessions and vendor sessions, support live viewing with one-click termination. Define who may terminate (SOC shift lead, with criteria) and the communication protocol — terminating a vendor's session mid-change needs coordination, not just a button.
6. **Protect the monitoring infrastructure.** The session manager and recording store are prime targets (attackers disable recording first). Harden them, alert on recording gaps or manager tampering, and replicate recordings to immutable storage. A gap in recordings during an incident is itself evidence of adversary action.
7. **Define the forensic review workflow.** Document how investigators request, access, and handle session recordings: approval chain, chain-of-custody for exported recordings, redaction of incidental sensitive data, and retention of investigation copies. Test the workflow before the incident.
8. **Review and tune continuously.** Weekly review of risky-command alerts for false positives (tune patterns per team workflow), monthly sampling of recorded sessions for policy compliance, quarterly access review of who can view recordings. Report metrics: proxied-session coverage %, risky-command alert volume and true-positive rate, mean time to review.

## Expected outputs

- Enforced proxied admin access with direct-path blocking.
- Session recording with tiered retention and protected storage.
- Real-time risky-command detections correlated with approvals/tickets.
- Live-monitoring and termination capability for Tier 0/vendor sessions.
- Forensic review workflow; tuning cadence and coverage metrics.

## Pitfalls

- **Recording without enforcement.** Sessions recorded voluntarily while direct access remains possible give you recordings of the honest and nothing of the attacker. Enforce the proxy path.
- **Alerting on everything.** Flagging every `sudo` or config change buries analysts. Tune to genuinely risky actions per platform and per team workflow, or the alerts get ignored.
- **Unprotected recordings.** Session recordings containing typed passwords and sensitive operations, stored with broad access, become a credential-harvesting target. Encrypt, restrict, audit playback.
- **No approval correlation.** Risky-command alerts without ticket/checkout context can't distinguish the planned change from the attack. The join is what makes the alert actionable.
- **Monitoring without notice.** Secretly recording employee admin sessions invites legal challenges and destroys trust. Publish the monitoring policy and get acknowledgment.

## References

- NIST SP 800-53 Rev. 5, AU-2/AU-3 (audit logging), AC-2 (account management) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- NIST SP 800-92, "Guide to Computer Security Log Management" — https://csrc.nist.gov/publications/detail/sp/800-92/final
- MITRE ATT&CK T1078 (Valid Accounts) — privileged session abuse context — https://attack.mitre.org/techniques/T1078/
- PCI DSS v4.0 Requirement 10 (logging and monitoring) — https://www.pcisecuritystandards.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
