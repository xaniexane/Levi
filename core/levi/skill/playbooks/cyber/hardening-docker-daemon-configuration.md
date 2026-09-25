---
skill_id: cyber_hardening_docker_daemon_configuration
name: Hardening Docker Daemon Configuration
description: Secure the Docker daemon and host: TLS for the API socket, authorization plugins, audit logging, and CIS-aligned daemon settings.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, hardening, linux]
version: 1.0.0
---
## Purpose

The Docker daemon runs as root and its API is equivalent to root on the
host — an exposed or misconfigured daemon is a full host compromise. This
playbook hardens the daemon itself and its host: socket protection,
authentication and authorization, audit logging, and CIS Docker Benchmark
daemon controls.

## When to use

- Provisioning or reviewing any Docker host (dev, CI runners, and
  production alike).
- After discovering an exposed Docker API (TCP 2375/2376) in an asset
  scan — treat as an incident until proven otherwise.
- CIS Docker Benchmark assessments of the daemon and host sections.
- Hardening CI/CD build hosts, which are high-value targets.

## Prerequisites

- Root/admin access to the Docker hosts and change control for daemon
  configuration changes.
- A PKI or certificate process for daemon TLS (do not use the
  unencrypted TCP socket).
- Centralized log collection for daemon audit events.
- The CIS Docker Benchmark as the control reference.

## Procedure

1. **Never expose the unauthenticated socket.** Bind the daemon to the
   Unix socket only by default. If remote API access is required, use
   TLS with mutual authentication (client certificates) — never
   plaintext TCP 2375 on any network.
2. **Restrict socket access.** Limit Unix-socket access to the `docker`
   group and treat membership in that group as root-equivalent (it is).
   Audit group membership regularly.
3. **Enable authorization.** Deploy an authorization plugin to enforce
   least-privilege API access per client, rather than giving every API
   consumer full daemon rights.
4. **Apply CIS daemon controls.** Set the daemon configuration per the
   benchmark: disable inter-container communication where not needed
   (`--icc=false` with explicit links), set a default ulimit, enable
   user-namespace remapping, configure log drivers with rotation
   (unbounded json-file logs fill disks — a DoS vector), and disable
   legacy registry (v1) access.
5. **Harden the host.** Keep the host OS minimal and patched, run a
   host firewall allowing only required ports, enable auditd rules for
   Docker-related files (`/etc/docker`, daemon.json, socket), and
   separate sensitive workloads from general container hosts.
6. **Centralize daemon audit logs.** Forward daemon logs and auditd
   events to the SIEM; alert on daemon restarts, configuration changes,
   privileged container creation, and socket-permission changes.
7. **Manage daemon TLS certificates.** Issue per-client certificates,
   rotate them on personnel/role changes, and revoke promptly on
   offboarding — a stale client cert is root on the host.
8. **Verify continuously.** Re-run the CIS benchmark checks on a
   schedule and after every daemon/host change; scan for exposed Docker
   APIs (2375/2376) from both inside and outside the network.

## Expected outputs

- A hardened daemon configuration (daemon.json) under version control.
- TLS mutual-auth for any remote API access with a certificate
  lifecycle process.
- Authorization plugin policy and docker-group membership audit.
- Centralized logging with alerts for daemon tampering.
- Recurring benchmark-compliance reports.

## Pitfalls

- The `docker` group is root-equivalent — adding developers to it for
  convenience grants host root; use authorization plugins instead.
- TLS without client-certificate verification still allows anyone to
  connect — mutual TLS is the requirement, not server-side TLS alone.
- Unbounded container logging fills host disks — always configure log
  rotation.
- Forgetting CI runners: build hosts run untrusted code by design and
  need the same daemon hardening plus job isolation.
- Daemon config changes require restarts — schedule them and verify
  containers come back healthy.

## References

- CIS Docker Benchmark (daemon and host configuration sections)
- Docker official documentation: "Protect the Docker daemon socket"
- NIST SP 800-190: Application Container Security Guide
- MITRE ATT&CK: T1609 (Container Administration Command)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
