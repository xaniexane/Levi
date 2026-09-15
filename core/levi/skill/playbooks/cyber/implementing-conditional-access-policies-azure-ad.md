---
skill_id: cyber_implementing_conditional_access_policies_azure_ad
name: Conditional Access Policies in Microsoft Entra ID
description: Design and roll out Entra Conditional Access policies: phased, tested, and break-glass-safe.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, azure]
version: 1.0.0
---
## Purpose
Conditional Access (CA) is the policy engine of Entra ID: every sign-in evaluated against signals
(user, device, location, risk, app) with grant controls (MFA, compliant device, terms of use). Done
well, it's the highest-ROI identity control available; done carelessly, it locks out the company.
This playbook implements CA in disciplined phases: baseline policies, report-only measurement,
staged enforcement, and protected break-glass.

## When to use
- Establishing identity perimeter controls to replace or augment network-based access.
- After credential-phishing, token-theft, or password-spray incidents.
- Meeting MFA and access-control requirements (cyber insurance, SOC 2, PCI DSS, CIS).
- Before rolling out SSO broadly: CA is what makes SSO'd access actually conditional.
- As the enforcement arm of the zero-trust identity pillar.

## Prerequisites
- Entra ID P1/P2 licensing for CA and risk-based policies.
- Named locations defined (corporate egress IPs, VPN ranges, trusted countries).
- Device compliance signals: Intune-managed device states flowing to Entra.
- Identity Protection (risk detections) enabled if using risk-based policies.
- Break-glass accounts created, excluded from all CA policies, monitored, and tested.

## Procedure
1. **Protect break-glass first.** Create emergency-access accounts, exclude them from every CA
   policy, and alert on any use. Then — and only then — start building policies. A CA
   misconfiguration without break-glass is a self-inflicted total lockout.
2. **Deploy the baseline policy set.** Microsoft's recommended baselines (or CIS equivalents):
   require MFA for all users; require MFA for administrators; require MFA for Azure management;
   block legacy authentication; require compliant/hybrid-joined device or approved app for sensitive
   apps later. Implement baselines before custom policies.
3. **Always start in report-only mode.** Every new policy runs in report-only for 1-2 weeks. Analyze
   the report-only logs: who would be blocked, which apps break, which legacy clients appear. Fix or
   except before enforcing — the logs tell you exactly what enforcement will do.
4. **Block legacy authentication.** Legacy protocols (basic auth, older Office clients) bypass MFA
   entirely. After report-only measurement and remediation (upgrade clients, app passwords
   eliminated), enforce the block. This single policy kills password spray at scale.
5. **Add risk-based policies.** With Identity Protection: require password change or block on high
   user risk; require MFA on medium sign-in risk. Tune feedback (confirm compromised/safe) so
   detections improve. Risk policies catch what static rules miss.
6. **Gate sensitive apps with device controls.** For finance, HR, admin portals, and production
   tools: require compliant device or Entra hybrid-joined device plus MFA. Less sensitive apps: MFA
   alone. Tier by data sensitivity — uniform strictness creates exception pressure.
7. **Control location and network signals.** Block or challenge sign-ins from countries with no
   business presence; be cautious with broad geo-blocks (travelers, VPNs). Prefer risk-based and
   device-based controls over pure geo-blocking, which is easily bypassed and operationally noisy.
8. **Manage CA as code and change.** Export policies (via Graph/DevOps pipelines), peer-review
   changes, and test in report-only. Log and alert on all CA policy modifications — an attacker with
   admin rights disabling CA is a critical incident signal.
9. **Handle service accounts and automation.** Inventory non-interactive sign-ins: migrate to
   managed identities or workload identity federation; exclude remaining legacy service accounts
   narrowly (per-account, per-app) with compensating controls and sunset plans. Broad
   service-account exclusions hollow out CA.
10. **Monitor, measure, mature.** Track: MFA coverage, legacy-auth block hits, report-only vs.
    enforced policy inventory, sign-in failure rates (UX impact), and risk-policy true-positive
    feedback. Quarterly: review exclusions, tighten tiers, and add policies for new apps. CA is a
    living policy set.

## Expected outputs
- Break-glass accounts protected, excluded, and monitored before any policy work.
- Baseline CA policies enforced (MFA for all/admins/Azure management, legacy-auth block) after
  report-only validation.
- Risk-based and device-gated policies tiered by application sensitivity.
- CA managed as reviewed, logged change with alerting on modifications.
- Metrics: MFA coverage, policy inventory, sign-in health, exclusion reviews.

## Pitfalls
- Enforcing without report-only: the classic CA outage. Every policy proves itself in report-only
  first.
- Forgetting break-glass: one bad policy without emergency access = company-wide lockout.
  Non-negotiable prerequisite.
- Over-broad exclusions: excluding "all service accounts" or entire subnets negates the policy.
  Narrow, justified, expiring exclusions.
- Geo-blocking as the primary control: bypassed by VPNs, breaks travelers. Use as a layer, not the
  foundation.
- Stale policies: apps decommissioned but policies remain; new apps without policies. Tie CA review
  to the app lifecycle.

## References
- Microsoft Learn: Conditional Access documentation (policies, report-only mode, baselines)
- Microsoft Learn: emergency access accounts and legacy authentication blocking
- CIS Microsoft 365 / Entra ID Benchmarks
- NIST SP 800-63B (authenticator assurance) and SP 800-207 (zero trust)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
