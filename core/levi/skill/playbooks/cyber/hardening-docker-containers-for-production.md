---
skill_id: cyber_hardening_docker_containers_for_production
name: Hardening Docker Containers for Production
description: Apply production hardening to containerized workloads: minimal images, non-root users, read-only filesystems, and runtime controls.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, hardening, devops]
version: 1.0.0
---
## Purpose

Containers ship with dangerously permissive defaults: root users, writable
filesystems, and broad capabilities. This playbook walks through hardening
containerized workloads for production — image hygiene, runtime
restrictions, and secrets handling — aligned with the CIS Docker Benchmark
and container-security best practices.

## When to use

- Preparing any containerized service for production deployment.
- Remediating container-security audit or benchmark findings.
- After a container-escape or cryptominer incident traced to weak
  container configuration.
- Standardizing a secure container baseline across teams (golden image
  / admission policy).

## Prerequisites

- Access to Dockerfiles, image build pipelines, and the orchestration
  platform's security policies (admission controllers where available).
- An image scanner integrated into CI.
- A test/staging environment to validate that hardening does not break
  the application.
- The CIS Docker Benchmark (container-runtime sections) as the control
  reference.

## Procedure

1. **Start from minimal images.** Use distroless or minimal base images,
   pin digests (not floating tags), and remove package managers, shells,
   and build tooling from runtime images via multi-stage builds.
2. **Run as non-root.** Set an explicit non-root `USER` in the
   Dockerfile, avoid `docker run --user root` overrides, and enable
   user-namespace remapping on the daemon where supported.
3. **Make the filesystem read-only.** Run containers with a read-only
   root filesystem and mount only the specific writable paths the
   application needs (tmpfs or named volumes). This single control
   defeats large classes of post-exploitation persistence.
4. **Drop capabilities and syscalls.** Drop all Linux capabilities and
   add back only what the application provably needs
   (`--cap-drop=all --cap-add=...`); apply a seccomp profile
   (default-docker is a floor, custom is better) and consider AppArmor/
   SELinux confinement.
5. **Never use privileged mode.** Prohibit `--privileged`; it disables
   nearly all isolation. Audit existing deployments for privileged
   containers and remediate each with a documented justification or
   removal.
6. **Handle secrets properly.** Never bake secrets into images or pass
   them as environment variables visible in inspect output — use a
   secrets manager with short-lived, mounted secrets, and rotate on a
   schedule.
7. **Scan and sign.** Scan images in CI for OS and language-package
   CVEs, fail builds on critical findings (with an exception process),
   and sign images so the runtime only runs trusted, verified images.
8. **Enforce at admission.** Codify the baseline in an admission
   controller/policy engine (e.g. "must be non-root, read-only, no
   privileged, from approved registries") so non-compliant workloads
   cannot reach production regardless of who deploys them.

## Expected outputs

- A hardened container baseline (Dockerfile patterns, run flags,
  policy definitions).
- CI-integrated image scanning with pass/fail gates.
- Admission policies enforcing the baseline in production.
- An audit report: current containers vs. baseline, with remediation
  owners for gaps.

## Pitfalls

- Read-only filesystems and dropped capabilities break applications
  that were never designed for them — test in staging and iterate.
- Distroless images complicate debugging (no shell) — establish a
  debug-image workflow rather than weakening production images.
- Environment-variable secrets leak through orchestration APIs and logs
  — treat any env-secret as compromised and migrate to mounted secrets.
- Image scanning without an exception process becomes shelfware —
  define who can accept risk and for how long.
- Forgetting the supply chain: pinning digests is undermined if the
  registry itself is untrusted — verify registry provenance.

## References

- CIS Docker Benchmark (container configuration sections)
- NIST SP 800-190: Application Container Security Guide
- Docker official documentation: security best practices
- OWASP: Docker security cheat sheet
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
