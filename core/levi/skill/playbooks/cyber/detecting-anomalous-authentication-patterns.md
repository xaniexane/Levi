---
skill_id: cyber_detecting_anomalous_authentication_patterns
name: Detecting Anomalous Authentication Patterns
description: Detect credential abuse with behavioral authentication analytics: impossible travel, spraying, and session anomalies.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, detection, authentication]
version: 1.0.0
---
## Purpose

Catch authentication abuse that valid credentials hide: logins from impossible locations, password spraying, token replay, and session anomalies — the signals that distinguish the legitimate user from the attacker holding their password.

## When to use

- Building identity-threat detection on IdP logs (Entra ID, Okta, AD).
- Investigating suspected account compromise or credential-stuffing campaigns.
- Tuning UEBA or identity-protection alerts that are too noisy or too quiet.
- Post-breach hunting for additional compromised accounts.

## Prerequisites

- Centralized authentication logs: IdP sign-in logs, AD security events (4624/4625/4768/4769), VPN logs.
- Baseline knowledge of normal patterns: user geographies, working hours, typical devices.
- A user inventory with roles and risk tiers (executives, admins, service accounts get tighter thresholds).
- Alerting path to the SOC with defined severity tiers.

## Procedure

1. **Detect impossible travel.** Alert when the same identity authenticates from two geographies faster than physically possible. Tune the velocity threshold per user population (executives traveling legitimately need wider windows than office staff), and exclude known VPN exit-node artifacts. Correlate with device: same device + impossible travel often means VPN, not compromise.
2. **Detect password spraying and brute force.** Alert on: many failed logons (4625) across many accounts from one source (spraying — low-and-slow, so use 24h windows), and many failures against one account (brute force). Distinguish service-account lockouts (often misconfigured apps) from user-targeted spraying by pattern.
3. **Detect anomalous logon characteristics.** Flag: first-time device or browser for a user, logons at unusual hours for the role, new MFA methods registered, MFA fatigue patterns (repeated push approvals), and logon types that don't match the user's norm (e.g. a user who only uses SSO suddenly authenticating via legacy protocols).
4. **Detect token and session anomalies.** Alert on: refresh-token reuse, tokens used from a different geography than issuance, concurrent sessions from distant locations, and session-cookie anomalies. In Entra ID, monitor risky sign-ins and unfamiliar sign-in properties — but validate them against your own data before trusting the risk score blindly.
5. **Hunt service-account abuse.** Service accounts have the most predictable patterns and the broadest access — the worst combination. Alert on: service accounts logging on interactively, service accounts authenticating from new hosts, and any human-pattern activity (web browsing, email) from a service identity. Maintain an allowlisted behavior profile per service account.
6. **Correlate authentication with post-auth activity.** A suspicious logon followed by mailbox rule creation, OAuth consent grants, or mass file downloads is a compromise; the same logon with normal activity may be travel. Build compound detections: anomaly + high-risk post-auth action = high-severity incident.
7. **Tune with feedback, not just thresholds.** Review every authentication alert's outcome weekly: true positive, benign (travel, new device), or misconfigured (service account). Feed benign patterns back as exclusions with expiry dates, and tighten thresholds where true positives were missed. Authentication detection is a living model, not a configured rule.

## Expected outputs

- Detections for impossible travel, spraying/brute force, logon anomalies, and token/session abuse.
- Service-account behavior profiles with deviation alerting.
- Compound detections (anomaly + risky post-auth action) and weekly tuning feedback.

## Pitfalls

- Impossible-travel alerts without VPN awareness — you'll drown in false positives.
- Treating IdP risk scores as ground truth — validate against your own telemetry first.
- Ignoring service accounts — they're the highest-value, least-monitored identities.
- Static thresholds for a global workforce — travel patterns vary by role and region.
- Alerting on the anomaly but not the follow-on — the logon is the start of the story, not the end.

## References

- Microsoft Learn — Entra ID sign-in logs, risky sign-ins, and identity protection
- NIST SP 800-63B (Authentication and Lifecycle Management)
- MITRE ATT&CK T1078 (Valid Accounts) and T1110 (Brute Force)
- CISA guidance on phishing-resistant MFA and authentication monitoring
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
