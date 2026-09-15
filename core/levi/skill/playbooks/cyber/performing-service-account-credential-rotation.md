---
skill_id: cyber_performing_service_account_credential_rotation
name: Service Account Credential Rotation
description: Rotate service account credentials safely with dependency mapping, staged rollout, and rollback planning.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, rotation, operations]
version: 1.0.0
---

## Purpose
- Reduce the window of exposure for service account credentials through regular rotation.
- Prevent the outages that make teams afraid to rotate, through careful dependency mapping.
- Build a repeatable rotation process instead of a heroic one-off effort.

## When to use
- On a defined schedule, typically every 90 to 180 days depending on risk.
- Immediately when a service account credential is suspected compromised or exposed.
- When onboarding service accounts into a PAM vault for the first time.
- After personnel changes involving staff who knew service account credentials.

## Prerequisites
- A complete dependency map for each account: where the credential is stored and which systems use it.
- A maintenance window with application owners on standby.
- Backup of current credentials in a secure vault in case rollback is needed.
- Monitoring in place to detect authentication failures during the rotation.

## Procedure
1. Confirm the dependency map is current: scan code, configs, CI secrets, and documentation for the credential.
2. Notify application owners of the rotation window and the rollback plan.
3. Generate the new credential meeting complexity and length requirements.
4. Stage the new credential in a vault; do not distribute it through chat or email.
5. Update consumers in dependency order, starting with the least critical systems.
6. Activate the new credential and monitor authentication logs for failures.
7. Keep the old credential valid briefly where the platform allows, to catch missed consumers.
8. Verify each application functions correctly with the new credential before closing the window.
9. Revoke the old credential and confirm no successful authentications use it afterward.
10. Document the rotation: date, systems touched, issues encountered, and lessons for next time.
11. Where possible, migrate to managed identities or automated rotation so the manual process becomes unnecessary.
12. Schedule the next rotation and assign an owner.

## Expected outputs
- Rotated credentials with verification that all consumers work.
- An updated dependency map reflecting any newly discovered consumers.
- A rotation runbook improved with lessons learned.
- Automation coverage metrics showing which rotations no longer need humans.
- A break-glass procedure for emergency rotations outside the schedule.

## Pitfalls
- Missing a consumer hidden in a script or config file, causing a delayed outage after the old credential expires.
- Rotating without a rollback plan; keep the old credential recoverable until verification is complete.
- Treating rotation as a substitute for vaulting and least privilege; rotate and improve the architecture together.
- Rotating the vault copy but not the actual account credential, or vice versa.

## References
- NIST SP 800-57 key management guidance
- NIST SP 800-63 guidance on authenticator lifecycle management
- Vendor PAM documentation on automated rotation
- NIST SP 800-53 control IA-2 on identification and authentication
- Cloud provider guidance on managed identities
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
