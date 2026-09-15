---
skill_id: cyber_securing_remote_access_to_ot_environment
name: Securing Remote Access to OT Environments
description: Control remote access into OT: jump hosts, MFA, session recording, and time-bound just-in-time access.
risk: info
permissions: []
requires_confirmation: false
tags: [ot, remote-access, access-control]
version: 1.0.0
---
## Purpose
Vendor and engineer remote access is one of the most exploited paths into OT environments. This playbook establishes controlled remote access: dedicated jump infrastructure, strong authentication, session recording, and time-bound approvals, so legitimate maintenance works without creating persistent inbound pathways.

## When to use
- Designing OT remote-access architecture.
- After incidents involving vendor VPNs or TeamViewer-style tools in OT.
- Compliance reviews of OT access controls.
- Onboarding new vendors requiring OT system access.

## Prerequisites
- Inventory of current remote-access paths (VPNs, vendor tools, modems).
- Identity provider supporting MFA and conditional access.
- Jump host infrastructure in the OT DMZ.
- Approval workflow for access requests.

## Procedure
1. Inventory and document every existing remote path into OT; remove unauthorized tools immediately.
2. Route all remote access through hardened jump hosts in the OT DMZ; no direct vendor-to-control-network connections.
3. Require MFA and device compliance for every remote session; use phishing-resistant MFA for privileged access.
4. Grant time-bound, ticket-linked access; credentials and network paths expire automatically.
5. Record sessions (video/keystroke) for privileged OT access; store recordings tamper-evident.
6. Restrict protocols and destinations per role: vendors reach only their systems, only required ports.
7. Monitor and alert on remote sessions: off-hours access, bulk data transfer, and configuration changes during sessions.
8. Review access grants quarterly; revoke vendor access the day contracts or work orders end.
9. Provision vendor accounts tied to specific work orders and disable them on completion.
10. Log emergency break-glass access retroactively with a mandatory post-incident review.
11. Test the full access workflow quarterly, including approval, provisioning, and revocation.

## Expected outputs
- Approved remote-access architecture with jump host design.
- Access request/approval workflow with time-bound grants.
- Session recording retention and monitoring rules.
- Work-order-linked vendor account lifecycle records.
- Break-glass usage log with post-incident reviews.
- Quarterly access-workflow test results.

## Pitfalls
- Always-on vendor VPNs are persistent attack paths; convert to just-in-time access.
- Shared vendor credentials destroy accountability; issue individual accounts.
- Session recording without review is theater; sample and investigate recordings regularly.
- Emergency break-glass access must exist but be heavily monitored and promptly rotated.
- Out-of-band approvals by phone must still be logged retroactively or they vanish from audit.
- Vendor support contracts that demand 24/7 access conflict with just-in-time models; renegotiate.
- Jump host patching windows are often skipped as 'too risky'; that is exactly when they are needed.
- Cellular out-of-band modems on OT equipment are forgotten remote paths; inventory them.

## References
- NIST SP 800-82 Rev. 3, Guide to OT Security.
- CISA guidance on OT remote access.
- ISA/IEC 62443-3-3 system security requirements.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
