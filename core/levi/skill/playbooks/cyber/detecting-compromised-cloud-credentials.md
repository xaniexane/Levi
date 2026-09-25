---
skill_id: cyber_detecting_compromised_cloud_credentials
name: Detecting Compromised Cloud Credentials
description: Detect stolen cloud credentials across AWS, Azure, and GCP with cross-signal behavioral analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, identity, detection]
version: 1.0.0
---
## Purpose

Detect compromised cloud credentials — access keys, service principals, service-account keys — across providers by correlating the behavioral signals that distinguish attacker use from legitimate use. Stolen credentials are the most common cloud initial-access vector; this is the detection that matters most.

## When to use

- Building multi-cloud credential-compromise detection.
- Investigating a suspected key leak or phishing of cloud admins.
- Hunting for active misuse after a secrets-scanning finding.
- Validating that credential-rotation and short-lived-credential initiatives are working.

## Prerequisites

- Centralized control-plane logs: CloudTrail (AWS), Activity Log + Entra sign-ins (Azure), Audit Logs (GCP).
- Inventory of credential types in use: long-lived keys, service principals, workload identities, and their owners.
- Baselines per credential: normal source IPs, APIs, hours, and user agents.
- Authority to revoke credentials immediately on confirmation.

## Procedure

1. **Inventory all long-lived credentials and rank by risk.** List every static access key, service-principal secret, and GCP service-account key: owner, age, last use, permissions. Keys older than 90 days, keys with admin permissions, and keys with no owner are your highest-risk population — monitor them hardest and rotate them first.
2. **Detect impossible and anomalous usage.** Alert on: usage from geographies the credential never touched, new ASNs (especially datacenter/VPN/Tor), usage at hours inconsistent with the workload, and user-agent changes (a key used by Terraform suddenly used by `aws-cli` manually). Each provider's logs carry these signals — build the detections per provider, correlate centrally.
3. **Detect the attacker's validation sequence.** Attackers test stolen credentials before using them: `sts:GetCallerIdentity` / equivalent identity-check calls from new sources, followed by enumeration (`List*`, `Describe*`). Alert on identity-check-then-enumeration sequences from new sources — this is the compromise confirmation, often hours before real damage.
4. **Monitor for credential-lifecycle tampering.** Alert on: new keys created on existing users/service principals (persistence), keys created by unusual actors, logging disabled around credential use (CloudTrail StopLogging, diagnostic-setting deletion), and MFA removed from the owning human account. Attackers secure their access — watch for it.
5. **Correlate across providers and with human identity.** Join signals: the same source IP using credentials in two clouds, a phished human account whose cloud keys activate within hours, and credential use concurrent with impossible-travel on the owner's identity. Multi-signal correlation separates compromise from travel and VPN artifacts.
6. **Hunt proactively, don't just alert.** Weekly: query for keys unused in 90 days (rotate or delete), keys used from multiple distant geographies, and service principals with new permission grants. Monthly: review the long-lived credential inventory trend — the count should be shrinking as you migrate to short-lived workload identities.
7. **Respond with full credential kill.** On confirmation: revoke all sessions/tokens (not just the key — kill active sessions), deactivate the key (preserve for forensics, don't delete), rotate every credential the attacker could have touched, audit the full activity window for what was accessed/exfiltrated, and determine the leak source (repo? phishing? laptop?) to close it.

## Expected outputs

- A risk-ranked long-lived credential inventory with anomalous-usage detections per provider.
- Attacker-validation-sequence detection (identity-check → enumeration from new sources).
- Credential-kill response runbooks and a shrinking long-lived-credential trend via short-lived migration.

## Pitfalls

- Monitoring only one cloud — attackers use every credential they steal, across providers.
- Key rotation without session revocation — the attacker's session survives.
- Deleting instead of deactivating — you lose the ability to detect continued use.
- No leak-source investigation — the same exposure re-compromises the replacement key.
- Treating workload-identity migration as optional — long-lived keys are the problem; short-lived identities are the fix.

## References

- AWS / Microsoft / Google Cloud documentation on credential monitoring and rotation
- MITRE ATT&CK T1552 (Unsecured Credentials) and T1078 (Valid Accounts)
- CISA guidance on cloud credential hygiene
- NIST SP 800-63B (authentication lifecycle) and SP 800-207 (workload identity)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
