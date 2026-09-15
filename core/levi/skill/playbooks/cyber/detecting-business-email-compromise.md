---
skill_id: cyber_detecting_business_email_compromise
name: Detecting Business Email Compromise
description: Detect BEC attacks with mailbox-rule, language-pattern, and payment-fraud monitoring across the email estate.
risk: info
permissions: []
requires_confirmation: false
tags: [email, fraud, detection]
version: 1.0.0
---
## Purpose

Detect business email compromise — attackers in mailboxes or spoofing executives to drive fraudulent wire transfers and gift-card scams — through the technical signals BEC leaves: forwarding rules, anomalous logons, language patterns, and payment anomalies. BEC is the costliest cybercrime category; detection here has direct financial ROI.

## When to use

- Building BEC detection for the first time or tuning noisy existing rules.
- Investigating a suspected executive impersonation or vendor email compromise.
- After a finance-team social-engineering attempt (successful or not).
- Validating email authentication (SPF/DKIM/DMARC) enforcement.

## Prerequisites

- Mailbox audit logging enabled (Exchange Online / Google Workspace) with centralized log access.
- Email gateway logs with header data (Return-Path, Reply-To, authentication results).
- Finance process knowledge: who can authorize payments, normal vendor/payment patterns.
- Alerting path to both the SOC and the finance team — BEC response is a joint operation.

## Procedure

1. **Enforce email authentication and monitor it.** Publish SPF, DKIM, and DMARC with `p=reject`, and alert on: DMARC failures for your domains, lookalike-domain registrations (monitor certificate transparency and domain-registration feeds for your brand), and display-name spoofing of executives in inbound mail.
2. **Detect mailbox-rule-based persistence.** Alert on any inbox rule that forwards, redirects, or deletes mail — especially rules created recently, rules forwarding to external addresses, and rules with suspicious names. Attackers create these to hide their activity and intercept replies. This is the highest-fidelity BEC technical signal.
3. **Detect account-takeover precursors.** Alert on: logons to executive/finance mailboxes from new locations or devices, MFA changes on finance accounts, OAuth consent grants to mail-reading apps, and password resets on finance mailboxes. Correlate with step 2 — takeover followed by rule creation is the classic BEC sequence.
4. **Monitor language and behavior patterns.** Flag messages that: request urgent wire transfers or gift cards, change payment instructions (especially vendor bank-detail changes), come from free webmail or lookalike domains impersonating executives/vendors, and exhibit urgency + secrecy language. Tune to your organization's communication norms — the CFO who never emails finance directly doing so is the signal.
5. **Protect the payment process itself.** Work with finance on out-of-band verification: any payment-instruction change requires a phone call to a known number (not one from the email). Alert the SOC on: new vendor bank accounts added, payments to first-time beneficiaries, and amounts just below approval thresholds. Technical detection plus process control beats either alone.
6. **Detect vendor email compromise.** Monitor for: established vendor contacts suddenly changing tone, bank details, or sending from new addresses; and replies that subtly alter thread context. Maintain a verified vendor-contact registry with confirmed phone numbers for verification callbacks.
7. **Respond fast — money moves in hours.** On confirmed BEC: recall/stop the transfer immediately (contact the bank's fraud department — speed matters more than completeness), preserve the mailbox and logs for forensics, reset the compromised account with session revocation, remove malicious rules, and check what else the attacker saw (they read mail for weeks before acting — scope the intelligence loss).

## Expected outputs

- DMARC at reject with lookalike-domain monitoring and display-name spoof detection.
- High-fidelity alerts on forwarding-rule creation, finance-account anomalies, and payment-instruction changes.
- Out-of-band payment verification process with finance; rapid wire-recall response procedure.

## Pitfalls

- DMARC at `p=none` forever — monitoring without enforcement doesn't stop spoofing.
- Alerting on forwarding rules but allowing users to create them freely — restrict external forwarding by policy.
- Finance verifying bank changes by replying to the same email thread — the attacker controls the thread.
- Treating BEC as purely a technical problem — the payment process is the real control.
- Slow response — wire transfers become unrecoverable within hours; the playbook must prioritize speed.

## References

- FBI IC3 Internet Crime Reports — BEC as the costliest cybercrime category
- CISA / NSA guidance on email security and BEC prevention
- Microsoft Learn — Exchange Online mailbox auditing and alert policies
- NIST SP 800-177 (Trustworthy Email) — SPF/DKIM/DMARC deployment
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
