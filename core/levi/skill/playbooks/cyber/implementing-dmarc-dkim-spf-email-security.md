---
skill_id: cyber_implementing_dmarc_dkim_spf_email_security
name: Email Authentication with DMARC, DKIM, and SPF
description: Deploy SPF, DKIM, and DMARC to p=reject, stopping exact-domain phishing and improving deliverability.
risk: moderate
permissions: []
requires_confirmation: true
tags: [email, authentication]
version: 1.0.0
---
## Purpose
Exact-domain phishing — emails that genuinely come "from" your domain — is only stoppable with email
authentication: SPF (which servers may send), DKIM (cryptographic signature), and DMARC (policy
tying them together with reporting). This playbook takes a domain from no authentication to DMARC
p=reject safely: inventory senders, phase the policy, and use aggregate reports to catch legitimate
mail before enforcement breaks it. Confirmation is required: DNS changes affect all outbound mail
flow.

## When to use
- Stopping exact-domain spoofing and phishing using your brand.
- After phishing incidents that spoofed your domain (or customer/partner complaints).
- Meeting email-authentication requirements (PCI DSS, Google/Yahoo bulk-sender requirements,
  government mandates).
- Improving deliverability: authenticated mail is trusted mail.
- Before a DMARC enforcement deadline (regulatory or contractual).

## Prerequisites
- DNS control for the domain(s): ability to publish TXT records.
- Complete inventory of legitimate senders: corporate mail (M365/Google), marketing platforms,
  transactional mail, HR/finance tools, and any shadow senders (discover via DMARC reports in
  monitor mode).
- DKIM key management: ability to generate and rotate selectors per sending service.
- A mailbox or service to receive DMARC aggregate (rua) and forensic (ruf) reports, plus tooling to
  analyze them (or a DMARC SaaS).
- Change windows coordinated with marketing/transactional mail owners.

## Procedure
1. **Inventory all legitimate senders.** Survey teams and check: mail platform admin consoles,
   marketing automation, CRM, support desks, and cloud services that send as your domain. Assume the
   inventory is incomplete — DMARC monitor mode will reveal the rest.
2. **Deploy SPF.** Publish an SPF TXT record listing all authorized sending IPs/services. Keep it
   under 10 DNS lookups (flatten includes where needed); end with `-all` (hard fail) only after
   validation, `~all` during transition. Verify with SPF checkers from multiple vantage points.
3. **Deploy DKIM for each sender.** Generate 2048-bit keys per sending service, publish selectors,
   and enable signing. Confirm signatures validate (check headers on test messages). Rotate
   selectors annually — document the rotation procedure per service.
4. **Publish DMARC at p=none with reporting.** Start: `v=DMARC1; p=none; rua=mailto:reports@...;
   ruf=mailto:...; fo=1`. This changes nothing about delivery but starts the aggregate-report
   firehose — your sender-discovery and compliance-measurement tool.
5. **Analyze reports and close gaps.** For 2-4 weeks, analyze aggregate reports: identify legitimate
   senders failing SPF/DKIM (shadow IT, new services, forwarding breakage), fix them (add to SPF,
   enable DKIM), and note unauthorized senders (potential spoofing — investigate). Drive SPF/DKIM
   alignment to ~100% for legitimate mail.
6. **Move to p=quarantine.** Once legitimate mail authenticates: `p=quarantine` (failing mail to
   spam). Monitor for another 1-2 weeks: watch for deliverability complaints, check reports for
   newly failing legitimate sources. This is the safety net phase — problems here are recoverable.
7. **Enforce p=reject.** With quarantine stable: `p=reject; pct=100`. Failing mail is now refused
   outright — exact-domain spoofing is dead. Keep monitoring reports permanently: new services,
   acquisitions, and infrastructure changes will introduce new senders that need authentication.
8. **Handle the hard cases.** Mailing lists and forwarding break SPF (use DKIM alignment + ARC where
   supported); third-party senders need DKIM delegation (they publish via your selector or you CNAME
   to them — prefer their DKIM with your domain in From). Document each exception's mechanism.
9. **Extend to subdomains and lookalikes.** Publish `sp=reject` for subdomains (or explicit
   subdomain policies), and set up defensive DMARC on lookalike/candidate domains you own. Monitor
   certificate transparency and domain registrations for lookalike domains used in cousin-domain
   phishing (DMARC can't stop those — user training and detection must).
10. **Maintain and report.** Quarterly: review aggregate reports for new senders and failures,
    rotate DKIM selectors, verify SPF lookup limits, and confirm p=reject still published (DNS
    changes and migrations silently drop records). Report: authentication pass rates, spoofing
    attempts blocked, and enforcement coverage across owned domains.

## Expected outputs
- SPF, DKIM (2048-bit, per-sender selectors), and DMARC p=reject deployed on all owned domains.
- Complete legitimate-sender inventory with alignment verified via aggregate reports.
- Phased rollout evidence (none → quarantine → reject) with monitoring at each stage.
- Handling for mailing lists, forwarding, and third-party senders documented.
- Ongoing report analysis, key rotation, and coverage of subdomains/lookalikes.

## Pitfalls
- Jumping to p=reject: unauthenticated legitimate senders (marketing, HR tools, shadow IT) get their
  mail refused. Phase through none and quarantine with report analysis.
- SPF lookup limits: nested includes exceeding 10 lookups cause permerror — flatten or prune.
- Forgetting subdomains: attackers spoof `anything.yourdomain.com` if `sp` isn't set. Cover the
  whole domain tree.
- No report analysis: publishing p=none without reading reports is security theater. The reports are
  the program.
- DMARC as anti-phishing complete: it stops exact-domain spoofing only. Cousin domains, compromised
  accounts, and display-name deception need other controls.

## References
- RFC 7208 (SPF), RFC 6376 (DKIM), RFC 7489 (DMARC)
- Google/Yahoo bulk sender requirements (authentication mandates)
- CISA guidance on email authentication / BOD 18-01 (for federal context)
- DHS/CISA DMARC deployment guides and report-analysis practices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
