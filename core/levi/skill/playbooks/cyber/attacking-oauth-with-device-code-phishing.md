# Detecting OAuth Device Code Phishing

## Purpose

Detect and respond to device code phishing against OAuth/OIDC identity providers
(Microsoft Entra ID, Google Workspace, Okta, GitHub). In this technique the victim is
tricked into completing a legitimate device authorization flow on the attacker's behalf;
the defender's job is to spot the resulting anomalous authorizations, tokens, and
sessions, and to harden the flow.

## When to use

- After a user reports a suspicious "enter this code at microsoft.com/devicelogin" (or
  equivalent) prompt.
- When hunting for OAuth-based initial access in Entra ID, Google, or Okta logs.
- When reviewing whether device code flow should remain enabled in the tenant.
- As part of phishing-response runbooks involving MFA-fatigue or consent-style lures.
- When a new client application suddenly appears in device-flow telemetry.

## Prerequisites

- Written authorization and defined scope for assessments; internal SOC hunts operate
  under existing monitoring authority.
- Access to identity provider sign-in and audit logs (Entra ID `SignInLogs`/`AuditLogs`,
  Google Workspace Admin SDK Reports API login events, Okta System Log).
- Baseline knowledge of which applications legitimately use the device code flow in the
  environment (smart TVs, CLI tools, printers, IoT devices).

## Procedure

1. **Understand the legitimate baseline.**
   - List every application and device type authorized to use the device authorization
     grant in each IdP.
   - In Entra ID, device code flow usage appears in sign-in logs with client-app and
     protocol details; most tenants have very few legitimate users of it.

2. **Hunt for anomalous device-code authentications.**
   - Query sign-in logs for device code flow events where the user agent, IP, or location
     does not match the expected device profile.
   - Example: a device-code sign-in completed from a desktop browser in a different
     country minutes after the code was issued to a supposed smart-TV app.

3. **Correlate issuance and completion.**
   - The device code is issued to one client session and completed by the user in a
     browser — flag pairs where issuance IP and completion IP differ sharply.
   - Flag completions happening unusually fast after a phishing lure timestamp from email
     gateway logs.

4. **Inspect the resulting sessions and tokens.**
   - Follow the sign-in to the tokens granted: check granted scopes, the client
     application, and subsequent Graph/API activity.
   - Attackers typically pivot immediately to mail read, file exfiltration, or further app
     consent — look for that burst.

5. **Check for impossible device claims.**
   - Some flows let the client assert device information; look for mismatches between the
     claimed device (e.g., a smart TV app) and actual telemetry (Windows browser user
     agent completing the code).

6. **Review user reports and phishing telemetry.**
   - Correlate with email gateway logs for lures containing device-login URLs or
     8-character codes (Defender for Office 365 Threat Explorer, Proofpoint, etc.).
   - Interview the targeted user about what site they visited and what the page looked
     like; capture headers and URLs if the lure is still available.

7. **Contain.**
   - Revoke the user's sessions and refresh tokens, remove any app consent grants created
     in the session, and reset credentials.
   - Block the phishing infrastructure (sender domains, lure URLs) at the email gateway
     and web proxy.

8. **Harden the flow.**
   - Restrict device code flow via conditional access or app policy to only approved
     client apps; require compliant devices for the completing browser session.
   - Consider disabling the flow tenant-wide if no legitimate use exists — in Entra ID use
     authentication flow policies and conditional access filters targeting device-code
     client apps.

9. **Add persistent detections.**
   - Alert on: device code flow used by a user who has never used it; completion IP
     differing from issuance IP; device code flow followed within minutes by
     high-privilege Graph calls.
   - Review and tune weekly for the first month — legitimate CLI usage patterns will
     surface.

10. **Educate users.**
    - Brief users that legitimate services never ask them to enter a code on a site reached
      from an unexpected email or message.
    - Route future reports to the SOC quickly; time matters because the attacker session is
      live the moment the code is completed.

## Key tools & commands

- Entra ID sign-in logs filtered on device code flow client apps; KQL in Sentinel against
  `SigninLogs` joined with `AADNonInteractiveUserSignInLogs`.
- Okta System Log queries for device-flow authentication events and anomalous device
  fingerprints.
- Google Workspace Reports API `activities.list` with `applicationName=login`, filtered by
  IP and application.
- Email gateway search (Defender for Office 365 Threat Explorer, Proofpoint, etc.) for
  messages containing device-login domains or code patterns.
- Conditional Access policies (Entra ID) / sign-on policies (Okta) to restrict the flow.

## Expected outputs

- Timeline linking lure delivery, code issuance, code completion, and post-compromise API
  activity.
- List of affected users, tokens/scopes granted, and data accessed.
- Containment record (sessions revoked, grants removed, infrastructure blocked).
- Policy changes restricting or disabling device code flow, plus new detection rules with
  tuning notes.

## Pitfalls

- The attack uses the *legitimate* IdP login page, so URL reputation and page appearance
  look clean — detection must rely on behavioral correlation, not page analysis.
- MFA does not stop this: the victim completes MFA themselves. Do not close the
  investigation at "MFA was satisfied."
- Forgetting to check which scopes the attacker's app received; session revocation alone
  may miss a consented malicious app that retains access.
- Alerting on all device code flow usage without a baseline — legitimate CLI and device
  usage will drown the signal.

## References

- MITRE ATT&CK: T1528 (Steal Application Access Token), T1078 (Valid Accounts), T1566
  (Phishing).
- Microsoft Learn: "Device authorization grant" flow documentation and conditional access
  guidance for authentication flows.
- Okta documentation: device authorization grant and System Log event types.
- OAuth 2.0 Device Authorization Grant, RFC 8628.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
