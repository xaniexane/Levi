---
skill_id: cyber_deploying_cloud_deception_with_decoy_resources
name: Deploying Cloud Deception with Decoy Resources
description: Seed believable decoy resources across cloud accounts that generate high-fidelity alerts when attackers interact.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, cloud, detection]
version: 1.0.0
---
## Purpose

Deploy cloud-native decoys — fake S3 buckets, credentials, databases, and API keys — that look like valuable targets but exist only to detect intruders. In cloud environments where perimeter visibility is thin, decoys are often the first reliable signal of compromise.

## When to use

- Detecting compromised cloud credentials or console access (the decoys catch what CloudTrail misses in the noise).
- Early warning for data-staging and exfiltration attempts in AWS, Azure, or GCP.
- Validating cloud detection coverage with self-testing tripwires.
- Environments with broad cloud footprints where reviewing every API call is infeasible.

## Prerequisites

- Cloud admin rights in the target accounts/subscriptions and a tagging/labeling convention for decoys.
- CloudTrail (or Azure Activity Log / GCP Audit Logs) enabled with centralized log delivery to the SIEM.
- Alerting pipeline that can distinguish decoy interactions from normal API traffic.
- Written authorization and a decoy inventory with owners — decoys are production resources.

## Procedure

1. **Choose decoy types matched to attacker goals.** Deploy a mix: (a) S3 buckets / storage containers with enticing names (`finance-backups`, `customer-data-archive`) containing fake-but-plausible files; (b) IAM access keys for a fake user, "leaked" in a realistic location (a decoy code repo, a fake config file in a bucket); (c) a decoy RDS/database with a tempting name and fake records; (d) fake API tokens in a decoy secrets-manager entry. Each should look like something an attacker would prioritize.
2. **Make decoys discoverable the way attackers discover things.** Attackers enumerate: list buckets, describe instances, read repos. Ensure decoys appear in those listings with realistic metadata (creation dates in the past, plausible tags, realistic sizes). A decoy that doesn't show up in enumeration is never found.
3. **Keep decoys inert and isolated.** Decoy credentials must grant access to nothing real — scope IAM policies to the decoy resources only, or make the keys monitored-but-useless. Decoy databases contain synthetic data only, never real customer or employee data. A decoy that leaks real data is a liability, not a control.
4. **Instrument with cloud-native detection.** Alert on: any `GetObject`/`ListObjects` on decoy buckets, any `sts:AssumeRole` or API call with decoy credentials, any connection to the decoy database, and any read of the decoy secret. Use CloudTrail event selectors / Azure diagnostic settings / GCP log sinks filtered to the decoy ARNs, and route matches to the SOC as high-severity.
5. **Add canary tokens for exfiltration detection.** Embed canary tokens (unique URLs, AWS keys from canary-token services, or custom webhook beacons) inside decoy files. If a file is exfiltrated and opened externally, the token fires — giving you detection even after data leaves your cloud.
6. **Test every tripwire before relying on it.** From a test role, list the decoy bucket, attempt to use the decoy key, and query the decoy database. Verify each action produces the expected alert within the SIEM's SLA. Untested decoys are decoration.
7. **Treat triggers as incidents and rotate.** Any decoy interaction means unauthorized cloud access until proven otherwise — scope immediately (which principal, from where, what else did it touch). Rotate decoy credentials and refresh decoy content quarterly so they stay plausible and any leaked-then-abandoned tokens don't linger.

## Expected outputs

- A documented decoy inventory (buckets, keys, databases, secrets) with owners, locations, and review dates.
- High-severity SIEM alerts on any decoy interaction, tested end-to-end.
- Canary tokens embedded for post-exfiltration detection; quarterly rotation.

## Pitfalls

- Decoys with real data or real permissions — the most dangerous possible misconfiguration.
- Decoy names that don't match your conventions — attackers filter for plausibility; `honeypot-bucket-123` fools no one.
- Alerting on the security team's own tests without a suppression window — test during announced windows and tag test traffic.
- Forgetting decoys exist during cloud migrations — orphaned decoys in old accounts generate confusion or get deleted silently.
- Over-deploying: dozens of decoys nobody maintains become stale and get ignored when they fire.

## References

- MITRE Engage (engage.mitre.org) — deception and adversary engagement planning
- AWS documentation — CloudTrail event selectors, IAM policy scoping, S3 logging
- Microsoft Learn — Azure Activity Log alerts and Microsoft Defender for Cloud
- NIST SP 800-53 SC-26 (honeypots) and SI-4 (system monitoring)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
