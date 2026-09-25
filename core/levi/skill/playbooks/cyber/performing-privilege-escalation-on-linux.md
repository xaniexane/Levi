---
skill_id: cyber_performing_privilege_escalation_on_linux
name: Linux Privilege Escalation Hardening
description: Audit Linux systems for privilege escalation vectors and harden them, plus detect escalation attempts in logs.
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privesc, hardening]
version: 1.0.0
---

## Purpose
- This playbook is defensive: audit and harden Linux privilege boundaries and detect escalation attempts. It does not cover exploiting these weaknesses without authorization.
- Systematically find the sudo, SUID, capability, and kernel weaknesses that enable Linux privilege escalation.
- Harden systems so common escalation paths are closed by configuration, not just by patching.
- Detect escalation attempts through audit logging and alerting.

## When to use
- When hardening Linux servers, especially internet-facing or multi-user systems.
- During authorized assessments where Linux privilege boundaries are in scope.
- After incidents involving Linux privilege escalation, to close the exploited paths fleet-wide.
- When building a secure Linux baseline or gold image.

## Prerequisites
- Administrative access to the target systems or their configuration management source of truth.
- A Linux hardening baseline such as CIS Benchmarks for the distribution in use.
- Centralized logging with sudo, authentication, and auditd events collected.
- A test system for validating hardening changes before fleet rollout.

## Procedure
1. Inventory privilege boundaries: sudoers rules, SUID and SGID binaries, file capabilities, and polkit policies.
2. Review sudo configuration for NOPASSWD entries, overly broad commands, and rules that allow shell escapes.
3. List SUID/SGID binaries and compare against a known-good baseline; investigate any additions.
4. Check file capabilities for binaries granted dangerous capabilities like CAP_SYS_ADMIN or CAP_DAC_OVERRIDE.
5. Review cron jobs, systemd timers, and services running as root with writable components.
6. Assess kernel and package patch levels for known local privilege escalation CVEs.
7. Check for credentials in world-readable files, shell history, and environment variables.
8. Harden: remove unnecessary SUID bits, tighten sudo to specific commands, drop unneeded capabilities, and enforce least privilege on cron and services.
9. Enable and tune auditing: auditd rules for privilege-relevant syscalls, sudo logging to a central collector, and alerts on suspicious patterns.
10. Validate hardening in the test environment, then roll out via configuration management with a rollback plan.

## Expected outputs
- A Linux privilege-boundary audit with findings and risk ratings.
- Hardening changes applied via configuration management with test evidence.
- Audit and alerting coverage for escalation attempts.
- A hardened gold image or Ansible role encoding the validated configuration.
- A fleet-wide compliance report showing hardening coverage.

## Pitfalls
- Breaking production by stripping SUID bits or tightening sudo without testing application impact.
- Focusing on exotic vectors while missing weak sudo rules, which cause most real escalations.
- Collecting audit logs nobody reviews; pair new audit rules with alerts and a review cadence.

## References
- NSA Linux hardening guidance
- CIS Benchmarks for Linux distributions
- MITRE ATT&CK privilege escalation techniques for Linux, https://attack.mitre.org/tactics/TA0004/
- Linux auditd documentation and rule guides
- NIST SP 800-123 Guide to General Server Security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
