---
skill_id: cyber_implementing_google_workspace_sso_configuration
name: SSO Configuration for Google Workspace
description: Configure SSO for Google Workspace: third-party IdP integration or Workspace-as-IdP, done securely.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, sso]
version: 1.0.0
---
## Purpose
Single sign-on centralizes authentication: one identity, one MFA, one place to disable access. For
Google Workspace, SSO means either federating Workspace logins to your third-party IdP (Okta, Entra
ID, etc.) or using Google as the IdP for third-party apps via SAML/OIDC. This playbook implements
both directions securely: correct SAML/OIDC configuration, MFA enforcement at the IdP, provisioning
lifecycle, and the super-admin exception handling that prevents lockouts.

## When to use
- Centralizing authentication for Workspace users under the corporate IdP.
- Using Google as the IdP for SaaS apps (reducing password sprawl).
- After incidents involving inconsistent MFA or orphaned app credentials.
- Meeting SSO/MFA requirements (SOC 2, cyber-insurance, internal policy).
- During IdP migrations or Workspace tenant consolidations.

## Prerequisites
- The authoritative IdP chosen and operational, with phishing-resistant MFA available.
- Inventory: which users authenticate where today, and which third-party apps need SSO.
- Super-admin break-glass accounts that bypass SSO (documented, monitored).
- Understanding of SAML/OIDC flows sufficient to validate configuration (or vendor support engaged).
- HR joiner/mover/leaver integration at the IdP (SSO's value depends on lifecycle).

## Procedure
1. **Decide the SSO direction(s).** Direction A: third-party IdP → Google Workspace (users log into
   Google via Okta/Entra). Direction B: Google → SaaS apps (Google as SAML/OIDC IdP). Most orgs need
   A; many also use B for long-tail apps. Document which direction each population uses — mixed
   without documentation confuses everyone.
2. **Protect super-admins from SSO first.** Designate break-glass super-admin accounts that
   authenticate directly to Google (bypassing SSO), secured per the admin-hardening playbook. Test
   them. SSO misconfiguration without direct-access recovery is a tenant lockout — this is step
   zero.
3. **Configure the SAML integration precisely.** In the IdP and Google Admin: exchange metadata
   correctly, set the NameID format both sides expect (usually email), map attributes (first/last
   name), configure signed assertions and (where supported) encrypted assertions, and validate the
   ACS URL and entity IDs. One mismatched field = silent login failures — verify each value.
4. **Enforce MFA at the IdP.** With SSO, Google trusts the IdP's authentication — so the IdP must
   enforce phishing-resistant MFA for all federated users. Verify: no MFA-bypass policies at the IdP
   for Workspace users, and Google's own 2SV settings don't conflict (federated users authenticate
   at the IdP; keep Google-side enforcement for the break-glass accounts).
5. **Migrate users in waves.** Pilot with IT, then departments. During migration: communicate the
   new login flow, provide the IdP login URL prominently, and monitor login failures (Admin audit
   log + IdP logs) to catch mapping errors fast. Keep a rollback path (revert to Google-auth) per
   wave until stable.
6. **Handle the exceptions explicitly.** Service accounts, API users, and legacy clients that can't
   do SAML: document each, use app passwords only where unavoidable (prefer OAuth/service accounts),
   and review exceptions quarterly. Broad "SSO exemption" groups hollow out the control.
7. **Configure Google-as-IdP for SaaS apps.** For third-party apps: use Google's SAML app catalog
   (pre-integrated) or custom SAML/OIDC with the same rigor — verify assertion signing, attribute
   mapping, and just-in-time vs. pre-provisioned user handling. Prefer apps supporting SCIM or
   Google Directory sync for lifecycle.
8. **Automate provisioning and deprovisioning.** Connect HR → IdP → Google (and Google → SaaS via
   automated provisioning): new hires get accounts automatically, departures lose access within the
   SLA (target: same day). Test the deprovisioning path — orphaned SSO sessions after termination
   are the incident waiting to happen. Set session lengths appropriately.
9. **Monitor authentication centrally.** Ship Google login audit logs and IdP sign-in logs to the
   SIEM. Alert on: SSO bypass attempts (direct Google logins by non-break-glass users), IdP
   configuration changes, failed SAML assertions spikes, and impossible-travel or token anomalies.
   Correlate IdP and Google logs for the full authentication picture.
10. **Review and document.** Quarterly: exception list, app inventory (stale SAML apps removed), IdP
    configuration backup, and break-glass tests. Document the entire SSO architecture: directions,
    IdP config, attribute maps, exception register, and recovery procedures — the runbook for the
    next admin.

## Expected outputs
- SSO operational in the chosen direction(s) with verified SAML/OIDC configuration.
- Break-glass super-admins secured and tested before migration.
- MFA enforced at the IdP for all federated users; exceptions documented and reviewed.
- Automated provisioning/deprovisioning with tested departure flows.
- Centralized auth monitoring with bypass alerting and quarterly reviews.

## Pitfalls
- No break-glass: SSO misconfigurations lock out all admins. Direct-access recovery accounts are
  mandatory before touching SSO.
- MFA assumed but not enforced at the IdP: federated trust without IdP-side MFA is single-factor
  with extra steps. Verify enforcement.
- Attribute-mapping errors: NameID mismatches cause confusing login failures — validate with pilot
  users and check both sides' logs.
- Deprovisioning gaps: SSO centralizes auth but sessions and app tokens linger. Test the full
  departure flow including session revocation.
- Exception sprawl: every "can't do SSO" app needs a documented path forward or sunset plan, not a
  permanent pass.

## References
- Google Workspace Admin Help: SSO with third-party IdPs; Google as SAML IdP
- SAML 2.0 / OpenID Connect specifications (configuration semantics)
- NIST SP 800-63C (federation and assertions)
- CIS Google Workspace Benchmarks (SSO and authentication settings)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
