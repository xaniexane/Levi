---
skill_id: cyber_scanning_docker_images_with_trivy
name: Scanning Docker Images with Trivy
description: Scan Docker images locally with Trivy for OS, dependency, secret, and misconfiguration findings.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, docker, trivy]
version: 1.0.0
---
## Purpose
Before an image is pushed or deployed, a quick local Trivy scan reveals known vulnerabilities, leaked secrets, and common misconfigurations. This playbook is the developer and operator workflow: scanning images on demand, interpreting the different scanner outputs, and fixing issues at the Dockerfile layer.

## When to use
- Pre-push check by developers building Docker images.
- Auditing images pulled from public registries before internal use.
- Incident response: checking whether a deployed image contains a newly disclosed CVE.
- Validating hardened or minimal base images.

## Prerequisites
- Trivy installed (binary, container, or IDE extension).
- Docker daemon or registry access to the target images.
- Basic Dockerfile literacy to implement fixes.
- Network access to vulnerability databases on first run (or a mirror).

## Procedure
1. Update Trivy's databases (`trivy image --download-db-only`) or rely on the automatic refresh.
2. Run a vulnerability scan: `trivy image --severity HIGH,CRITICAL myapp:latest`.
3. Add secret scanning (`--scanners vuln,secret`) to catch credentials baked into layers.
4. Add misconfiguration scanning for the Dockerfile to flag issues like running as root.
5. Triage: confirm fix availability, check whether the vulnerable code path is reachable, and note false positives.
6. Fix at the source: update base image tags, bump dependencies, remove secrets from layers, add a non-root USER.
7. Rebuild with `--no-cache` where layer caching could hide fixes, then rescan.
8. For images you publish, document the scan in release notes or attach the report to the registry artifact.
9. Compare the image against your approved base-image list; unapproved bases are findings by themselves.
10. Scan the platform variant you deploy; multi-arch images differ per architecture.
11. Check image history for secrets committed in early layers even if later layers look clean.

## Expected outputs
- Trivy scan reports per image (vulnerabilities, secrets, misconfigs).
- Fixed Dockerfiles with rescan evidence.
- Notes on accepted risks with justification.
- Base-image approval check result per image.
- Per-architecture scan results for multi-arch images.
- Layer-history secret review notes.

## Pitfalls
- Secrets found in layers cannot be fixed by later layers; the history must be rewritten and the secret rotated.
- Scanning `latest` tags is non-reproducible; pin digests for meaningful comparisons.
- Unfixed CVEs with no patch need compensating controls, not indefinite ignoring.
- Trivy needs DB updates; offline scans go stale quickly.
- Multi-arch images scan per-platform; scanning only amd64 misses arm vulnerabilities.
- Secrets in squashed layers are still recoverable; squashing is not remediation.
- Relying on Docker Hub's own scanning instead of your own loses policy control.
- Base image provenance matters as much as CVE count; prefer images with published SBOMs.

## References
- Aqua Trivy documentation (aquasecurity.github.io/trivy).
- Docker official documentation: Dockerfile best practices.
- CIS Docker Benchmark.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
