---
skill_id: cyber_performing_cloud_incident_containment_procedures
name: Cloud Incident Containment Procedures
description: Contain active cloud incidents through credential revocation, network isolation, and resource quarantine.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, incident-response, containment]
version: 1.0.0
---

## Purpose

Containment in the cloud is about the identity plane and the API surface, not unplugging cables. An attacker with a valid access key can act from anywhere; a compromised instance can be rebuilt in minutes but the stolen credentials live on. This playbook gives a prioritized containment sequence for AWS-style cloud incidents: stop the bleeding (credentials, access paths), isolate affected resources without destroying evidence, and verify the attacker is actually locked out. Adapt the specific console/CLI actions to your provider.

## When to use

- Active suspected compromise of cloud credentials, instances, or serverless workloads.
- A GuardDuty/Defender finding indicates ongoing malicious API activity.
- A leaked key or exposed console password is reported and may already be in use.
- Ransomware or wiper activity is observed against cloud storage or volumes.
- As the containment runbook referenced by your broader cloud incident response plan.

## Prerequisites

- Break-glass responder access to the affected accounts, tested before the incident.
- Pre-built containment artifacts: quarantine security groups/VPCs, a forensic account, and documented CLI commands for key revocation.
- Authority to revoke credentials and isolate resources, with a defined approval path for production impact.
- Communication plan: who is notified, in what order, before containment actions that cause outages.
- Evidence-preservation awareness: containment must not destroy snapshots, logs, or volatile state needed for forensics.

## Procedure

1. **Revoke the attacker's access first.** Disable or delete compromised IAM users' access keys, revoke active sessions (attach a deny-all policy with a session-revocation condition or rotate the role's trust), rotate exposed secrets, and force re-authentication on federated identities. Do this before touching infrastructure — credentials are the fastest attack path.
2. **Block malicious network paths.** Attach quarantine security groups to suspect instances (deny all ingress/egress except a responder bastion path), remove public IPs or disassociate Elastic IPs, and revoke overly permissive security group rules the attacker may have added. For serverless, disable triggers and set function concurrency to zero rather than deleting the function.
3. **Quarantine affected resources.** Move suspect instances to an isolated subnet or apply SCPs/permission boundaries that freeze their API capabilities. Snapshot disks before any state change. For storage under active encryption/deletion, suspend versioning deletes via MFA-delete policies and enable Object Lock where available — then copy affected objects to the forensic account.
4. **Freeze identity-plane changes.** Temporarily restrict IAM write actions (via SCP or permission boundary) in the affected accounts to prevent the attacker from creating backdoor users, roles, or access keys while you work. Log every responder action for the timeline.
5. **Cut off data exfiltration paths.** Review and revoke resource policies (S3 bucket policies, KMS grants, role trust policies) that grant external principals access. Check for newly created VPC endpoints, peering connections, or PrivateLink shares the attacker may have built for quiet egress.
6. **Contain at the organization level if needed.** For multi-account compromise, apply organization-wide SCPs denying high-risk actions, suspend compromised member accounts' programmatic access, and engage the provider's abuse/security team for infrastructure-level blocks you cannot apply yourself.
7. **Verify lockout.** After containment, monitor CloudTrail in near-real time for the suspect identities: look for `AccessDenied` errors (proof the keys are dead) versus continued successful calls (proof you missed a session or key). Re-run your exposure queries (public buckets, open security groups) to confirm the attacker's changes are reverted.
8. **Hand off to eradication.** Document every containment action with timestamps for the forensic timeline, then transition: rotate all credentials that shared trust with the compromised ones, rebuild affected instances from known-good images, and remove attacker persistence (backdoor users, keys, policies, scheduled functions).

## Expected outputs

- Timestamped containment log: each action, who performed it, and its effect.
- Revoked/rotated credential inventory with verification that no valid attacker sessions remain.
- Quarantined resources with preserved snapshots and logs for forensics.
- Verification evidence: post-containment CloudTrail monitoring showing lockout.
- Handoff package for eradication: persistence found, rotations required, rebuild list.

## Pitfalls

- Deleting compromised resources instead of quarantining them — you lose forensic evidence and the attacker may already have other footholds.
- Revoking keys but missing active role sessions or federated tokens, leaving the attacker authenticated.
- Containment actions that cause a larger outage than the incident; sequence credential revocation before network isolation of production workloads where possible.
- Forgetting resource policies: an attacker with a bucket policy granting their external account access does not need your IAM credentials.
- Declaring containment complete without monitoring for continued API activity — verify, then verify again.

## References

- NIST SP 800-61, "Computer Security Incident Handling Guide" (containment phase)
- AWS documentation on IAM credential revocation and permission boundaries
- CISA guidance on cloud incident response and containment
- MITRE ATT&CK T1078 (Valid Accounts), T1136 (Create Account), T1486 (Data Encrypted for Impact)
- SANS cloud incident response cheat sheets
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
