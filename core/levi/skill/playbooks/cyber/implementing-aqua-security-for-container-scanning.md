---
skill_id: cyber_implementing_aqua_security_for_container_scanning
name: Container Image Scanning with Aqua Security
description: Embed Aqua Security image scanning into the container pipeline with risk-based gates and runtime linkage.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, scanning]
version: 1.0.0
---
## Purpose
Vulnerable base images and misconfigured containers ship daily through CI/CD; runtime incidents
later trace back to a CVE that was scannable at build time. This playbook implements container image
scanning with Aqua Security (representative container-security platform): scan every image at build,
gate promotion on risk policy, and link image findings to running workloads so fix priority follows
real exposure.

## When to use
- Building or maturing container security in a Docker/Kubernetes estate.
- After incidents or audits finding critical CVEs in production images.
- To satisfy supply-chain requirements: every deployed image scanned, attested, and traceable to
  source.
- Before a Kubernetes production launch or a registry migration.
- Alongside minimal-base-image and admission-control playbooks (scan, slim, then enforce).

## Prerequisites
- A container registry (or registries) Aqua can integrate with, and CI/CD access to insert scan
  stages.
- Defined risk policy: which severities block promotion, grace periods for fixable vs. unfixable
  CVEs, and exception workflow.
- SBOM generation capability or agreement to use scanner-produced manifests for traceability.
- Kubernetes admission control (or a deployment gate) to enforce "only scanned-and-passed images
  deploy."
- Owners for base images: someone must own rebuilding them when CVEs land.

## Procedure
1. **Connect registries and CI.** Integrate Aqua with the container registry for continuous scanning
   of stored images and with CI pipelines (Jenkins, GitLab, GitHub Actions) for build-time scans.
   Both matter: CI catches new issues, registry scanning catches newly disclosed CVEs in old images.
2. **Establish the baseline.** Scan all existing images; produce the initial vulnerability and
   misconfiguration report. Expect noise — triage into: fixable with patch available, unfixable (no
   upstream fix), and misconfigurations (running as root, secrets in layers, exposed ports).
3. **Define a risk-based gate policy.** Block promotion on: critical CVEs with fixes in
   internet-facing images, hardcoded secrets, and malware signatures. Warn (don't block) on
   medium/low or unfixable CVEs initially. Encode exceptions with expiry dates, never permanently.
4. **Scan in the pipeline, fail the build.** Add the scan step after image build, before push to the
   release registry. Developers get findings in the PR with fix guidance (which base image tag or
   package version resolves it). Keep scan times acceptable — cache vulnerability databases, scan
   only changed layers where supported.
5. **Assess misconfigurations, not just CVEs.** Enable checks for: root user, sensitive mounts,
   unpinned base tags (`latest`), embedded secrets, and unnecessary packages. A CVE-free image
   running as root with the Docker socket mounted is still a finding.
6. **Link images to running workloads.** Correlate scan results with the orchestrator: which
   vulnerable images are actually deployed, where, and with what exposure. Prioritize fixes for
   internet-facing, privileged, or data-handling workloads first — an unused image in the registry
   is lower priority.
7. **Drive base-image hygiene.** Standardize on minimal, maintained base images (see distroless
   playbook), pin digests, and rebuild on a cadence (weekly for critical apps). Assign base-image
   ownership so CVE fixes have a responsible team.
8. **Handle exceptions transparently.** For unfixable or accepted-risk findings: document business
   justification, compensating controls (network policy, runtime protection), owner, and expiry.
   Review the exception list monthly — exceptions rot into permanent debt.
9. **Add runtime assurance linkage.** Where Aqua runtime protection is deployed, ensure image scan
   context feeds runtime policies (e.g., block unexpected executables in containers built from
   high-risk images) and that runtime anomalies feed back into image review.
10. **Report trends, not just counts.** Track: percent of images scanned before deploy, gate-block
    rate, mean time to remediate critical CVEs in running workloads, and base-image freshness.
    Report deltas to engineering leadership.

## Expected outputs
- Registry + CI scanning coverage with a documented gate policy and exception process.
- Baselines and triaged findings linked to running workloads and owners.
- Pipeline gates failing builds on policy violations; admission control blocking unscanned images.
- Base-image standards (minimal, pinned, owned, rebuilt on cadence).
- Trend metrics on scan coverage, remediation time, and exception aging.

## Pitfalls
- Scanning only at build: newly published CVEs affect old images — registry rescan on feed updates
  is mandatory.
- Blocking on unfixable CVEs with no exception path: builds grind to a halt and teams bypass the
  gate. Policy must distinguish fixable from unfixable.
- Ignoring misconfigurations while chasing CVE counts: runtime posture (root, mounts, secrets)
  matters as much as patch level.
- Scanner findings without owners: "critical CVE in image X" with no team assigned is a report, not
  remediation. Map images to services to teams.
- Treating the scanner as the whole program: scanning finds issues; base-image standards, admission
  control, and runtime protection fix and contain them.

## References
- Aqua Security documentation (image scanning, CI/CD integration, assurance policies)
- NIST SP 800-190 (container security: image, registry, orchestrator, container, host)
- CIS Docker and Kubernetes Benchmarks
- SLSA framework (supply-chain levels for build integrity)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
