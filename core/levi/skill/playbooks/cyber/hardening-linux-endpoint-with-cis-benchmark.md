---
skill_id: cyber_hardening_linux_endpoint_with_cis_benchmark
name: Hardening Linux Endpoints with CIS Benchmark
description: Apply the CIS Linux benchmark to harden endpoints: filesystem, services, kernel, auth, and logging controls with safe rollout practices.
risk: low
permissions: []
requires_confirmation: false
tags: [linux, hardening, compliance]
version: 1.0.0
---
## Purpose

The CIS Benchmarks provide consensus-based, prioritized hardening controls
for Linux distributions. This playbook guides applying the CIS Linux
benchmark to endpoints and servers: assessing current posture, remediating
by control family, and rolling out safely without breaking production
workloads.

## When to use

- Establishing a secure Linux baseline for new builds (golden images).
- Compliance programs requiring CIS alignment (often alongside PCI DSS,
  SOC 2, or internal policy).
- Post-incident hardening of rebuilt systems.
- Periodic posture reviews: measuring drift from the baseline.

## Prerequisites

- Root access to target systems and change control for configuration
  changes.
- A CIS-CAT-class scanner or equivalent assessment tooling, plus a
  staging environment mirroring production for testing.
- Inventory of the systems' roles (workloads, required services) to
  judge which controls can break functionality.
- Backup/rollback capability (snapshots, config management) before
  remediation.

## Procedure

1. **Assess first.** Run the benchmark assessment against a
   representative sample to establish the current pass/fail per control.
   Triage failures by CIS level: Level 1 (safe defaults, apply broadly)
   vs. Level 2 (defense-in-depth, may impair functionality — evaluate
   per role).
2. **Harden filesystems.** Apply controls for partition separation
   (`/tmp`, `/var`, `/home` mount options: nodev, nosuid, noexec where
   appropriate), disable unused filesystem types (cramfs, squashfs
   unless needed), and set restrictive permissions on sensitive files.
3. **Minimize services.** Disable and remove unnecessary services and
   inetd/xinetd-managed services; ensure only required ports listen.
   Each listening service is attack surface — document the business
   need for each one that remains.
4. **Apply kernel and network hardening.** Set sysctl controls: IP
   forwarding off (unless the host routes), source-route rejection,
   ICMP redirect rejection, SYN-cookie protection, and reverse-path
   filtering. Harden IPv6 or disable it if unused.
5. **Lock down access and authentication.** Enforce strong password
   policy and account lockout, remove empty-password and legacy
   accounts, restrict root to console/su-path controls, configure sudo
   with least privilege and logging, and set SSH to protocol 2 with
   key-based auth, disabled root login, and idle timeouts.
6. **Enable auditing and logging.** Deploy auditd with rules covering
   privileged commands, authentication events, and sensitive file
   access; forward logs centrally; ensure time synchronization (NTP/
   chrony) so logs are trustworthy.
7. **Roll out in rings.** Apply Level 1 broadly after staging validation;
   pilot Level 2 per server role, measure application impact, and record
   formal exceptions with compensating controls where a control cannot
   be applied.
8. **Monitor for drift.** Re-assess on a schedule and on every
   configuration change; integrate benchmark checks into config-
   management (Ansible/Puppet/Chef) so the baseline is enforced, not
   just documented.

## Expected outputs

- A benchmark assessment report: pass/fail per control with severity.
- Remediation applied per control family, with staging validation
  records.
- Documented exceptions for Level 2 controls with compensating
  controls and expiry dates.
- Config-management enforcement of the baseline and recurring
  compliance reports.

## Pitfalls

- Applying Level 2 controls blindly breaks applications — always pilot
  per role and keep rollback ready.
- Mount options like noexec on /tmp break installers and some
  applications — test, then decide per host class.
- auditd misconfiguration can flood disks or drop events — size rules
  and storage, and monitor auditd health itself.
- SSH hardening can lock out administrators — verify key-based access
  works before disabling password auth, and keep console access.
- Benchmark versions track OS releases — assess against the benchmark
  for your exact distribution and version.

## References

- CIS Benchmarks for Linux distributions (CIS WorkBench)
- NIST SP 800-53 (configuration management and hardening controls)
- NIST SP 800-123: Guide to General Server Security
- Vendor hardening guides for the specific distribution in use
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
