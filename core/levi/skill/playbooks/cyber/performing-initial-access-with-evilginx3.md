---
skill_id: cyber_performing_initial_access_with_evilginx3
name: Adversary-in-the-Middle Phishing Defense
description: Detect AiTM phishing kits and harden authentication against session theft.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, detection, authentication]
version: 1.0.0
---
# Adversary-in-the-Middle Phishing Defense

## Purpose

Adversary-in-the-middle (AiTM) phishing proxies relay a victim's real
login — including MFA codes — to the legitimate site and steal the
resulting session. Tools like Evilginx automate this. This playbook is
purely defensive: how to detect AiTM campaigns, investigate them, and
harden authentication so stolen sessions are useless.

## When to use

- Investigating phishing reports where users completed MFA yet accounts
  were still compromised.
- Reviewing authentication logs for session-token replay indicators.
- Hardening identity infrastructure against MFA-bypass phishing.
- Threat-modeling the organization's phishing resilience.

## Prerequisites

- Access to identity-provider sign-in logs (Entra ID, Okta, Google
  Workspace) with IP, user agent, and MFA details.
- Ability to enforce phishing-resistant MFA (FIDO2/WebAuthn) and
  Conditional Access-style policies.
- A phishing-reporting channel so user reports reach the SOC quickly.

## Procedure

1. Recognize the AiTM signature: successful MFA followed by a session
   used from a different IP/ASN, user agent, or geography than the
   login — the proxy relays credentials but the attacker replays the
   cookie.
2. Hunt in sign-in logs: look for logins where the IP's ASN or
   geolocation differs between the authentication event and subsequent
   session activity, and for user agents inconsistent with the user's
   fleet.
3. Inspect reported phishing URLs: resolve the lure domain, check its
   age and registrar, and confirm it proxies a legitimate login page
   (TLS certificate details and page source referencing the real
   identity provider are tells).
4. Contain compromised sessions: revoke refresh tokens and sessions
   for affected users immediately, force re-authentication, and review
   what the attacker accessed during the session window.
5. Deploy phishing-resistant MFA: FIDO2 security keys or passkeys bind
   authentication to the real origin — a proxy cannot complete the
   ceremony on a different domain.
6. Enforce token protection: Conditional Access policies requiring
   compliant devices, and token-binding or continuous-access evaluation
   where supported, so replayed sessions fail policy checks.
7. Block and share: add the phishing domains and IPs to email gateway
   and proxy blocklists, submit to takedown and threat-intel sharing.
8. Train with the real story: show users that "I used MFA" is not proof
   of safety, and reinforce reporting speed — session theft has a short
   useful life if revocation is fast.

## Expected outputs

- Hunt queries detecting login/session IP and user-agent mismatches.
- Containment records: sessions revoked, users re-secured.
- Phishing-resistant MFA rollout plan and token-protection policies.
- Blocklist entries and takedown requests filed.

## Pitfalls

- Assuming MFA equals immunity: only phishing-resistant MFA stops
   AiTM — TOTP and push can both be relayed.
- Revoking the password but not the session: the attacker keeps the
   stolen cookie.
- Treating one campaign as the whole problem: AiTM kits are reusable —
   fix the authentication, not just the domain.
- Slow revocation: every hour of session life is attacker dwell time.

## References

- CISA guidance on phishing-resistant MFA (cisa.gov)
- Microsoft documentation on token protection and Conditional Access
- MITRE ATT&CK: Adversary-in-the-Middle (T1557) and Steal Web Session Cookie (T1539)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
