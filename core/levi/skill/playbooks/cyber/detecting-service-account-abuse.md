---
skill_id: cyber_detecting_service_account_abuse
name: Detecting Service Account Abuse
description: Detect compromise and misuse of service and machine accounts.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, service-accounts, detection]
version: 1.0.0
---
## Purpose

Service accounts are high-value targets: they often hold broad permissions, rarely use MFA, and their 'normal' is poorly documented — so abuse blends in. This playbook helps defenders baseline service-account behavior and detect the abuse patterns: interactive logons, impossible locations, privilege misuse, and credential theft indicators.

## When to use

- A service account shows logons from unexpected hosts or locations.
- You need a service-account security review across AD and cloud.
- Threat hunting after a compromise where service accounts were in scope.
- Compliance requires monitoring of non-human privileged identities.

## Prerequisites

- Inventory of service accounts: AD service accounts, managed identities, cloud service principals, API keys — with owners and permission scopes.
- Authentication logs: AD logons (4624/4768/4769), cloud sign-in logs, and API audit logs per platform.
- Baseline of legitimate service-account behavior: source hosts, schedules, accessed resources.
- Ownership records: every service account must have a human owner and a purpose.

## Procedure

1. Build the authoritative inventory first. Enumerate service accounts across AD, Entra ID/cloud IAM, and application-local stores. For each: owner, purpose, permission scope, authentication method, and expected source hosts. Ownerless or purposeless accounts are findings in themselves — you cannot detect abuse of an account whose normal is unknown.
2. Detect interactive and anomalous usage. Service accounts should never log on interactively: alert on interactive/RDP logons (Type 2/10), logons from user workstations, logons outside the account's normal schedule, and concurrent sessions from multiple locations. These are the highest-fidelity service-account abuse signals.
3. Detect privilege and scope anomalies. Alert on: a service account accessing resources outside its documented scope, privilege-escalation actions (role assignments, policy changes) by service accounts, authentication from new IPs/ASNs, and cloud service principals used outside their assigned workloads. Weight by permission level — a subscription-owner service principal acting oddly is critical.
4. Hunt credential-theft precursors. Service-account credentials get stolen from: config files and code repos (scan for embedded secrets), LSASS on hosts running services, and CI/CD systems. Correlate abuse alerts with secret-scanning hits and host-compromise indicators; a service account abused from an attacker host usually means its credential was harvested, not guessed.
5. Respond with service-aware discipline. Disable or rotate the credential immediately — but coordinate with the owner first, because breaking a production service at 2 AM creates its own incident. Prefer managed identities / workload identity federation over long-lived secrets, scope permissions to least privilege, and require approval workflows for permission changes on high-privilege service accounts.
6. Drive structural improvements: migrate to managed identities/gMSAs, eliminate embedded secrets via vaults, enforce conditional-access-style policies on service principals where supported, and run quarterly attestation where owners re-certify each account's necessity and scope.

## Expected outputs

- Authoritative service-account inventory with owners, purposes, and permission scopes.
- Abuse detections: interactive logons, off-schedule/off-host usage, scope anomalies, new-location auth.
- Secret-hygiene findings: embedded credentials, vault-migration backlog.
- Quarterly attestation process with owner sign-off.

## Pitfalls

- Alerting without a documented 'normal' per account produces unactionable noise — inventory first.
- Rotating a service-account credential without owner coordination breaks production — plan rotations.
- Managed identities and federated credentials change the detection model — update playbooks when migrating.
- Shared service accounts across environments defeat scoping — one account per purpose per environment.
- Service accounts used by humans 'temporarily' become permanent blind spots — prohibit and detect interactive use.

## References

- Microsoft Learn: securing service accounts, managed identities; MITRE ATT&CK T1078 (Valid Accounts) — https://attack.mitre.org/techniques/T1078/; NIST SP 800-63B (memorized secrets and look-up secrets)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
