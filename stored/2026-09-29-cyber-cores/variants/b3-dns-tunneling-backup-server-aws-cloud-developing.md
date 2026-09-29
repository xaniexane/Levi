---
skill_id: cyber_b3_dns_tunneling_backup_server_aws_cloud_developing
name: DNS Tunneling Defense for Backup Servers in AWS Cloud (Developing Maturity)
description: "DNS Tunneling defense playbook for Backup Servers in AWS Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, dns, c2, backup, ransomware, cloud, aws, maturity-developing]
version: 1.0.0
---
# DNS Tunneling Defense for Backup Servers in AWS Cloud (Developing Maturity)

## Purpose

DNS tunneling smuggles data or C2 inside DNS queries, abusing a protocol almost every network allows outbound. Detection hinges on query shape (length, entropy, volume, record types), not on blocklists. Applies to Backup Servers in AWS Cloud at Developing maturity.

## When to use

- Long, high-entropy subdomains (often 50+ chars) in DNS logs, unusual record types (TXT, NULL) at volume, or a single host generating thousands of queries to one domain.
- Beacon-like regularity in query timing to an obscure domain, or DNS queries for domains registered within the last 30 days.
- Responses with abnormally large TXT records relative to the query — data coming back down the tunnel.
- Lens: Best telemetry: job audit logs + admin-console access logs + integrity-check results. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Backup job definitions, run histories, and deletion/retention-change audit entries and Admin console logons and configuration exports; repository credential-change history; run `# conceptually (product CLIs differ):` then `backup-cli jobs list --failed --last 7d`.
3. **Analyze.** Decode a sample of tunneled queries/responses in a sandbox to determine direction and content: C2 instructions, exfiltrated data, or both. Then: Identify patient zero by earliest query timestamp, then hunt laterally: tunneling tools are often deployed to multiple hosts.
4. **Contain and harden.** Force all DNS through logged, filtered resolvers; block direct port-53 egress from endpoints and alert on non-standard DNS ports. Asset layer: Immutable storage, separate admin credentials with MFA, no domain-joined backup console if avoidable. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking the domain without finding the implant — the attacker rotates domains faster than you blocklist.
- Ignoring DNS over HTTPS (DoH): tunneled traffic inside DoH is invisible to passive DNS monitoring — log at the endpoint.

## References

- MITRE ATT&CK: T1071.004 (Command and Control: DNS)
- Vendor logging and hardening baselines for Backup Servers; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
