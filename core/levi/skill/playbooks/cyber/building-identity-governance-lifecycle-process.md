---
skill_id: cyber_building_identity_governance_lifecycle_process
name: Building an Identity Governance Lifecycle Process
description: Practitioner guide to designing joiner-mover-leaver identity lifecycle processes with access reviews and least-privilege enforcement.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, governance, access-management]
version: 1.0.0
---
## Purpose
Orphaned accounts and stale entitlements are a leading cause of privilege misuse. This playbook builds the identity governance lifecycle -- joiner, mover, and leaver workflows plus periodic access reviews -- so that every account exists for a reason, holds only needed access, and disappears promptly when it should.

## When to use
- Standing up identity governance in an organization that still provisions accounts manually.
- Responding to audit findings about orphaned accounts or excessive privilege.
- Preparing for compliance frameworks that require access reviews (SOX, PCI DSS, ISO 27001).
- Integrating HR systems with identity provisioning for automation.

## Prerequisites
- Authoritative identity source (HR system) with reliable hire, transfer, and termination feeds.
- Inventory of applications, their owners, and their entitlement models.
- Identity governance tooling or a managed process with clear ownership.
- Executive sponsorship, since deprovisioning touches every department.

## Procedure
1. Define the lifecycle states. Document joiner, mover (department or role change), leaver, and extended-leave states, with required actions and SLAs for each.
2. Connect the HR feed. Establish the authoritative source and the sync cadence; handle edge cases such as rehires, contractors, and name changes.
3. Automate joiner provisioning. Use role-based templates so new hires receive standard access on day one without manual ticket handling.
4. Build mover workflows. Trigger entitlement re-evaluation on role changes; remove access tied to the old role within a defined window.
5. Enforce leaver deprovisioning. Disable accounts within hours of termination, revoke sessions and tokens, and archive or transfer data ownership.
6. Implement access reviews. Run periodic certification campaigns where managers and application owners attest to entitlements; auto-revoke unreviewed access.
7. Handle exceptions. Provide a documented, time-bound exception process for access outside the standard roles, with mandatory expiry.
8. Measure and report. Track metrics such as time to deprovision, orphaned-account count, and review completion rates; report to leadership quarterly.

## Expected outputs
- Documented JML processes with SLAs and owners.
- Automated provisioning and deprovisioning connected to the HR source.
- Access-review program with completion tracking and auto-revocation rules.
- Governance metrics reported to leadership.

## Pitfalls
- Stale HR data silently breaks the whole lifecycle; validate feed quality first.
- Mover processes are the most neglected; without them, privilege accumulates with every transfer.
- Reviews without consequences (no auto-revocation) become rubber-stamp exercises.
- Service and shared accounts fall outside HR feeds and need a separate ownership model.

## References
- NIST SP 800-63-3, Digital Identity Guidelines
- ISO/IEC 27001 access control requirements
- Microsoft Learn: Microsoft Entra ID Governance documentation
- CIS Controls: account management safeguards
