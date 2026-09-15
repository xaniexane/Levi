---
skill_id: cyber_performing_credential_access_with_lazagne
name: Detecting LaZagne-Style Credential Access
description: Audit endpoint credential exposure recoverable by tools like LaZagne and detect their use.
risk: low
permissions: []
requires_confirmation: false
tags: [endpoint, detection, credentials]
version: 1.0.0
---

## Purpose

LaZagne is an open-source credential-recovery tool that extracts stored passwords from browsers, Wi-Fi profiles, email clients, and application configs on a machine it runs on. Attackers use it post-compromise to harvest credentials at scale; defenders can use the same knowledge to answer two questions: where on my endpoints are credentials stored in recoverable form, and would I detect this tool running? This playbook covers auditing your own endpoints for recoverable credential stores, detecting LaZagne-style execution, and reducing what is recoverable. All assessment is limited to endpoints you own.

## When to use

- Post-compromise assessment: determining what credentials an attacker could have harvested from an endpoint.
- Proactive audit of credential hygiene on corporate workstations and servers.
- Building detections for credential-access tooling (ATT&CK T1003/T1555).
- Evaluating whether browser password managers and local secret stores meet policy.
- Purple-team validation that EDR rules fire on credential-dumping behavior.

## Prerequisites

- Authorization to run credential-recovery auditing on the in-scope endpoints (this touches sensitive material — get explicit approval and define handling rules).
- Representative test endpoints matching production builds (OS, browser versions, EDR configuration).
- EDR/Sysmon telemetry from endpoints for detection validation.
- Inventory of approved credential stores (enterprise password manager, OS keychain with policy) vs. prohibited ones.
- Secure handling procedure for any credentials recovered during the audit: they must be rotated, never retained.

## Procedure

1. **Map recoverable credential stores.** On a representative test endpoint you own, inventory where credentials persist: browser password stores (Chrome Login Data, Firefox logins.json), OS credential managers, Wi-Fi profiles, RDP/SSH client configs, email client profiles, and application config files with embedded passwords. Document which are encrypted with user context (DPAPI) versus effectively plaintext.
2. **Assess recoverability under your threat model.** Determine what an attacker with user-level vs. SYSTEM-level access could extract. DPAPI-protected stores fall to tools running as the user; LSA secrets and SAM require elevation. This bounds the blast radius of a compromised endpoint honestly.
3. **Detect the tooling, not just the hash.** Build detections for LaZagne-style execution: process creation for known binary names and renamed variants, command lines with module flags, access to browser Login Data files by unusual processes, DPAPI `CryptUnprotectData` call patterns from non-browser processes, and Sysmon events for LSASS-adjacent reads. Hash-based detection alone fails against recompiled variants — use behavior.
4. **Validate detection in a controlled test.** In an isolated lab (never production), execute the recovery tool against a sacrificial endpoint and confirm each detection fires end-to-end: EDR alert, SIEM ingestion, and analyst queue. Tune out the false positives from legitimate software that touches the same stores (some backup and migration tools do).
5. **Reduce what is recoverable.** Drive remediation: migrate users to an enterprise password manager with no local browser storage, enforce OS keychain/disk encryption, remove embedded passwords from scripts and configs (replace with vault-retrieved secrets), and disable credential caching (e.g., limit cached logons, disable WDigest).
6. **Plan for the compromised-endpoint scenario.** Define the playbook for "attacker ran credential recovery on this host": which credentials are presumed compromised (all user-context secrets on the box), the rotation scope (user passwords, service accounts used from the host, Wi-Fi PSKs), and the evidence to collect (tool artifacts, timestamps of execution).
7. **Monitor continuously.** Alert on new recoverable-store creation (e.g., a browser profile appearing on a server), mass DPAPI unprotect events, and execution of unsigned binaries that touch credential stores.

## Expected outputs

- An inventory of recoverable credential stores on standard endpoint builds, by privilege level required.
- Behavioral detections for credential-recovery tooling, validated in lab.
- Remediation plan: password-manager migration, vault adoption, caching reductions.
- A compromised-endpoint credential rotation playbook with defined scope.
- Handling rules ensuring audited credentials are rotated, never retained.

## Pitfalls

- Running recovery tools on production endpoints or retaining recovered passwords — the audit itself becomes a credential-exposure incident.
- Hash-only detection for open-source tooling; attackers recompile in seconds. Detect behavior.
- Assuming DPAPI equals safe: any process running as the user can unprotect user-DPAPI data. It protects against offline theft, not live compromise.
- Forgetting service accounts: credentials used from a compromised host (scheduled tasks, mapped drives) are compromised too.
- Tuning detections so tightly to the lab that renamed or updated variants slip through — keep behavioral rules generic.

## References

- MITRE ATT&CK T1003 (OS Credential Dumping), T1555 (Credentials from Password Stores)
- Microsoft documentation on DPAPI and credential theft mitigations
- Sysmon documentation for process and file-access telemetry
- NIST SP 800-63B, "Digital Identity Guidelines: Authentication and Lifecycle Management"
- CISA guidance on credential hygiene and LSA protection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
