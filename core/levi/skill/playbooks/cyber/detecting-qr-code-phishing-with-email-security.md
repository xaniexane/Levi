---
skill_id: cyber_detecting_qr_code_phishing_with_email_security
name: Detecting QR Code Phishing with Email Security
description: Detect QR-code phishing (quishing) that bypasses URL-based email defenses.
risk: low
permissions: []
requires_confirmation: false
tags: [phishing, email-security, detection]
version: 1.0.0
---
## Purpose

QR-code phishing embeds the malicious URL in an image, defeating URL-rewriting and link-analysis defenses that can't 'see' the destination. This playbook covers detecting quishing at the email gateway and in user-reported mail: image analysis, QR decoding, and the policy controls that reduce exposure.

## When to use

- Phishing reports mention QR codes or your gateway lacks QR analysis.
- Users received 'scan to verify' or 'scan to view document' emails.
- You need to assess quishing exposure and add controls.
- Incident response: a quishing campaign targeted your users.

## Prerequisites

- Email gateway with attachment/image analysis capability, or a QR-decoding step you can add (gateway feature or downstream analysis).
- Access to quarantined/delivered mail samples for analysis and tuning.
- URL-analysis infrastructure (detonation, reputation) to evaluate decoded destinations.
- User-reporting channel (phishing report button) feeding the SOC.

## Procedure

1. Understand why quishing bypasses controls. QR codes move the URL from text (inspectable) to image (opaque): link-rewriting, Safe Links-style detonation, and domain-reputation checks all fail silently. Confirm your gateway's behavior on image-embedded URLs — many gateways simply don't extract them, which defines your gap.
2. Add QR extraction and analysis to the mail flow. Where the gateway supports it, enable QR-code detection/decoding; otherwise build a downstream step: extract images from inbound mail, decode QR payloads, and submit decoded URLs to your standard URL-analysis pipeline (reputation, detonation, blocklist). Treat decoded QR URLs with the same policy as message-body URLs.
3. Write detections for quishing patterns. Alert on: inbound mail containing QR images with social-engineering lures (MFA re-registration, 'document shared', package delivery, HR/benefits themes), QR destinations pointing to newly registered domains or credential-harvesting kits, and QR codes in mails from first-time or spoofed senders. Correlate user QR-scan reports (from mobile threat defense, if available) with mail delivery logs.
4. Hunt historically when a campaign is confirmed. Decode QR payloads from delivered mail over the retention window, identify the credential-harvesting domains, check proxy/DNS logs for users who visited them post-delivery, and treat visitors as compromised credentials until password reset + MFA re-verification.
5. Respond to successful quishing as credential compromise. Reset affected passwords, revoke sessions/tokens, review MFA enrollment changes (attackers often register their own authenticator after harvesting), check mail-forwarding rules the attacker may have set, and block the infrastructure at gateway, proxy, and DNS.
6. Harden structurally: enable gateway QR-code analysis, add quishing examples to security awareness training (teaching users to distrust 'scan to' prompts from email), consider blocking or quarantining inbound mail with QR codes for high-risk groups, and enforce phishing-resistant MFA so harvested passwords alone are insufficient.

## Expected outputs

- QR extraction/decoding integrated into the mail-analysis pipeline.
- Quishing detection rules: lure themes + QR presence + decoded-URL reputation.
- Historical hunt procedure: decode → domain identification → visitor scoping.
- Awareness content: quishing examples and 'scan-to' skepticism training.

## Pitfalls

- Decoding QR codes without analyzing the destination URL just moves the blind spot — always analyze decoded URLs.
- Legitimate QR use (event tickets, MFA enrollment, internal comms) exists — tune lures and sender reputation, don't blanket-block.
- Users scan QR codes on personal phones, bypassing corporate proxy visibility — pair with user reporting and IdP anomaly detection.
- QR payloads can be non-URL (WiFi configs, payment requests) — handle decode outputs by type.
- Awareness training alone doesn't stop quishing; it must pair with gateway decoding and MFA hardening.

## References

- NIST SP 800-177 (email security); MITRE ATT&CK T1566.002 (Phishing: Spearphishing Link) — https://attack.mitre.org/techniques/T1566/002/; CISA guidance on phishing-resistant MFA
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
