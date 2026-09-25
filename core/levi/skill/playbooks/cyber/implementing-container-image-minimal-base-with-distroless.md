---
skill_id: cyber_implementing_container_image_minimal_base_with_distroless
name: Minimal Container Images with Distroless Bases
description: Shrink container attack surface with distroless/minimal base images and verified build practices.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, hardening]
version: 1.0.0
---
## Purpose
Full OS base images ship shells, package managers, and hundreds of utilities your application never
uses — each a potential tool for attackers and a source of CVEs to triage. Distroless and minimal
base images contain only the application and its runtime dependencies: smaller attack surface, fewer
CVEs, faster scans, faster pulls. This playbook migrates container builds to minimal bases safely.

## When to use
- Reducing container CVE counts and image sizes across a Kubernetes/Docker estate.
- After incidents where attackers used in-container shells or utilities for lateral movement.
- Meeting minimal-attack-surface requirements (SLSA, internal hardening standards).
- Speeding up CI pipelines and deployments (smaller images pull and scan faster).
- As the build-hygiene foundation beneath image scanning and admission control.

## Prerequisites
- Application runtime knowledge: language, dependencies, and whether the app needs a shell at
  runtime (most don't).
- CI/CD access to modify Dockerfiles and build pipelines.
- An image scanner to compare CVE counts before/after (proves the value).
- A debugging strategy for shell-less images (debug sidecars, ephemeral containers — decide
  upfront).
- Base-image provenance: use official distroless/minimal images from trusted registries, pinned by
  digest.

## Procedure
1. **Baseline current images.** Record size, package count, and CVE counts for existing images. You
   need the "before" numbers — the improvement story funds the migration.
2. **Choose the right minimal base.** Google's distroless (per-language: java, nodejs, python, go,
   cc), Chainguard images, or minimal distro bases (Alpine, slim variants) — matched to your
   runtime. Prefer images with SBOMs and provenance attestations. Pin by digest, not tag.
3. **Restructure Dockerfiles to multi-stage builds.** Build stage: full toolchain (compilers,
   package managers) compiles the app. Final stage: distroless/minimal base + compiled artifacts
   only. Build tools must never ship in the runtime image — multi-stage is the mechanism.
4. **Handle the shell-less reality.** Remove assumptions: no shell for entrypoint scripts (use
   exec-form CMD or a static binary wrapper), no package manager at runtime, no debugging via exec
   shell. Provide alternatives: distroless debug variants for troubleshooting, kubectl debug
   ephemeral containers, and structured logging that reduces the need for shell access.
5. **Run as non-root.** Set a non-root USER in the final stage, make file permissions correct at
   build time, and drop Linux capabilities. Minimal base + non-root + read-only filesystem is the
   hardened trifecta — implement all three together.
6. **Verify functionality thoroughly.** Test the migrated image: application startup, health checks,
   signal handling (PID 1 behavior without a shell — use exec form or a tiny init), file writes
   (redirect to mounted volumes), and TLS (distroless includes CA certs — verify). Stage-gate before
   production.
7. **Scan and compare.** Rescan: CVE count should drop dramatically (fewer packages = fewer CVEs),
   image size shrinks, scan time drops. Investigate remaining findings — they're now in your actual
   dependencies, which deserve attention.
8. **Migrate in waves.** Start with stateless services and batch jobs (easiest), then stateful apps,
   then the hard cases (legacy apps needing shells — refactor or isolate with justification). Each
   wave: build, test, canary deploy, monitor.
9. **Standardize and govern.** Publish the approved base-image catalog (per language, pinned
   digests, owner, update cadence). Require new services to use catalog images via pipeline checks
   or admission policy. Exceptions need security approval and expiry.
10. **Maintain the bases.** Rebuild images on base-image updates (automate: watch upstream, rebuild
    weekly or on CVE). Track base-image age — a distroless image from 6 months ago still accumulates
    application-layer CVEs. Freshness is continuous.

## Expected outputs
- Migrated images on distroless/minimal bases with before/after size and CVE comparisons.
- Multi-stage Dockerfiles with non-root users and read-only filesystems.
- A debugging strategy for shell-less images (debug variants, ephemeral containers).
- An approved base-image catalog with pinned digests, owners, and update cadence.
- Pipeline/admission enforcement of catalog images.

## Pitfalls
- Assuming the app doesn't need a shell: entrypoint scripts, signal handling, and health checks
  often do. Test thoroughly — don't discover in production.
- Debugging without a plan: teams locked out of shell-less containers during incidents will revert
  to fat images. Provide debug variants and kubectl debug workflows upfront.
- Tag pinning instead of digest pinning: `latest` or floating tags silently change contents.
  Digest-pin for reproducibility.
- Forgetting CA certificates and timezones: distroless bases are truly minimal — verify TLS trust
  and timezone data your app needs are present.
- One-time migration: base images need continuous rebuilds. Without automation, minimal images go
  stale like any other.

## References
- GoogleContainerTools distroless documentation (image variants, debug images)
- Chainguard images documentation (minimal, SBOM'd base images)
- NIST SP 800-190 (container image security)
- CIS Docker Benchmark (minimal image guidance)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
