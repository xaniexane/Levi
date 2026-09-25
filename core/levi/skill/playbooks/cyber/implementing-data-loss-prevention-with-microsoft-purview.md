---
skill_id: cyber_implementing_data_loss_prevention_with_microsoft_purview
name: DLP with Microsoft Purview
description: Implement data loss prevention with Microsoft Purview across M365, endpoints, and cloud apps.
risk: low
permissions: []
requires_confirmation: false
tags: [dlp, microsoft-365]
version: 1.0.0
---
## Purpose
Microsoft 365 holds the organization's crown-jewel unstructured data: email, Teams, SharePoint,
OneDrive, and endpoints. Microsoft Purview DLP enforces data-protection policy natively across these
workloads — no agents to deploy on M365, unified policy, and integration with sensitivity labels.
This playbook implements Purview DLP from classification through phased enforcement.

## When to use
- Protecting regulated or sensitive data in Microsoft 365 (PII, PHI, financial, IP).
- After data-exposure incidents via email, Teams, or overshared SharePoint/OneDrive links.
- Meeting DLP requirements for HIPAA, PCI DSS, GDPR, or SOC 2 in M365-centric environments.
- Before broad Copilot/AI adoption: DLP and labeling are prerequisites for safe AI on your data.
- Consolidating fragmented DLP point tools into the native M365 control plane.

## Prerequisites
- Microsoft 365 E5 (or E3 + add-ons) licensing for full DLP capabilities — verify license coverage.
- Data classification scheme and sensitivity labels defined (Purview DLP works best label-driven).
- Inventory of M365 workloads in scope: Exchange, SharePoint, OneDrive, Teams, endpoints (Endpoint
  DLP), and cloud apps via Defender for Cloud Apps.
- Policy owners per data type who define what constitutes a violation.
- User communication plan: DLP actions (blocks, justifications) need explanation before enforcement.

## Procedure
1. **Classify first with sensitivity labels.** Deploy Purview sensitivity labels (Confidential,
   Highly Confidential, etc.) with auto-labeling for known data types. DLP policies keyed on labels
   are more accurate than content-only matching — labeling is the force multiplier. Train users on
   manual labeling for what automation misses.
2. **Start DLP in audit/test mode.** Create policies in test mode (no enforcement) across workloads.
   Collect 2-4 weeks of would-trigger events. This measures the blast radius of enforcement and
   reveals the false-positive landscape before users feel anything.
3. **Tune detectors and policy scope.** Triage test-mode hits: tune sensitive-information types (add
   keywords, exclusions for test data), scope policies to the right sites/users/groups (start with
   high-risk groups and sensitive sites), and identify legitimate workflows needing exceptions.
   Precision before enforcement.
4. **Phase enforcement by workload.** Recommended order: Exchange (email exfiltration — highest
   risk), then SharePoint/OneDrive sharing, then Teams, then Endpoint DLP (USB, copy to personal
   cloud), then Defender for Cloud Apps session policies. Each phase: announce, enforce, support,
   measure, then proceed.
5. **Use graduated actions.** Configure: warn with policy tip and allow override with justification
   (low-risk), block with override requiring business justification (medium), hard block (regulated
   data exfiltration). Overrides must be logged, reviewed, and sampled — the justification trail is
   audit evidence.
6. **Protect the sensitive sites specifically.** For SharePoint/Teams sites holding regulated data:
   DLP policies scoped to those containers with stricter actions, plus sharing restrictions (no
   anonymous links, limited external sharing). Container-level policy beats tenant-wide where data
   concentrates.
7. **Deploy Endpoint DLP for the exfiltration paths M365 can't see.** Enable Endpoint DLP
   (Intune-onboarded devices): control USB/removable media, copy to network shares, print, and
   uploads to unsanctioned cloud apps for labeled content. This closes the endpoint gap in the M365
   DLP story.
8. **Monitor DLP as insider-threat signal.** Ship DLP alerts to the SIEM/SOC. Alert on: bulk
   override justifications, repeated blocks for the same user, DLP policy tampering, and violations
   by departing employees (integrate with HR signals). Handle per insider-threat procedures with
   legal coordination.
9. **Manage exceptions and overrides.** Maintain the exception register: who, what data, which
   channel, justification, approver, expiry. Sample-review override justifications monthly —
   "business need" without specifics gets followed up. Exceptions expire; renewals require
   re-justification.
10. **Govern quarterly.** Review with data owners: false-positive rates, override trends, new data
    types needing detectors, new M365 workloads/Copilot features needing coverage, and policy
    effectiveness. Report: incidents prevented, blocks/overrides, coverage of sensitive sites, and
    labeling adoption.

## Expected outputs
- Sensitivity labels deployed with auto-labeling; DLP policies label-driven.
- Phased enforcement across Exchange, SharePoint/OneDrive, Teams, endpoints, and cloud apps.
- Graduated actions with logged, reviewed overrides and an exception register.
- SIEM-integrated DLP alerting with insider-threat handling.
- Quarterly governance with coverage and effectiveness metrics.

## Pitfalls
- Enforcing before test-mode tuning: mass blocks on legitimate email and sharing will get DLP
  disabled. Test → tune → enforce.
- Content-only policies without labels: lower precision, more false positives. Invest in labeling —
  it's the highest-ROI DLP work.
- Ignoring endpoints: M365 DLP without Endpoint DLP leaves USB and personal-cloud uploads wide open.
- Override without review: justification workflows nobody samples become rubber stamps. Sample and
  follow up.
- Licensing gaps: DLP features vary by license — verify every in-scope user is licensed or coverage
  has silent holes.

## References
- Microsoft Learn: Microsoft Purview Data Loss Prevention documentation
- Microsoft Learn: sensitivity labels and auto-labeling
- NIST SP 800-53 MP-5, SC-7 (media transport, boundary protection)
- HIPAA Security Rule, PCI DSS v4.0 (DLP control expectations)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
