---
skill_id: cyber_detecting_cryptomining_in_cloud
name: Detecting Cryptomining in Cloud
description: Detect unauthorized cryptomining in cloud accounts with billing, behavioral, and threat-intel signals.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, cryptomining, detection]
version: 1.0.0
---
## Purpose

Catch cryptominers in your cloud — whether from compromised credentials spinning up instances or malware on existing workloads. Mining burns money and signals deeper compromise; detecting it fast limits both the bill and the blast radius.

## When to use

- Monitoring cloud accounts for resource-abuse and compromise indicators.
- Investigating unexpected billing spikes or performance degradation.
- Hunting after a credential-leak finding (miners are the most common use of stolen cloud keys).
- Validating cloud guardrails that should prevent unauthorized compute.

## Prerequisites

- Billing/cost-anomaly alerting (AWS Cost Anomaly Detection, Azure Cost Management alerts, GCP budgets).
- GuardDuty / Defender for Cloud / Security Command Center enabled with crypto-mining finding types.
- CloudTrail/Activity Log centralized; compute inventory with owners.
- Authority to stop instances and revoke credentials on confirmation.

## Procedure

1. **Alert on billing anomalies first.** Configure cost-anomaly detection per account/project with tight thresholds on compute spend. Billing is often the first signal — a miner's economics depend on your money, and the bill doesn't lie. Route billing anomalies to the SOC, not just finance, with a compromise-investigation trigger.
2. **Detect mining-specific threat signals.** Enable and tune: GuardDuty `CryptoCurrency` finding types, Defender for Cloud's mining detections, and threat-intel matches on known mining-pool domains/IPs in DNS and flow logs. These are high-confidence — tune for immediate triage, not daily review.
3. **Hunt anomalous compute patterns.** Query for: instances in regions you never use, GPU instance types outside ML projects, sudden scale-out of compute, instances with no owner tags, and long-running high-CPU instances with no legitimate workload. Miners optimize for hash rate per dollar — their instance choices look nothing like your workloads.
4. **Detect mining on existing workloads.** On hosts/containers, alert on: sustained 100% CPU with unknown processes, known miner binaries and stratum-protocol connections, mining-pool DNS queries, and performance degradation correlated with new processes. EDR process + network correlation confirms it — CPU alone is not enough (legitimate batch jobs exist).
5. **Trace the intrusion vector.** Every miner got in somehow — determine how: compromised cloud credential (check CloudTrail for the instance creation), exploited public service, or malware on an existing host. The miner is the symptom; the access vector is the incident. Close it before declaring victory.
6. **Respond with cost containment.** On confirmation: stop/terminate the mining instances immediately (snapshot first for forensics if the vector is unclear), revoke the credentials used to create them, block mining-pool domains at DNS, and dispute/verify the billing impact. Then hunt: check every account for the same indicators — miners rarely limit themselves to one account.
7. **Prevent recurrence with guardrails.** Implement: SCP/organization policies denying GPU instance types except in approved accounts, required instance tagging (untagged instances get terminated automatically), approval workflows for new regions, and short-lived credentials to limit the value of stolen keys. Prevention here is mostly policy, not products.

## Expected outputs

- Billing-anomaly alerting routed to the SOC with compromise-investigation triggers.
- Mining-specific detections (threat intel, GuardDuty/Defender findings, compute-pattern hunting).
- Guardrail policies (GPU denials, tagging enforcement, region approvals) preventing recurrence.

## Pitfalls

- Billing alerts going only to finance — by the time finance notices, the incident is weeks old.
- CPU alerting without process context — you'll page on every legitimate batch job.
- Killing the miner without finding the vector — it comes back within hours.
- No cross-account hunting — the miner you found is rarely the only one.
- Treating it as "just" a billing issue — miners indicate compromise; investigate accordingly.

## References

- AWS / Azure / GCP documentation — cost anomaly detection and crypto-mining findings
- MITRE ATT&CK T1496 (Resource Hijacking)
- CISA guidance on cloud security and resource-hijacking response
- Cloud provider best-practice guides for compute guardrails
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
