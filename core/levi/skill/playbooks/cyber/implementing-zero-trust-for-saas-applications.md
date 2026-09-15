---
skill_id: cyber_implementing_zero_trust_for_saas_applications
name: Implementing Zero Trust for SaaS Applications
description: Apply zero-trust controls to SaaS: inventory, SSO, posture checks, and session policy.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, saas, identity]
version: 1.0.0
---
## Purpose
This playbook brings SaaS applications under zero-trust governance: discovering shadow SaaS, enforcing SSO and MFA, evaluating device and user risk at access time, and controlling sessions — so SaaS access is continuously verified, not implicitly trusted.

## When to use
- SaaS sprawl with inconsistent authentication and no central inventory.
- Sensitive data lives in SaaS apps outside DLP and logging coverage.
- Moving toward a zero-trust architecture and SaaS is the largest gap.

## Prerequisites
- Identity provider with SSO/MFA capability (Okta, Entra ID, or similar).
- CASB or SaaS-management platform for discovery and policy enforcement.
- Data classification to know which SaaS apps handle sensitive information.

## Procedure
1. **Discover the SaaS estate.** Combine CASB discovery, IdP app catalogs, expense data, and DNS/firewall logs to build the full inventory, including unsanctioned apps.
2. **Classify and rationalize.** Rate each app by data sensitivity and business need; consolidate duplicates and retire unjustified shadow IT.
3. **Enforce SSO and phishing-resistant MFA.** Federate every sanctioned app to the IdP; require phishing-resistant MFA (FIDO2/WebAuthn) for apps handling sensitive data.
4. **Apply conditional access.** Build policies on user risk, device compliance, network, and application sensitivity: allow, step-up, or block with clear user messaging.
5. **Control the session.** Enforce session lifetimes, token binding where supported, and continuous access evaluation so revocation propagates quickly.
6. **Extend DLP and logging.** Enable SaaS audit logging into the SIEM; apply DLP policies to uploads, sharing links, and external collaborators.
7. **Govern continuously.** Re-certify app ownership and access quarterly; automatically flag new shadow SaaS for review.

8. **Audit third-party integrations.** Inventory OAuth grants and API tokens each SaaS app holds; revoke unused integrations and restrict scopes on the rest.
9. **Plan for IdP outage.** Document how critical SaaS access works if the IdP is down, including break-glass accounts with phishing-resistant MFA, tested in drills.

## Expected outputs
- Complete SaaS inventory with classification, owners, and SSO status.
- Conditional access policies covering sanctioned SaaS with MFA enforcement.
- SaaS audit logs in the SIEM with DLP coverage on sensitive apps.
- Example: all finance SaaS apps federated to the IdP with FIDO2-required conditional access; a sign-in from a non-compliant device triggers step-up authentication and the attempt is logged to the SIEM.

## Pitfalls
- SSO without MFA on the IdP itself: one phished password still opens every app.
- Allowing indefinite OAuth grants to third-party integrations without review.
- Blocking shadow SaaS outright without providing an approved alternative, which just drives it further underground.

- Conditional access policies with overlapping rules where the most permissive wins unexpectedly; test policy evaluation order deliberately.
- Forgetting service accounts and API integrations in the SSO push; non-human SaaS access is often the least governed.

## References
- NIST SP 800-207, Zero Trust Architecture.
- CISA Zero Trust Maturity Model (cisa.gov/zero-trust-maturity-model).
- CSA Security Guidance for Critical Areas of Focus in Cloud Computing (cloudsecurityalliance.org).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
