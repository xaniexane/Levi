---
skill_id: cyber_implementing_attack_path_analysis_with_xm_cyber
name: Attack Path Analysis with XM Cyber
description: Deploy continuous attack-path modeling to find and cut the choke points attackers would actually use.
risk: info
permissions: []
requires_confirmation: false
tags: [attack-surface, exposure]
version: 1.0.0
---
## Purpose
Vulnerability lists tell you what is weak; attack paths tell you what is reachable — the chains of
misconfigurations, excessive privileges, and trust relationships that turn a foothold into domain
compromise. This playbook implements continuous attack-path analysis using XM Cyber (representative
exposure-management platform): model the environment, compute paths to critical assets, and
remediate the choke points with the highest blast-radius reduction per fix.

## When to use
- Moving from vulnerability-counting to exposure-based prioritization.
- After Active Directory or cloud IAM findings that are hard to rank by severity alone.
- Before red-team exercises: validate that known paths are closed, and scope the test to residual
  paths.
- For identity-security programs: quantifying how privileged-access sprawl translates to compromise
  paths.
- Alongside attack-surface management: external exposure plus internal paths gives the full picture.

## Prerequisites
- Credentials or collectors with read access to the modeled environments: Active Directory, Entra
  ID, cloud IAM, and network segmentation data.
- A defined crown-jewels list: the critical assets (domain controllers, backup systems, payment
  databases, cloud management plane) that paths are computed against.
- Change control awareness: some remediations (removing admin rights, changing group memberships)
  affect operations — plan communication.
- A ticketing/owner mapping so path findings route to the teams that can fix them.
- Baseline red-team or pentest reports, if available, to validate the model's paths against reality.

## Procedure
1. **Define what matters.** Document the critical assets and the compromise scenarios you care about
   (e.g., "attacker with a phished standard user reaches domain admin," "compromised developer
   laptop reaches production data"). The model is only as useful as the targets.
2. **Deploy collectors with least privilege.** Install XM Cyber collectors/sensors per vendor
   guidance using read-only service accounts. Verify coverage: all domains, forests trusts, cloud
   accounts, and key network segments. Unmodeled areas are blind spots — document them explicitly.
3. **Let the model compute, then validate.** Review the generated attack paths to crown jewels.
   Sanity-check top paths against known environment facts; investigate any path that looks
   impossible — it may reveal a misconfiguration you didn't know about, or a collector gap.
4. **Prioritize choke points, not endpoints.** Identify nodes that appear in many paths
   (over-privileged service accounts, users with admin on many machines, stale trust relationships).
   One fix at a choke point collapses dozens of paths — this is the highest-ROI remediation in
   identity security.
5. **Remediate in order of blast-radius reduction.** Typical high-value fixes: remove Domain Admins
   membership sprawl, tier administrative accounts, remove local admin rights via LAPS/GPO, clean
   stale privileged group memberships, fix dangerous ACLs (e.g., GenericAll on privileged groups),
   and segment flat networks. Each fix: change ticket, owner, rollback plan.
6. **Re-run the model after changes.** Attack paths shift when you fix things — new choke points
   emerge. Treat the model as a continuous feedback loop: remediate, rescan, re-prioritize. Monthly
   at minimum; after any major AD or cloud IAM change.
7. **Track exposure metrics.** Report: number of paths to each crown jewel, mean path length (longer
   = harder for attackers), count of choke-point remediations completed, and trend over time. These
   are board-reportable security metrics.
8. **Integrate with the vulnerability program.** Correlate path findings with vuln scan data: a
   critical CVE on a machine that sits on ten attack paths outranks the same CVE on an isolated
   host. Feed combined priority into patching SLAs.
9. **Use paths to scope testing.** Give red teams the residual top paths as objectives ("we closed
   X; try Y") and use purple-team exercises to validate that modeled paths are actually exploitable
   — and that detections fire along the way.
10. **Govern the program.** Quarterly review: are new paths appearing faster than old ones close?
    Which teams own the most choke points? Tie path-reduction targets into security OKRs so the work
    is resourced, not just reported.

## Expected outputs
- A continuously updated attack-path model covering AD, cloud, and network, aimed at defined crown
  jewels.
- A prioritized choke-point remediation backlog with owners and blast-radius justification.
- Trend metrics: path counts, mean path length, remediation velocity.
- Integration with vuln management (combined prioritization) and red/purple-team scoping.
- Quarterly governance review with path-reduction targets.

## Pitfalls
- Modeling without crown jewels: you get thousands of paths to nowhere and no priorities. Define
  targets first.
- Treating the model as ground truth: collectors miss things (unmodeled trusts, shadow IT); validate
  surprising paths and document coverage gaps.
- Remediating endpoints instead of choke points: fixing 50 individual findings while the
  over-privileged service account remains is motion without progress.
- One-time modeling: environments drift weekly; a quarterly snapshot decays into fiction. Continuous
  or don't bother.
- Breaking operations: removing privileges without understanding service dependencies causes outages
  — always have a rollback plan and a maintenance window for identity changes.

## References
- XM Cyber platform documentation (attack path modeling, choke-point methodology)
- MITRE ATT&CK (techniques commonly appearing in attack paths: T1078, T1484, T1134, T1552)
- Microsoft: Securing Privileged Access / Enterprise Access Model (tiering guidance)
- CISA: guidance on reducing privileged-access risk and identity attack surface
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
