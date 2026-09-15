---
skill_id: cyber_attacking_entra_id_with_roadtools
name: Detecting Entra ID Attacks Using Roadtools Techniques
description: Detect Roadtools-style Entra ID tradecraft: token abuse and PRT signals.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud]
version: 1.0.0
---
# Detecting Entra ID Attacks Using Roadtools Techniques

## Purpose

Detect, in a defensive capacity, the attacker tradecraft commonly associated with the
Roadtools toolkit family against Microsoft Entra ID (formerly Azure AD): token theft and
replay, PRT (Primary Refresh Token) abuse, malicious OAuth consent, and reconnaissance of
users, groups, and conditional access policies. This playbook tells defenders what to hunt
for and how to harden — it does not document offensive use of any tool.

## When to use

- During threat hunting after suspected Entra ID compromise or token theft.
- When building detections for credential-access and lateral-movement activity in
  Microsoft 365 / Entra ID.
- After an incident involving a stolen refresh token, PRT, or suspicious OAuth consent.
- When hardening Entra ID against token-replay and device-identity abuse.
- As a detection-engineering reference when new token-theft tradecraft is reported.

See also: auditing-entra-id-with-aadinternals.md

## Prerequisites

- Written authorization and a defined scope if this is an assessment; internal SOC hunts
  operate under existing monitoring authority.
- Microsoft Entra diagnostic settings exporting `SignInLogs`, `AuditLogs`, and
  `NonInteractiveUserSignInLogs` to the SIEM — token replay is largely invisible without
  non-interactive sign-ins.
- Familiarity with Entra ID authentication flows: PRT issuance and use, refresh tokens,
  device compliance states, and conditional access evaluation.
- A baseline of normal sign-in patterns (locations, devices, applications, ASNs) for the
  tenant, ideally 30+ days.

## Procedure

1. **Establish the data sources.**
   - Confirm Entra ID diagnostic settings export `SignInLogs`, `AuditLogs`, and
     `NonInteractiveUserSignInLogs` to the SIEM with no gaps.
   - Validate with an event count per category over the last 24 hours before hunting.

2. **Hunt for token replay anomalies.**
   - Query sign-in logs for the same `userPrincipalName` authenticating from
     geographically impossible locations in a short window.
   - Flag sudden changes in ASN, device ID, or OS for an established session; correlate on
     `ipAddress`, `deviceDetail.deviceId`, and `appId`.

3. **Look for PRT anomalies.**
   - PRT-based sign-ins carry distinctive authentication details — hunt for sign-ins where
     the device identity changes mid-session.
   - Flag a PRT used from a device never previously seen for that user, or device-based
     auth originating from unmanaged devices.

4. **Detect refresh-token theft and reuse.**
   - Alert on repeated invalid/expired refresh-token errors (`50126`, `700082` families).
   - Flag a token used from a new IP immediately after legitimate use from the original
     IP, and concurrent sessions for one user from divergent locations.

5. **Build the KQL starting point.**
   - In Sentinel, start from `SigninLogs` and `AADNonInteractiveUserSignInLogs`: filter
     `ResultType != 0`, summarize distinct IPs, locations, and device IDs per user per
     hour.
   - Flag users with high distinct-IP counts or impossible-travel pairs; tune thresholds
     against the baseline from the prerequisites.

6. **Review OAuth consent grants.**
   - In audit logs, look for `Consent to application` events granting broad scopes
     (`Mail.ReadWrite`, `Files.ReadWrite.All`, `Directory.ReadWrite.All`), especially to
     newly registered, unverified, or multi-tenant apps.
   - Cross-check app registrations for recently added redirect URIs, new client secrets,
     or changed publisher domains.

7. **Hunt for reconnaissance patterns.**
   - Toolkit-driven recon appears as bursts of Microsoft Graph reads: user/group
     enumeration, conditional access policy reads, and role-assignment enumeration from a
     single principal in a short window.
   - Baseline normal Graph activity per service principal first to avoid noise.

8. **Check for device identity manipulation.**
   - Review registered devices for entries with no Intune enrollment, duplicate device
     names, recently created devices that immediately show PRT activity, or stale devices
     suddenly active again.
   - PRT abuse typically needs a device identity to anchor to — unexpected device
     registrations are a leading indicator.

9. **Correlate with endpoint telemetry.**
   - Join suspicious sign-ins with Defender for Endpoint / EDR data: look for
     credential-dumping behavior, LSASS access, or browser cookie/token theft on the
     source device in the same timeframe.
   - Token theft starts on an endpoint — the sign-in anomaly is the second half of the
     story.

10. **Contain on confirmation.**
    - Revoke all refresh tokens for the user (Entra admin center → Revoke sessions, or
      Graph `POST /users/{id}/revokeSignInSessions`).
    - Disable compromised accounts and malicious app registrations, rotate secrets on
      affected apps, and delete illicit consent grants.

11. **Harden after the hunt.**
    - Enforce phishing-resistant MFA and require compliant or hybrid-joined devices via
      conditional access.
    - Block legacy authentication, enable continuous access evaluation, restrict user app
      consent to admins, and apply token protection / session controls where licensed.

## Key tools & commands

- Microsoft Entra admin center → Monitoring → Sign-in logs / Audit logs: the primary
  hunting surface; export via diagnostic settings for SIEM analysis.
- Microsoft Sentinel with the Entra ID data connector: KQL hunting across `SigninLogs`,
  `AADNonInteractiveUserSignInLogs`, and `AuditLogs`.
- Microsoft Graph: `GET /auditLogs/signIns` and `/auditLogs/directoryAudits` for scripted
  log retrieval and offline analysis.
- Defender for Identity / Defender for Cloud Apps: session anomaly, impossible-travel, and
  anomaly alerts that corroborate token abuse.
- Defensive knowledge of toolkit artifacts (device registration events, token-use patterns
  in logs) used solely to write better detections — never to operate tooling offensively.

## Expected outputs

- Hunting queries (KQL) for token replay, PRT anomalies, consent-grant abuse, and Graph
  recon bursts, with tuning notes.
- Timeline of suspicious authentication events per affected identity, correlated with
  endpoint telemetry.
- Containment actions taken (sessions revoked, accounts disabled, apps removed, grants
  deleted).
- Hardening recommendations mapped to conditional access, app governance, and session
  controls.

## Pitfalls

- Missing non-interactive sign-in logs — token replay often never produces an interactive
  sign-in, so the attack is invisible without them.
- Treating every impossible-travel alert as a true positive; VPNs, mobile carriers, and
  legitimate travel cause noise. Corroborate with device and app signals.
- Revoking sessions without removing malicious app consent grants — the attacker
  re-authenticates through the consented app within minutes.
- Focusing only on user accounts: service principals and app registrations are equally
  abused for persistence and are harder to notice.
- Stale baselines: sign-in patterns drift as the workforce changes; re-baseline quarterly
  or the detections decay.

## References

- MITRE ATT&CK: T1550 (Use Alternate Authentication Material), T1550.001 (Application
  Access Token), T1528 (Steal Application Access Token), T1078 (Valid Accounts).
- Microsoft Learn: "What is Conditional Access", "Continuous access evaluation in
  Microsoft Entra ID", "Detect and remediate illicit consent grants".
- Microsoft Learn: Entra ID sign-in log schema, authentication details, and error code
  reference.
- CISA guidance on Microsoft 365 / Entra ID hardening and token-theft response.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
