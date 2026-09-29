---
skill_id: cyber_b3_lateral_movement_rdp_api_gateway_aws_cloud_developing
name: RDP Lateral Movement Defense for API Gateways in AWS Cloud (Developing Maturity)
description: "RDP Lateral Movement defense playbook for API Gateways in AWS Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, web, api, cloud, aws, maturity-developing]
version: 1.0.0
---
# RDP Lateral Movement Defense for API Gateways in AWS Cloud (Developing Maturity)

## Purpose

RDP is both an admin tool and the attacker's favorite lateral highway. Compromised credentials plus unrestricted RDP equals domain-wide movement that looks almost legitimate in the logs. Applies to API Gateways in AWS Cloud at Developing maturity.

## When to use

- 4624 type-10 (RDP) logons from a workstation to servers or other workstations outside the user's normal admin pattern.
- RDP sessions at unusual hours, from hosts the account never logged into before, or with clipboard/drive redirection moving tools onto the target.
- TerminalServices-LocalSessionManager events (21/25) on targets without a matching helpdesk ticket or change record.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** Correlate RDP logons with the source host's compromise timeline to distinguish attacker sessions from legitimate admin work. Then: Check for credential harvesting on each RDP target: LSASS access or SAM reads following the session indicate theft.
4. **Contain and harden.** RDP restricted to jump hosts/bastions with MFA; Network Level Authentication enforced; no direct workstation-to-server RDP. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Allowing 'temporary' RDP exceptions that become permanent lateral paths.
- Missing RDP-based movement because you only hunted SMB — attackers use whatever is open.

## References

- MITRE ATT&CK: T1021.001 (Lateral Movement: Remote Desktop Protocol)
- Vendor logging and hardening baselines for API Gateways; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
