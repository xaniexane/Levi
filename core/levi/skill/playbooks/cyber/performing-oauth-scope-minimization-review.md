---
skill_id: cyber_performing_oauth_scope_minimization_review
name: OAuth Scope Minimization Review
description: Audit OAuth application registrations and granted scopes to enforce least privilege and remove excessive permissions.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, oauth, hardening]
version: 1.0.0
---

## Purpose
- Reduce the blast radius of compromised OAuth applications by ensuring each app holds only the scopes it truly needs.
- Find over-privileged, stale, or rogue application registrations across identity providers.
- Build an approval and review process that keeps scopes minimal as new integrations arrive.

## When to use
- During identity security reviews or access recertification cycles.
- After an incident involving a compromised third-party integration or leaked client secret.
- Before onboarding a new SaaS integration that requests broad OAuth permissions.
- When preparing for audits that examine application-level access to corporate data.

## Prerequisites
- Administrative access to the identity provider's app registration inventory (Entra ID, Okta, Google Workspace, or equivalent).
- An inventory of approved applications with business owners and documented justifications.
- Logs of application consent grants and admin consent workflows.
- Understanding of the scopes each platform exposes and what data each scope unlocks.

## Procedure
1. Export the full application registration inventory, including client IDs, owners, creation dates, and granted scopes.
2. Flag applications with high-privilege scopes such as mail read, directory read-all, or impersonation-style delegated permissions.
3. For each flagged app, verify the business justification with the owner and check whether the scope is actually exercised in sign-in and API logs.
4. Identify stale registrations: apps with no sign-ins for 90 days, orphaned owners, or scopes granted for one-time projects.
5. Review admin consent grants to confirm each followed the approval workflow and was not a bypass.
6. Check credential hygiene on each app: expiring or long-lived client secrets, unused certificates, and redirect URIs that look suspicious.
7. Reduce scopes to the minimum set the app demonstrably uses, or remove the registration entirely for unjustified apps.
8. Tighten consent policy: require admin consent for high-risk scopes and publish a list of pre-approved low-risk scopes.
9. Set up alerting for new app registrations, new high-privilege scope grants, and secret additions.
10. Document the review with decisions per app and schedule the next recertification cycle.
11. Verify that conditional access and continuous access evaluation cover the remaining high-privilege apps.
12. Re-run the inventory after each change window to confirm reductions actually took effect.

## Expected outputs
- A reviewed application inventory with a keep, reduce, or remove decision for every registration.
- Removed or de-scoped applications with change records.
- Consent policy updates and monitoring rules for new registrations.

## Pitfalls
- Breaking production integrations by removing scopes without checking usage logs and warning owners first.
- Reviewing only delegated user scopes while ignoring application (client-credentials) permissions, which are often broader.
- Missing shadow IT apps registered by users before admin consent enforcement was turned on.
- Forgetting service principals used by automation, which often hold the broadest scopes.

## References
- CISA Secure Cloud Business Applications guidance
- Microsoft Learn documentation on Entra ID application permissions and consent
- OAuth 2.0 Security Best Current Practice, RFC 9700
- NIST SP 800-63 Digital Identity Guidelines on federation and assertions
- CISA guidance on securing cloud application integrations
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
