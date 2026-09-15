---
skill_id: cyber_performing_docker_bench_security_assessment
name: Docker Bench Security Assessment
description: Run the CIS Docker benchmark against container hosts and harden failing checks.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, benchmark, hardening]
version: 1.0.0
---
# Docker Bench Security Assessment

## Purpose

Docker Bench for Security is an open-source script that audits a container
host against the CIS Docker Benchmark: host configuration, daemon settings,
image provenance, runtime policies, and swarm/TLS controls. This playbook
turns a bench run into a prioritized hardening backlog.

## When to use

- Hardening Docker hosts before production rollout or an audit.
- Verifying remediation after a container-related finding or incident.
- Periodic compliance checks of CI build runners and orchestrator nodes.
- Pre-migration review when moving workloads into Docker.

## Prerequisites

- Authorization to run read-only checks on the target Docker host; the
  script inspects configuration but does not change anything.
- Docker Bench for Security cloned on the analysis host
  (docker/docker-bench-security).
- Root or a Docker-privileged user on the scanned host, since daemon and
  host-level checks require elevated access.

## Procedure

1. Run the script from the repo directory on the host being assessed:
   `sudo sh docker-bench-security.sh`. Capture both stdout and the exit
   summary to a dated log file.
2. Triage results by section: 1.x host configuration, 2.x daemon
   configuration, 3.x daemon configuration files, 4.x container images and
   builds, 5.x container runtime, 6.x swarm mode, 7.x enterprise operations.
3. Work the highest-risk failures first: exposed daemon socket on a TCP
   port without TLS (2.x), containers running as root by default (5.x),
   inter-container communication left enabled, and sensitive host paths
   mounted into containers.
4. For each FAIL, read the remediation text the script prints — it names the
   exact daemon flag or `/etc/docker/daemon.json` key (e.g. set
   `"userns-remap"`, `"no-new-privileges": true`, `"icc": false`,
   `"tlsverify": true`).
5. Harden images per section 4: use minimal base images, pin digests rather
   than mutable tags, run builds with `.dockerignore`, and scan images with
   a vulnerability scanner (Trivy, Grype) since the bench does not check
   image CVEs.
6. Address swarm findings (section 6): verify manager encryption at rest,
   certificate rotation, and that `docker swarm` services do not expose
   management ports beyond the required set.
7. Re-run the script after changes and record the delta: resolved checks,
   accepted risks with compensating controls, and checks not applicable
   (e.g. swarm-only checks on a standalone host).
8. Feed accepted failures into a recurring schedule — monthly on build
   runners, quarterly on production hosts — and store reports with hashes
   for audit evidence.

## Expected outputs

- A dated Docker Bench report with PASS/WARN/FAIL per check, mapped to
  CIS Docker Benchmark v1.4/1.5 section numbers.
- A prioritized remediation list with concrete daemon.json flags and
  runtime changes.
- A re-run report showing resolved checks plus a documented accepted-risk
  register for the remainder.

## Pitfalls

- Treating INFO checks as failures: some checks (e.g. auditd rules) are
  informational and may be covered by another control — verify before
  "fixing" them.
- Running the script only once: drift returns quickly on build hosts; the
  value is in the re-run cadence.
- Assuming the bench covers image vulnerabilities: it does not — pair it
  with an image scanner.
- Copying daemon.json snippets blindly across hosts with different storage
  drivers or TLS layouts.

## References

- CIS Docker Benchmark (CIS WorkBench)
- Docker Bench for Security repository documentation (docker/docker-bench-security)
- NIST SP 800-190, Application Container Security Guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
