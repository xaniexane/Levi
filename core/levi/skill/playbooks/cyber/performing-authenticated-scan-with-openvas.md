---
skill_id: cyber_performing_authenticated_scan_with_openvas
name: Performing Authenticated Scans with OpenVAS
description: Run credentialed OpenVAS scans for deep, patch-accurate host assessment.
risk: low
permissions: []
requires_confirmation: false
tags: [vulnerability-management, openvas, scanning]
version: 1.0.0
---

## Purpose
This playbook runs authenticated (credentialed) OpenVAS/Greenbone scans: configuring scan credentials safely, executing deep host assessments, and using the patch-level accuracy that unauthenticated scans cannot provide.

## When to use
- Unauthenticated scans miss patch detail and produce false positives on backported fixes.
- Compliance requires credentialed assessment of in-scope systems.
- You need definitive "is this host actually vulnerable" answers for critical assets.

## Prerequisites
- Greenbone/OpenVAS deployment with current feeds.
- Written approval for credentialed scanning of target systems.
- Least-privilege scan credentials: SSH keys or service accounts with read-only assessment rights.

## Procedure
1. **Get approval and define windows.** Document target systems, scan windows, and the credential types approved; coordinate with system owners.
2. **Create least-privilege credentials.** Use dedicated scan accounts: SSH key-based where possible, no interactive logon rights, and no access beyond assessment needs.
3. **Store credentials securely.** Keep them in Greenbone's credential store; rotate on the same schedule as other service accounts and after personnel changes.
4. **Build authenticated scan configs.** Clone the standard config and enable local security checks; verify the scanner can log in with a small pilot target first.
5. **Run and validate.** Execute scans in the approved window; spot-check results against known patch states to confirm the credentials worked (failed logins silently degrade to unauthenticated results).
6. **Triage with confidence.** Authenticated results support firmer conclusions: prioritize missing patches on critical assets and verify false positives against actual package versions.
7. **Review credential hygiene.** Audit scan-credential usage logs for unexpected targets or times; a scan credential is a privileged account and must be monitored as one.

8. **Handle scan failures as findings.** Hosts that repeatedly fail authenticated scans go on an exception list with owner accountability, not into silent obscurity.
9. **Benchmark unauthenticated vs. authenticated.** Periodically compare both result sets to quantify what the credentialed scans add; the delta justifies the credential-management overhead.

## Expected outputs
- Approved scan plan with credential inventory and rotation schedule.
- Authenticated scan results with login-success verification per target.
- Findings with patch-level evidence fed to remediation.
- Example: an authenticated scan confirms a missing kernel patch that the unauthenticated scan missed due to backported version strings; the finding includes the exact installed package version as evidence.

## Pitfalls
- Silent authentication failure: the scan runs, finds little, and everyone assumes the hosts are clean.
- Over-privileged scan accounts that become attractive lateral-movement targets.
- Scanning outside the approved window and tripping change-control or availability alarms.

## References
- Greenbone documentation (docs.greenbone.net).
- NIST SP 800-40 Rev. 4, Guide to Enterprise Patch Management Planning.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
