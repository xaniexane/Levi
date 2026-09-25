---
skill_id: cyber_performing_active_directory_bloodhound_analysis
name: Performing Active Directory BloodHound Analysis (Authorized Audit)
description: Conduct authorized BloodHound-based analysis of your own AD to find and fix attack paths.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, bloodhound, auditing]
version: 1.0.0
---

## Purpose
This playbook is the end-to-end workflow for an authorized BloodHound analysis engagement against your own Active Directory: planning, collection, analysis, reporting, and verified remediation. It assumes written authorization and covers only your own directory.

## When to use
- Periodic AD security assessments or pre-audit hardening.
- After AD changes (migrations, new delegation models) to verify no new paths opened.
- Demonstrating AD risk to leadership with concrete path evidence.

## Prerequisites
- Written authorization specifying domains, collection methods, and window.
- BloodHound (CE or Enterprise) deployed; collection tooling (SharpHound) tested in a lab.
- A remediation owner with authority to change group memberships and ACLs.

## Procedure
1. **Plan and authorize.** Document objectives, scope, collection account, and rules of engagement; get sign-off from AD and security leadership.
2. **Collect safely.** Run the collector during the agreed window; prefer the least-invasive collection method that answers the questions; validate data completeness (computer coverage, session data freshness).
3. **Analyze methodically.** Work through: shortest paths to Domain Admins, kerberoastable accounts, unconstrained delegation, DCSync rights, adminSDHolder anomalies, and cross-trust paths.
4. **Validate findings.** Confirm each finding in ADUC/ADSI or PowerShell before reporting; graph data can be stale or misinterpreted.
5. **Report with remediation priority.** Rank by path length to tier-0, number of principals that can traverse, and ease of exploitation; include exact remediation steps per finding.
6. **Remediate with the AD team.** Remove excessive rights, fix nesting, rotate service account credentials, implement tiering; re-collect to prove each path is closed.
7. **Establish recurrence.** Schedule the analysis quarterly or on significant AD change; trend the number of tier-0-reachable paths over time.

8. **Protect the collection data.** BloodHound databases map your entire privilege structure; encrypt, access-control, and purge them per the engagement's data-handling rules.
9. **Train AD admins on the graph.** A walkthrough of the findings with the AD team transfers more lasting value than the report alone.

## Expected outputs
- Engagement report: methodology, findings with evidence, prioritized remediation.
- Verified remediation: before/after collection diffs.
- Recurring assessment schedule with trend metrics.
- Example: the engagement demonstrates a 3-hop path from a service account to Domain Admins via nested group membership; after the AD team flattens the nesting, re-collection proves the path closed.

## Pitfalls
- Running collection tools outside the authorized window or scope.
- Reporting graph artifacts as findings without validation in the live directory.
- Handing over a findings list with no remediation partnership — nothing gets fixed.

- Collecting once and reporting for months; AD changes daily, and a stale graph misleads more than it helps.
- Fixing symptoms (removing one user from one group) instead of the structural cause (broken delegation model that recreates the problem).

## References
- BloodHound documentation (bloodhound.readthedocs.io).
- Microsoft Learn: Active Directory security best practices (learn.microsoft.com).
- PingCastle documentation (github.com/vletoux/pingcastle) — complementary AD auditing.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
