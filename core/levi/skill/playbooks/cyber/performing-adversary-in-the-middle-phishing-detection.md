---
skill_id: cyber_performing_adversary_in_the_middle_phishing_detection
name: Performing Adversary-in-the-Middle Phishing Detection
description: Detect AiTM phishing kits that relay credentials and MFA in real time.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, aitm, detection]
version: 1.0.0
---

## Purpose
Adversary-in-the-middle (AiTM) phishing kits proxy the real login flow, defeating traditional MFA by relaying the session. This playbook builds detection for AiTM campaigns: identifying kit infrastructure, spotting victim sessions, and responding before session cookies are abused.

## When to use
- Phishing reports involve lookalike login pages that "felt real" to users.
- You need to detect session-cookie theft that bypasses MFA.
- Threat intel names AiTM kits (Evilginx-style, Tycoon, NakedPages variants) targeting your sector.

## Prerequisites
- Email gateway and web proxy logs with full URL visibility.
- Identity provider sign-in logs with session, device, and network metadata.
- Threat intel on current AiTM kit domains, URL patterns, and infrastructure.

## Procedure
1. **Know the kit markers.** AiTM pages proxy the legitimate IdP: look for lookalike domains, unusual redirect chains, and login flows where the final IdP session originates from datacenter IPs rather than the user's network.
2. **Detect at the email layer.** Flag messages linking to newly-registered lookalike domains, URLs with AiTM kit path patterns, and QR-code-based lures (quishing) that push users to mobile browsers.
3. **Detect at the identity layer.** Alert on: successful logons immediately preceded by impossible-travel or datacenter ASN source, new session cookie use from a different device/network than the one that authenticated, and MFA satisfied but session established from anomalous infrastructure.
4. **Hunt victim sessions.** For each confirmed lure, list who visited, who authenticated, and whether a session token was issued to attacker infrastructure; revoke those sessions immediately.
5. **Contain the campaign.** Block kit domains at proxy/DNS/email gateway, purge the lures tenant-wide, and force re-authentication for affected users.
6. **Move to phishing-resistant MFA.** The durable fix is FIDO2/WebAuthn, which AiTM cannot relay; prioritize rollout for high-risk users and track adoption.
7. **Share indicators.** Report kit domains and patterns to your ISAC and the impersonated brand's abuse team.

8. **Monitor for kit evolution.** Track new AiTM kit variants and QR-based lures in threat intel; update email and identity detections as kits change infrastructure and techniques.
9. **Test user resilience.** Include AiTM-style lures (lookalike login pages, QR codes) in phishing simulations so users learn what modern phishing actually looks like.

## Expected outputs
- AiTM detections across email, web, and identity telemetry.
- Victim session inventory with revocation records.
- Phishing-resistant MFA rollout plan informed by AiTM exposure.
- Example: identity logs show a successful MFA-satisfied logon where the session was established from a datacenter ASN minutes after the user authenticated from their home IP — the classic AiTM session-theft signature, triggering immediate session revocation.

## Pitfalls
- Resetting passwords but leaving stolen session cookies valid: the attacker stays logged in.
- Treating AiTM as "just phishing": the MFA bypass changes the response urgency.
- Blocking one kit domain while the operator rotates to fresh infrastructure hourly.

- Relying on users to report AiTM pages; the pages look pixel-identical to the real login, so detection must be technical, not human.
- Blocking kit domains at the email gateway only, while users reach the same kits via SMS, messaging apps, or QR codes.

## References
- MITRE ATT&CK T1557 (Adversary-in-the-Middle).
- CISA guidance on phishing-resistant MFA (cisa.gov).
- Microsoft threat intelligence on AiTM phishing (microsoft.com/security/blog) — kit technique analysis.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
