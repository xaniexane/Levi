---
skill_id: cyber_building_role_mining_for_rbac_optimization
name: Building Role Mining for RBAC Optimization
description: Practitioner guide to discovering candidate roles from entitlement data and rationalizing role-based access control.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, access-management, analytics]
version: 1.0.0
---
## Purpose
Role-based access control fails when roles are designed by guesswork. Role mining analyzes actual entitlement and usage data to discover natural groupings of permissions, producing candidate roles grounded in how people really work. This playbook walks through data collection, analysis, role design, and migration without disrupting the business.

## When to use
- Cleaning up RBAC implementations that have decayed into per-user exceptions.
- Reducing administrative overhead of access provisioning.
- Preparing for identity-governance tooling that needs a clean role model.
- Responding to audit findings about excessive or undocumented entitlements.

## Prerequisites
- Entitlement exports from key applications and the identity provider.
- HR data: department, job title, location, manager hierarchy.
- Usage or last-access data where available to distinguish active from dormant rights.
- Sponsorship from application owners who must approve the resulting roles.

## Procedure
1. Collect entitlement data. Export user-to-permission mappings from in-scope applications; normalize permission names and formats.
2. Add organizational context. Join HR attributes (role, department, location) so candidate roles align with business structure.
3. Analyze permission clusters. Group users with similar entitlement sets; identify permissions that co-occur frequently and map cleanly to job functions.
4. Draft candidate roles. Propose roles with clear names, descriptions, and permission sets; keep the role count manageable (dozens, not thousands).
5. Validate with owners. Have application and business owners review each role for correctness and completeness; adjust for edge cases.
6. Handle exceptions explicitly. Permissions that fit no role go through a documented exception process with expiry, not back into per-user sprawl.
7. Migrate in waves. Move users to roles department by department, verifying access still works before decommissioning old entitlements.
8. Maintain the model. Re-run mining annually or after reorganizations; track role sprawl metrics and exception rates.

## Expected outputs
- Candidate role catalog with definitions, owners, and approval records.
- Migration plan and completion tracking.
- Ongoing role-hygiene metrics and review cadence.

## Pitfalls
- Mining on entitlement data alone reproduces existing sprawl; include usage data.
- Too many granular roles are as unmanageable as none; aim for meaningful groupings.
- Skipping owner validation produces roles nobody trusts or uses.
- One-time cleanup without maintenance decays within a year.

## References
- NIST IR 7817, A Profile for Role-Based Access Control
- NIST SP 800-162, Guide to Attribute Based Access Control (for context)
- ISO/IEC 27001 access control requirements
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
