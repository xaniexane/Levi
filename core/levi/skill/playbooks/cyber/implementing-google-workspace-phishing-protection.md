---
skill_id: cyber_implementing_google_workspace_phishing_protection
name: Phishing Protection in Google Workspace
description: Harden Gmail against phishing: advanced attachment/URL defense, spoofing controls, and user reporting.
risk: low
permissions: []
requires_confirmation: false
tags: [email, phishing]
version: 1.0.0
---
## Purpose
Gmail's default protections are good; targeted phishing still lands. Google Workspace offers layered
phishing defenses: enhanced safe-browsing and attachment protection, link and image protections,
spoofing/impersonation controls, and security sandbox for attachments. This playbook enables and
tunes them, plus the user-reporting workflow that turns employees into sensors.

## When to use
- Reducing phishing-driven incidents (credential theft, malware, BEC) in a Workspace environment.
- After successful phishing campaigns bypassed default Gmail filtering.
- Meeting email-security expectations for high-target organizations.
- Before high-risk periods or after executive targeting is observed.
- As the email layer alongside DMARC authentication and security awareness.

## Prerequisites
- Super-admin or security-admin access to the Gmail safety settings.
- Defined risk tiers: executives/finance (strictest) vs. general users.
- DMARC/SPF/DKIM deployed (authentication complements content filtering — do both).
- A SOC workflow for phishing reports: triage, IOC extraction, and remediation.
- User communication: what changes (banners, delays, report button) and why.

## Procedure
1. **Enable enhanced protections.** Turn on: enhanced pre-delivery message scanning, attachment
   protection (security sandbox for suspicious attachments), link and external-image protection, and
   spoofing/unauthenticated-email protections. These are the advanced toggles beyond defaults —
   enable org-wide, not just for pilot OUs.
2. **Deploy the security sandbox thoughtfully.** Enable attachment sandboxing for high-risk OUs
   first (executives, finance), measure delay and false-positive impact, then expand. Communicate
   expected delays for scanned attachments — surprise delays generate helpdesk tickets and bypass
   requests.
3. **Tune spoofing and impersonation controls.** Enable: protect against domain spoofing (with your
   authenticated domains), employee-name spoofing warnings, and unauthenticated-email warnings. Add
   your executive names and key partner domains to impersonation protections — BEC lives on these.
4. **Use safety settings per risk tier.** High-risk OUs: aggressive attachment/link handling,
   shorter or no allowance for risky content, mandatory warnings. General OUs: standard with
   warnings. Service/automation mailboxes: tuned to avoid breaking legitimate flows. One policy for
   everyone either under-protects executives or over-blocks operations.
5. **Deploy user reporting.** Enable the Gmail "report phishing" integration feeding the SOC queue
   (or a dedicated phishing mailbox with automated enrichment). Close the loop: acknowledge reports,
   share outcomes in aggregate. Reporting rate is a security-culture metric — celebrate it, don't
   just measure clicks.
6. **Build the SOC triage workflow.** On report or alert: extract URLs/attachments, check sandbox
   verdicts, search for other recipients (Gmail search across the tenant), remove/quarantine
   malicious messages tenant-wide, block IOCs at proxy/DNS/EDR, and reset credentials for clickers
   on credential-harvesting pages. Time-to-removal is the metric.
7. **Run targeted simulations.** Phishing-test high-risk groups with realistic lures (not gotchas):
   measure report rate (the metric that matters) alongside click rate. Use failures as coaching
   moments, not punishment — punitive programs suppress reporting.
8. **Monitor the email threat landscape.** Review: phishing reports by campaign, sandbox detection
   trends, impersonation attempts against executives, and filter-bypass samples (what got through
   and why). Feed bypasses into tuning and into user-training examples (real, recent, relevant).
9. **Coordinate with authentication.** Keep DMARC at p=reject, monitor aggregate reports for
   spoofing attempts, and ensure the content-filtering and authentication layers are both healthy —
   they defend different attack variants. Review both in the same quarterly email-security review.
10. **Report email-security posture.** Metrics: phishing emails blocked/delivered, user report rate
    and true-positive rate, mean time to remove malicious mail, credential-reset counts from clicks,
    and simulation trends. The story: fewer incidents from email year over year, faster response
    when they occur.

## Expected outputs
- Enhanced Gmail protections enabled org-wide: scanning, sandbox, link/image, spoofing controls.
- Risk-tiered safety settings with impersonation protection for executives and partners.
- User reporting integrated with SOC triage, tenant-wide removal, and IOC blocking.
- Simulation program measuring report rate; bypass-driven tuning.
- Quarterly email-security reviews with posture metrics.

## Pitfalls
- Defaults assumed sufficient: targeted phishing beats defaults regularly. The advanced toggles
  exist for a reason — enable them.
- Sandbox delays unexplained: users tolerate security friction they understand. Communicate before
  enabling.
- Punitive simulations: shaming clickers suppresses the reporting you actually need. Coach, don't
  punish.
- No tenant-wide removal capability: finding one phish without removing its siblings leaves the
  campaign alive. Build the search-and-remove workflow.
- Treating content filtering as complete: authentication (DMARC), user behavior, and process
  controls (payment verification) are co-required.

## References
- Google Workspace Admin Help: Gmail safety and phishing settings
- Google Workspace Alert Center (phishing-related alerts)
- CISA phishing guidance and BEC prevention
- MITRE ATT&CK T1566 (Phishing)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
