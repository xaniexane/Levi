---
skill_id: cyber_detecting_credential_dumping_techniques
name: Detecting Credential Dumping Techniques
description: Detect LSASS access, SAM theft, DCSync, and other credential-dumping techniques with layered endpoint and AD monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [credentials, detection, endpoint]
version: 1.0.0
---
## Purpose

Detect credential dumping — the attack phase that turns one compromised host into domain-wide access. Cover LSASS memory access, SAM/NTDS theft, DCSync, and cloud-credential harvesting with endpoint, AD, and log-based detections. Dumping detected early is a contained incident; dumping missed is a domain compromise.

## When to use

- Building detection for credential-access techniques (the most critical ATT&CK tactic to catch early).
- Hunting after a suspected compromise for credential theft indicators.
- Validating that EDR and AD monitoring catch dumping tools and techniques.
- Post-incident scoping: determining whether credentials were stolen (drives the reset scope).

## Prerequisites

- EDR with process/memory-access telemetry on endpoints; Sysmon with a dumping-aware config as backup.
- AD security event collection (4662, 4768, 4769, 4624) from domain controllers.
- Baseline of legitimate LSASS-adjacent activity (AV, EDR, and admin tools that touch LSASS).
- Credential-tiering model: which accounts are high-value (domain admins, service accounts) for prioritization.

## Procedure

1. **Detect LSASS memory access.** Alert on: processes opening LSASS with `PROCESS_VM_READ` / `PROCESS_QUERY_INFORMATION` (Sysmon Event ID 10, EDR equivalents), unsigned or unusual binaries accessing LSASS, and known dumping tools (Mimikatz, ProcDump, Task Manager abused, comsvcs.dll MiniDump). Baseline legitimate accessors (your EDR, specific admin tools) and alert on everything else.
2. **Detect SAM and registry hive theft.** Alert on: access to `HKLM\SAM`, `HKLM\SECURITY`, `HKLM\SYSTEM` hive files, `ntdsutil` or `vssadmin` shadow-copy creation on DCs, and copying of `ntds.dit`. Shadow copies on a domain controller outside backup windows are a red flag — legitimate backups are scheduled; theft is not.
3. **Detect DCSync and DCShadow.** Alert on: `DRSUAPI` replication requests (Event ID 4662 with the replication GUID) from non-DC hosts — only domain controllers should replicate; and DCShadow indicators (new SPNs, fake DC registration). DCSync from a member server or workstation is definitive compromise evidence.
4. **Detect Kerberos ticket theft and abuse.** Alert on: anomalous TGT/TGS patterns (4768/4769), RC4-encrypted tickets in modern environments (downgrade for overpass-the-hash), ticket lifetimes inconsistent with policy, and pass-the-ticket indicators (ticket used from a different host than requested). Correlate with the LSASS alerts — dumping usually precedes ticket abuse.
5. **Detect cloud and browser credential harvesting.** On endpoints, alert on: access to cloud credential files (`~/.aws/credentials`, Azure CLI tokens), browser credential-store access by unusual processes, and clipboard/keylogger indicators. In cloud logs, alert on the subsequent use — harvested credentials get used, and the use is often more visible than the theft.
6. **Prioritize by credential tier.** When dumping is detected, immediately determine what was accessible: was it a domain admin session? a service account? Scope the incident by the highest-value credential the compromised host held — that defines the reset and rotation blast radius.
7. **Respond with credential invalidation.** On confirmed dumping: force password resets for affected accounts (twice for KRBTGT in AD to kill golden tickets), rotate service-account credentials, revoke cloud keys and sessions, and hunt for where the dumped credentials were used (logon anomalies from step 6's scope). Assume dumped credentials are used until logs prove otherwise.

## Expected outputs

- Layered dumping detections: LSASS access, SAM/NTDS theft, DCSync/DCShadow, ticket abuse, cloud-credential harvesting.
- Credential-tiering model driving incident scoping and reset priorities.
- Credential-invalidation response runbooks (resets, KRBTGT double-reset, rotation).

## Pitfalls

- Alerting on LSASS access without baselining — EDR and AV touch LSASS legitimately; tune first.
- Missing DCSync because 4662 isn't collected from DCs — the highest-value detection needs the right logs.
- Detecting the dump but not scoping the credentials — the incident scope is defined by what was stolen.
- Single password resets for KRBTGT — golden tickets survive one reset; reset twice.
- Forgetting cloud credentials on the endpoint — the attacker dumps those too.

## References

- MITRE ATT&CK T1003 (OS Credential Dumping) — all sub-techniques
- Microsoft Learn — AD security event IDs (4662, 4768, 4769) and DCSync detection
- Sysmon documentation — Event ID 10 (ProcessAccess) configuration
- NIST SP 800-53 IA-5 (authenticator management) and SC-28 (protection at rest)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
