---
skill_id: cyber_conducting_cloud_incident_response
name: Conducting Cloud Incident Response
description: Practitioner guide to investigating and containing security incidents in cloud environments (AWS, Azure, GCP).
risk: low
permissions: []
requires_confirmation: false
tags: [incident-response, cloud, forensics]
version: 1.0.0
---
## Purpose
Cloud incidents differ from on-premises ones: no physical hosts to image, ephemeral resources, and control-plane logs as the primary evidence. This playbook adapts incident response to the cloud -- scoping across accounts and subscriptions, collecting control-plane and data-plane evidence, containing via cloud-native controls, and recovering without reintroducing the compromise.

## When to use
- Responding to suspected compromise of cloud accounts, workloads, or identities.
- Investigating anomalous API activity, cryptomining, or data-access alerts in the cloud.
- Building cloud-specific IR runbooks before an incident occurs.
- Coordinating with a cloud provider's security team.

## Prerequisites
- Centralized cloud audit logging enabled (CloudTrail, Azure Activity Log, GCP Audit Logs) with retention.
- Defined roles with permission to isolate resources, revoke keys, and snapshot volumes.
- Inventory of accounts, subscriptions, and projects with ownership.
- Contact path to the cloud provider for support escalation.

## Procedure
1. Scope the blast radius. Identify affected accounts, regions, resources, and identities; determine whether the compromise spans the control plane, workloads, or both.
2. Preserve control-plane evidence. Ensure audit logs are retained and immutable; export relevant log windows before retention or attacker tampering becomes an issue.
3. Snapshot before containing. Take EBS snapshots, VM disk snapshots, or memory captures of suspect workloads where feasible before termination.
4. Contain with cloud controls. Revoke compromised keys and sessions, isolate instances with security groups, disable compromised identities, and quarantine storage.
5. Investigate identity first. In cloud incidents, start with IAM: which principals acted, what policies allowed it, and whether persistence (new users, keys, roles) was created.
6. Determine data impact. Review data-plane logs (S3 access, database audit) to assess exfiltration or modification; involve legal early if customer data is affected.
7. Eradicate and recover. Remove persistence, rotate all potentially exposed credentials, rebuild compromised workloads from known-good images, and re-enable with hardened configuration.
8. Harden and learn. Close the gaps that enabled access (overly broad IAM, public storage, missing MFA); feed lessons into detection engineering.

## Expected outputs
- Scoped incident record with affected accounts, resources, and identities.
- Preserved logs and snapshots with chain of custody.
- Eradication and recovery verification, plus hardening actions.

## Pitfalls
- Terminating instances before snapshotting destroys the only evidence.
- Focusing on workloads while missing control-plane persistence (rogue IAM users).
- Assuming logs exist; verify logging was enabled before you need it.
- Recovering by restarting the same misconfigured resources.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- CISA cloud incident response guidance
- AWS, Microsoft, and Google Cloud incident response documentation
- MITRE ATT&CK cloud matrices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
