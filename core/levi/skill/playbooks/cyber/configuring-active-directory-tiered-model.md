---
skill_id: cyber_configuring_active_directory_tiered_model
name: Configuring the Active Directory Tiered Administration Model
description: Practitioner guide to implementing tiered administration (Tier 0/1/2) to contain credential theft and limit lateral movement in Active Directory.
risk: info
permissions: []
requires_confirmation: false
tags: [active-directory, hardening, identity]
version: 1.0.0
---
## Purpose
When a domain-admin credential lives on a workstation, one compromise becomes domain compromise. The tiered model separates administration into Tier 0 (domain controllers and identity systems), Tier 1 (servers), and Tier 2 (workstations), with credential isolation between tiers. This playbook implements that model step by step.

## When to use
- Reducing lateral-movement risk in an Active Directory environment.
- Responding to assessments that found excessive privileged-credential exposure.
- Building a privileged-access strategy aligned with modern best practices.
- Preparing for or recovering from an AD compromise.

## Prerequisites
- Complete inventory of privileged accounts and where their credentials are used.
- Understanding of current administrative workflows and tools.
- Dedicated privileged-access workstations (PAWs) or equivalent for Tier 0.
- Change-management support, since admin workflows will change.

## Procedure
1. Inventory privilege. List all accounts with administrative rights, their tiers of use, and where credentials currently exist (workstations, servers, scripts).
2. Define the tiers. Document what belongs in each tier: Tier 0 for DCs and identity infrastructure, Tier 1 for member servers and applications, Tier 2 for workstations and user devices.
3. Create tiered admin accounts. Provision separate accounts per tier (no single account administering across tiers); name them clearly.
4. Enforce credential isolation. Use GPOs to deny Tier 0 credentials on lower tiers (deny logon policies); ensure Tier 0 admins use dedicated secure workstations.
5. Clean up privileged groups. Remove unnecessary members from Domain Admins, Enterprise Admins, and Schema Admins; use just-in-time elevation where possible.
6. Protect service accounts. Move Tier 0 service accounts to managed service accounts or group managed service accounts with strong, rotated credentials.
7. Monitor tier violations. Alert on Tier 0 credentials appearing on Tier 1 or 2 systems; treat violations as security incidents.
8. Maintain the model. Review tier assignments after every infrastructure change; include tiering in admin onboarding training.

## Expected outputs
- Tiered account structure with documented tier boundaries.
- GPO-enforced credential isolation and monitoring.
- Reduced privileged-group membership with ongoing review.

## Pitfalls
- Creating tiered accounts but letting old habits persist defeats the model; enforce technically.
- Missing service accounts and scripts that embed privileged credentials.
- Tier 0 work without dedicated secure workstations reintroduces exposure.
- Overly complex tiering that admins bypass; keep it usable.

## References
- Microsoft Learn: securing privileged access and tiered administration model
- MITRE ATT&CK: T1078 (Valid Accounts), credential-access techniques
- CISA guidance on Active Directory hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
