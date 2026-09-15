---
skill_id: cyber_building_identity_federation_with_saml_azure_ad
name: Building Identity Federation with SAML and Entra ID
description: Practitioner guide to designing and deploying SAML-based single sign-on federation using Microsoft Entra ID as the identity provider.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, federation, authentication]
version: 1.0.0
---
## Purpose
Federating applications to a central identity provider with SAML reduces password sprawl, enables conditional access, and centralizes deprovisioning. This playbook covers designing the federation architecture, configuring Entra ID as the IdP, integrating service providers, and hardening the resulting trust relationships.

## When to use
- Consolidating application authentication onto a single identity provider.
- Replacing legacy credential stores or shared passwords with SSO.
- Enabling conditional access and MFA enforcement across SaaS applications.
- Auditing existing federation trusts for misconfiguration.

## Prerequisites
- Entra ID tenant with application-administrator rights.
- Application inventory: which apps support SAML, their entity IDs, and required claims.
- Certificate management process for signing certificates and rotation.
- Test users and a non-production environment for initial integration.

## Procedure
1. Inventory and prioritize applications. List apps, their SAML support, user populations, and business criticality; start with high-risk, high-user-count apps.
2. Design the claim strategy. Define standard claims (user principal name, groups, role) and app-specific claims; document the attribute mapping for each integration.
3. Register the application in Entra ID. Create the enterprise application, configure the SAML endpoints (entity ID, reply URL, sign-on URL), and assign test users.
4. Configure the service provider. Import the IdP metadata into the application, map claims to local roles, and verify signature validation is enforced.
5. Enforce security controls. Require signed assertions and encrypted assertions where supported; enable MFA and conditional access policies on the federated app.
6. Test end to end. Verify login, logout (single logout if supported), group-driven role mapping, and failure modes such as revoked users and expired sessions.
7. Plan certificate rotation. Document signing-certificate expiry, set calendar reminders, and rehearse rollover before certificates expire.
8. Monitor and review. Log sign-ins through Entra ID sign-in logs; review federation trusts quarterly for orphaned apps and stale assignments.

## Expected outputs
- Federated SSO for prioritized applications with documented claim mappings.
- Conditional access and MFA policies applied to federated apps.
- Certificate rotation plan and monitoring in place.

## Pitfalls
- Unsigned assertions or disabled signature validation enable token forgery.
- Overly broad group claims leak role information or grant excess privilege.
- Expired signing certificates cause sudden, total SSO outages; track them centrally.
- Orphaned enterprise applications from departed vendors remain as attack surface.

## References
- Microsoft Learn: SAML single sign-on with Microsoft Entra ID
- OASIS SAML 2.0 specifications
- NIST SP 800-63-3, Digital Identity Guidelines
- CISA guidance on phishing-resistant authentication
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
