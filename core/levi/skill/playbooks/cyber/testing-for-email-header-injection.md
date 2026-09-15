---
skill_id: cyber_testing_for_email_header_injection
name: Testing for Email Header Injection
description: Authorized testing for CRLF email header injection in forms, plus safe email-sending patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [web, injection, testing]
version: 1.0.0
---
## Purpose
Where user input is placed into email headers (contact forms, invitations, password resets), CRLF injection can add BCC recipients or rewrite messages, turning your mailer into a spam relay. This playbook covers authorized testing of your own applications and the safe coding patterns that eliminate the issue.

## When to use
- Security testing of features that send email from user input.
- After adding contact, invite, or notification features.
- Reviewing legacy code that builds mail headers by string concatenation.
- Investigating suspected abuse of your mail forms for spam.

## Prerequisites
- Written authorization and a test mail catcher (never real inboxes).
- Inventory of user-controlled inputs reaching email headers (to, subject, reply-to, custom headers).
- Access to the mail-sending code or library configuration.
- Proxy tooling for injecting CRLF sequences.

## Procedure
1. Map every user input that flows into email headers or the envelope.
2. Submit CRLF payloads (`%0d%0a`, `\r\n`) in each field and observe the generated message in the test catcher.
3. Attempt to inject `Bcc:`, `Cc:`, `Subject:`, and `Content-Type:` headers via the vulnerable field.
4. Check whether injected headers are acted upon by the MTA or merely logged.
5. Verify the fix: use mail libraries' structured APIs (never string-concatenated headers), strip CR/LF from header inputs, and validate addresses with proper parsers.
6. Confirm that display names and subjects are encoded, not interpolated.
7. Re-test all previously vulnerable fields after the fix.
8. Add monitoring for outbound mail anomalies: volume spikes and unusual recipient patterns.
9. Check SMS and push notification paths too; they share the same header-injection class.
10. Normalize Unicode input before validation; exotic line separators bypass naive CR/LF stripping.
11. Review scheduled and bulk-mail jobs, not just interactive forms.

## Expected outputs
- Field-by-field injection test results with captured messages.
- Findings with spam-relay impact assessment.
- Fixed mail-sending code patterns and retest evidence.
- Multi-channel (email/SMS/push) injection assessment.
- Unicode normalization verification results.
- Bulk-mail job review notes.

## Pitfalls
- Different MTAs and libraries handle bare LF vs CRLF differently; test the real stack.
- Fixing the contact form while the invite feature uses the same helper leaves the bug alive.
- Display-name injection is often missed when only the address field is tested.
- Rate limiting the form reduces abuse but does not fix the injection.
- Unicode line separators bypass naive CR/LF stripping; normalize input first.
- Bulk-mail personalization engines are a second injection surface; review them.
- Logging email content for debugging can leak PII; sanitize mail logs.
- Bounce and autoresponder messages can reflect injected headers back to attackers; test those paths.

## References
- OWASP Web Security Testing Guide: testing for email header injection.
- OWASP Cheat Sheet: injection prevention patterns.
- Mail library documentation (structured header APIs).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
