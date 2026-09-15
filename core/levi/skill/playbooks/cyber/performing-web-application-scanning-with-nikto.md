---
skill_id: cyber_performing_web_application_scanning_with_nikto
name: Web Application Scanning with Nikto
description: Run authorized Nikto scans against your own web servers to find outdated software, dangerous files, and misconfigurations.
risk: low
permissions: []
requires_confirmation: false
tags: [web, scanning, vulnerability-management]
version: 1.0.0
---

## Purpose
This playbook covers authorized vulnerability scanning of web servers you own or have written permission to test, using the open-source Nikto scanner. The goal is defensive: build an inventory of outdated components, exposed admin interfaces, dangerous default files, and server misconfigurations so they can be remediated before attackers find them. Scanning any system without explicit written authorization is out of scope and may be unlawful.

## When to use
- Quarterly vulnerability assessments of public-facing web infrastructure.
- Pre-launch security review of a new site or major deployment.
- After infrastructure changes such as migrations, CDN swaps, or server rebuilds.
- As a cheap first-pass sweep feeding a deeper manual assessment.

## Prerequisites
- Written authorization defining the exact in-scope hosts, URLs, and test window.
- Nikto installed (package manager or source) with an up-to-date plugin database (`nikto -update`).
- Inventory of target hosts including virtual hosts and TLS endpoints.
- Agreed scan window and a contact who can stop the scan if a target degrades.

## Procedure
1. Confirm the authorization letter covers every target IP, hostname, and port; abort on any ambiguity.
2. Update Nikto's databases and plugins so checks reflect current signatures.
3. Run a baseline scan per host, e.g. `nikto -h https://www.example.com -o nikto-<host>.html -Format htm`.
4. Use Tuning options to skip checks that are irrelevant or dangerous for the target (e.g. skip denial-of-service checks with `-Tuning x 0`).
5. Throttle with `-Pause` and limit concurrency (`-maxtime`) on fragile or legacy applications.
6. Manually verify each high and critical finding; Nikto reports many informational items that are not vulnerabilities.
7. Correlate findings with server banners, patch records, and WAF behavior to weed out false positives.
8. File remediation tickets with evidence, affected asset, and a suggested fix for every confirmed issue.
9. Rescan after remediation to confirm closure and keep the report as audit evidence.
10. Record the Nikto plugin database version in the report so results are reproducible months later.
11. Scan non-standard ports too; Nikto's defaults miss applications on unusual ports.
12. Compare findings against the previous scan to highlight new issues and regressions.

## Expected outputs
- HTML/CSV scan report per host with timestamps and plugin versions.
- Verified finding list with false positives removed and severity assigned.
- Remediation tickets tracked to closure, plus a rescan report proving fixes.
- Exception register for accepted-risk findings with owner and expiry dates.
- Scan-to-scan delta report showing new, fixed, and persistent findings.
- Coverage note listing hosts or ports excluded and why.

## Pitfalls
- Nikto is noisy; run it without warning the SOC and you will generate incident tickets.
- Banner-based findings can be false positives when versions are backported by the OS vendor.
- Aggressive scans can crash fragile apps; always throttle and prefer staging first.
- Nikto only finds known signatures; a clean scan is not proof of security.
- Nikto over HTTPS with SNI mismatches can scan the wrong virtual host; verify the target served.
- Relying on Nikto alone for compliance evidence is insufficient; pair it with manual review.
- Forgetting to update the plugin database silently tests against stale signatures.

## References
- Nikto official documentation (cirt.net/Nikto2).
- OWASP Web Security Testing Guide.
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
