---
skill_id: cyber_scanning_container_images_with_grype
name: Scanning Container Images with Grype
description: Scan container images for known vulnerabilities with Grype and turn results into remediation actions.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, scanning, grype]
version: 1.0.0
---
## Purpose
Grype matches installed OS and language packages in container images against vulnerability databases. This playbook covers running it as part of a defensive container security program: scanning images, triaging matches, fixing at the Dockerfile or base-image layer, and tracking vulnerability debt across the image fleet.

## When to use
- Evaluating base images before standardizing them for the organization.
- Ad-hoc assessment of a third-party or legacy image before deployment.
- Validating that rebuilds actually cleared previously reported CVEs.
- Periodic sweep of images stored in the registry.

## Prerequisites
- Grype installed with an updated vulnerability database.
- Access to the images to scan (registry credentials or local daemon).
- Inventory of which images are actually deployed vs stale.
- Remediation path: who owns each Dockerfile and base image choice.

## Procedure
1. Update the Grype database so matches reflect current CVE data.
2. Scan each image, e.g. `grype registry.example.com/team/app:1.2.3 -o json > grype.json`.
3. Filter results by severity and by fix availability; unfixed CVEs need compensating controls, not just tickets.
4. Verify matches against the actual package versions; Grype can flag distro-backported versions incorrectly.
5. Remediate at the source: bump the base image, update the pinned package, or remove the unnecessary dependency.
6. Rebuild and rescan to confirm the CVE is gone; record the before/after reports.
7. Track recurring offenders: base images or packages that repeatedly introduce criticals.
8. Feed results into image promotion gates so vulnerable images cannot reach production registries.
9. Generate and archive an SBOM at scan time alongside the report for auditability.
10. Pin the Grype database version in CI so results are reproducible across runs.
11. Scan images by digest rather than tag to avoid tag-mutation surprises.

## Expected outputs
- Per-image scan reports with verified, actionable findings.
- Remediation log: base-image or package changes with rescan evidence.
- Base-image allowlist/blocklist updates based on recurring findings.
- Archived SBOM per scanned image.
- Database version record for reproducibility.
- Digest-pinned scan manifest.

## Pitfalls
- Distro security backports cause false positives; check the distro's CVE tracker before panicking.
- Scanning without ownership mapping produces reports nobody acts on.
- Language-package CVEs often require app dependency updates, not just base-image bumps.
- A clean Grype scan is not a clean image; it only covers known CVEs.
- Grype database updates can change results overnight; pin versions in CI.
- Distroless and minimal images reduce noise but can hide language-package CVEs; verify coverage.
- Vulnerability matches without reachable code paths need exploitability triage, not panic.
- Grype results need ownership routing; unowned images accumulate CVEs indefinitely.

## References
- Anchore Grype documentation.
- NIST SP 800-190, Application Container Security Guide.
- CIS Docker Benchmark.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
