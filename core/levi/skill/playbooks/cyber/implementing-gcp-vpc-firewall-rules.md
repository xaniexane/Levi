---
skill_id: cyber_implementing_gcp_vpc_firewall_rules
name: GCP VPC Firewall Rules
description: Design least-privilege GCP VPC firewall rules with hierarchy, logging, and drift control.
risk: moderate
permissions: []
requires_confirmation: true
tags: [gcp, networking]
version: 1.0.0
---
## Purpose
VPC firewall rules are the network segmentation of GCP: overly broad rules (0.0.0.0/0 to everything,
allow-all egress) are how breaches spread and data leaves. This playbook implements least-privilege
firewall rules with hierarchical policies, service-account-based targeting, and logging — replacing
flat allow-anything with intentional, auditable connectivity. Confirmation is required: firewall
changes can sever production traffic.

## When to use
- Segmenting GCP networks to contain breaches and meet compliance network-isolation requirements.
- After incidents involving lateral movement or exfiltration through permissive firewall rules.
- Cleaning up legacy allow-all rules accumulated over years.
- Before production launches of sensitive workloads on GCP.
- As the network layer of GCP defense-in-depth (with org policies and private service access).

## Prerequisites
- Network inventory: VPCs, subnets, routes, peerings, and current firewall rules with their purposes
  (or lack thereof).
- Service-account and tag strategy: firewall rules target service accounts and network tags —
  inconsistent labeling makes least-privilege impossible.
- Flow logging: VPC Flow Logs enabled for baselining actual traffic.
- Change control with fast rollback: rule mistakes cause outages; revert must be quick.
- A non-production VPC mirroring production for rule testing.

## Procedure
1. **Inventory and classify existing rules.** Export all firewall rules; classify each: documented
   purpose and still needed, overly broad (0.0.0.0/0 sources, all-ports), unused (no flow-log hits
   in 90 days), or unknown. Unknown rules are findings — every rule needs an owner and
   justification.
2. **Establish hierarchical firewall policies.** Use hierarchical firewall policies at org/folder
   level for universal denies (deny all ingress from the internet to non-edge, deny known-bad ports
   like 23/135-139/445 broadly) and VPC-level rules for workload specifics. Hierarchy prevents
   project-level rules from undermining baselines.
3. **Baseline actual traffic.** Analyze VPC Flow Logs for 2-4 weeks: which sources talk to which
   destinations on which ports. The flow data — not documentation — defines the least-privilege rule
   set. Identify undocumented dependencies to codify, not to break.
4. **Write least-privilege rules.** Replace broad rules with: specific source ranges or (better)
   source service accounts/tags, specific destination ports, and explicit protocols. Prefer
   service-account-based rules over IP-based where workloads are dynamic. Deny by default: end each
   policy chain with an explicit deny-all (egress too, for sensitive tiers) with logging.
5. **Handle special cases deliberately.** Health checks: allow Google's health-check ranges
   explicitly. IAP: allow IAP proxy ranges for admin access instead of opening SSH/RDP to the world.
   DNS/metadata: allow required Google API and metadata server access explicitly. Each special case
   documented — they're the rules auditors question.
6. **Enable firewall-rules logging.** Turn on logging for deny rules (all) and key allow rules
   (sensitive tiers). Ship to the SIEM: denied-connection logs are intrusion-attempt signal;
   allowed-but-unexpected logs reveal policy gaps. Alert on deny spikes and denied egress to
   external destinations.
7. **Test in non-production first.** Apply the new rule set to the mirror VPC with production-like
   traffic (load tests, synthetic transactions). Verify legitimate flows pass and unauthorized
   attempts are denied and logged. Fix rules, not tests.
8. **Roll out VPC by VPC.** Enforce per VPC in waves: non-critical first, production last. Each
   wave: apply, monitor deny logs intensely for 48 hours, keep one-click rollback ready. Communicate
   maintenance windows for sensitive changes.
9. **Control drift.** Alert on firewall-rule changes outside the IaC/GitOps pipeline; reconcile
   rules against the declared baseline weekly. Firewall rules managed by click-ops drift within
   months — IaC (Terraform) with peer review is the long-term answer.
10. **Review quarterly.** Audit: overly broad rules that crept back, unused rules (no flow hits —
    remove), new workloads without proper rules, and hierarchical policy effectiveness. Tighten
    progressively; report the rule-hygiene trend.

## Expected outputs
- Inventoried, classified, and least-privilege firewall rules with hierarchical policies.
- Flow-log-baselined rule sets tested in non-production before enforcement.
- Firewall logging shipped to SIEM with deny-spike and exfiltration alerting.
- IaC-managed rules with drift detection and fast rollback.
- Quarterly rule-hygiene reviews with tightening trends.

## Pitfalls
- Enforcing without flow-log baselining: undocumented dependencies break. Measure actual traffic
  first.
- Forgetting health checks and IAP ranges: the most common self-inflicted outages — codify Google's
  special ranges explicitly.
- IP-based rules for dynamic workloads: IPs churn; service-account/tag-based rules survive
  rescheduling. Use identity, not addresses.
- Click-ops management: rules drift, ownership fades, and nobody knows why port 8080 is open. IaC
  with review, always.
- Allow-all egress: the exfiltration highway. Sensitive tiers get explicit egress allows with
  deny-all-logged default.

## References
- Google Cloud VPC firewall documentation (rules, hierarchical policies, logging)
- CIS Google Cloud Platform Foundations Benchmark (networking controls)
- NIST SP 800-53 SC-7 (boundary protection)
- MITRE ATT&CK T1048, T1021 (exfiltration, remote services — what segmentation constrains)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
