---
skill_id: cyber_implementing_patch_management_workflow
name: Implementing Patch Management Workflow
description: Design the end-to-end enterprise patch management workflow — discovery, prioritization, testing, deployment rings, verification, and exception handling.
risk: info
permissions: []
requires_confirmation: false
tags: [patch-management, vulnerability-management, operations]
version: 1.0.0
---
## Purpose

Make patching a reliable production line instead of a monthly scramble. This playbook defines the full workflow: asset discovery feeding vulnerability identification, risk-based prioritization, testing, ring-based deployment, verification, and exception management — with SLAs, metrics, and the rollback discipline that lets teams patch aggressively without fear.

## When to use

- Building or formalizing enterprise patch management (servers, workstations, network gear, applications).
- Reducing mean time to remediate critical vulnerabilities.
- Meeting SLA expectations (internal policy, PCI DSS 4.0, cyber-insurance requirements).
- After incidents where the exploited vulnerability had a patch available for months.
- Consolidating fragmented patching (SCCM here, manual there, "we don't patch those" elsewhere) into one program.

## Prerequisites

- Asset inventory with ownership, criticality, and maintenance-window assignments (patching without ownership data stalls at "who approves the reboot?").
- Patching tooling deployed: WSUS/Intune/Autopatch, SCCM/MECM, Ansible, or platform-native (Linux repos, cloud update managers) per fleet segment.
- Vulnerability scanning feeding prioritization (Tenable, Qualys, Rapid7) with asset reconciliation.
- Defined patch windows per environment tier and an emergency out-of-band process.
- Backup/snapshot capability enabling rollback for each tier.

## Procedure

1. **Discover and reconcile continuously.** Maintain the asset inventory via the patching tools' own agents plus network discovery; reconcile against vulnerability scanner coverage monthly. Unmanaged assets are unpatched assets — the reconciliation gap report is a standing agenda item, not a one-time cleanup.
2. **Prioritize with risk, not just severity.** Combine CVSS with exploitability intelligence (CISA KEV catalog membership, public exploit availability) and asset criticality/exposure. KEV-listed vulnerabilities on internet-facing systems: emergency track. Everything else: scheduled by tier. Publish the prioritization rubric so teams understand why their system is in which track.
3. **Test on a representative pilot ring.** Ring 0: lab/canary systems running the patch for 24–72 hours with automated health checks. Ring 1: IT and volunteer systems. Only then broad deployment. Maintain a known-bad-patch list and a rapid rollback trigger — a patch that breaks authentication fleet-wide must be reversible in minutes, not days.
4. **Deploy in rings with deadlines.** Ring 2: non-critical production; Ring 3: critical production in maintenance windows. Set SLA clocks by priority: critical/exploitable (days), high (2 weeks), medium/low (30–90 days). Automate deployment and reboot scheduling; manual patching doesn't scale past dozens of systems.
5. **Handle third-party applications.** OS patching tools don't cover Java, browsers, readers, and line-of-business apps — the actual exploited surface in many incidents. Extend the workflow with application patching (Intune app updates, Chocolatey/Winget automation, vendor auto-update policies centrally managed) and track third-party patch compliance separately.
6. **Verify, don't assume.** Post-deployment, verify via scanner rescan and agent reporting: patch compliance percentage per tier, per SLA track. Investigate non-compliant systems individually — "the tool says deployed" without verification is how gaps persist for quarters.
7. **Manage exceptions formally.** Systems that can't be patched (legacy apps, change freezes, vendor blocks) get documented exceptions: risk assessment, compensating controls, expiry date, owner sign-off. Exceptions expire and re-justify; permanent exceptions require executive risk acceptance reviewed annually.
8. **Report metrics that drive action.** Dashboard: compliance % by tier and SLA track, mean time to patch by priority, exception inventory with expiries, and — the metric that matters — exploitable-vulnerability dwell time on internet-facing assets. Review with system owners monthly; escalate chronic non-compliance to leadership.

## Expected outputs

- Documented workflow with rings, SLAs, and emergency out-of-band process.
- Prioritization rubric combining severity, exploitability (KEV), and asset criticality.
- Ring-based deployment with tested rollback procedures.
- Third-party application patching coverage.
- Compliance verification and exception register; metrics dashboard with monthly reviews.

## Pitfalls

- **Patching without verification.** Deployment success rates lie; only scanner-verified compliance counts. The gap between "pushed" and "actually patched" is where breaches live.
- **One ring for everything.** Patching domain controllers with the same process as print servers guarantees either excessive caution or catastrophic boldness. Tier by blast radius.
- **Ignoring third-party apps.** OS fully patched, Java from 2019 — attackers read the same threat reports you do. Application patching is not optional.
- **Exception permanence.** Exceptions granted "temporarily" in 2021 still open in 2026. Expiry dates with teeth, or the exception process is a waiver machine.
- **Fear-driven patching freezes.** After one bad patch, organizations freeze all patching for months — trading a known, bounded rollback event for unbounded vulnerability exposure. The answer to a bad patch is better testing and rollback, not stopping.

## References

- NIST SP 800-40 Rev. 4, "Guide to Enterprise Patch Management Planning" — https://csrc.nist.gov/publications/detail/sp/800-40/rev-4/final
- CISA Known Exploited Vulnerabilities (KEV) catalog — https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- CIS Critical Security Controls v8 (Control 7: Continuous Vulnerability Management) — https://www.cisecurity.org/controls
- MITRE ATT&CK T1190 (Exploit Public-Facing Application) — https://attack.mitre.org/techniques/T1190/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
