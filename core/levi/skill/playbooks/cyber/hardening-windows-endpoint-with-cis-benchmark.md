---
skill_id: cyber_hardening_windows_endpoint_with_cis_benchmark
name: Hardening Windows Endpoints with CIS Benchmark
description: Apply the CIS Windows benchmark to harden endpoints: account policy, auditing, services, Defender, and firewall controls with safe rollout.
risk: low
permissions: []
requires_confirmation: false
tags: [windows, hardening, compliance]
version: 1.0.0
---
## Purpose

The CIS Benchmarks for Windows provide prioritized hardening controls for
workstations and servers. This playbook guides assessing against the CIS
Windows benchmark, remediating by control family (account policy,
auditing, services, Defender/AV, firewall), and rolling out via Group
Policy or MDM without breaking users or workloads.

## When to use

- Building secure Windows baselines (golden images, Autopilot/Intune
  profiles, Group Policy baselines).
- Compliance programs requiring CIS alignment.
- Post-incident rebuild hardening.
- Measuring and correcting configuration drift across the fleet.

## Prerequisites

- Domain/GPO or MDM (Intune) administration rights and change control.
- A benchmark assessment tool and a pilot OU/device group for staged
  rollout.
- Inventory of endpoint roles and required software to evaluate
  functionality impact.
- Rollback plan: GPO versioning/backups, image restore capability.

## Procedure

1. **Assess the baseline.** Run the benchmark assessment against
   representative workstations and servers. Separate Level 1 (broadly
   safe) from Level 2 (evaluate per role) findings and prioritize
   authentication, auditing, and Defender gaps.
2. **Harden account and password policy.** Enforce password complexity
   and length, lockout thresholds, and (where applicable) LAPS for local
   administrator passwords. Remove/disable unused local accounts and
   the default Administrator/guest accounts per policy.
3. **Configure advanced auditing.** Enable the CIS-recommended audit
   subcategories: logon/logoff, account management, object access for
   sensitive objects, privilege use, and process creation (4688 with
   command-line logging) — the telemetry everything else depends on.
4. **Minimize services and features.** Disable unnecessary services
   (per benchmark lists), remove unused Windows features, and restrict
   autorun/autoplay. Document each retained service's business need.
5. **Enforce Defender and exploit protection.** Ensure Microsoft
   Defender (or approved AV) is active with cloud-delivered protection,
   tamper protection on, and attack-surface-reduction (ASR) rules in
   block mode after a pilot/audit phase. Enable Credential Guard and
   HVCI where hardware supports them.
6. **Configure the host firewall.** Apply the benchmark's firewall
   profile settings; default-deny inbound on untrusted networks and
   restrict SMB/RDP to management subnets. Log dropped packets for
   hunting value.
7. **Roll out in rings.** Pilot in a test OU, then IT, then broad
   deployment — with a pause between rings to catch application and
   usability breakage. Record formal exceptions with compensating
   controls and review dates.
8. **Enforce and monitor drift.** Keep baselines in GPO/MDM as code
   where possible, re-assess on a schedule, and alert on local policy
   tampering or Defender-disablement events.

## Expected outputs

- Benchmark assessment reports per endpoint class.
- GPO/MDM baselines implementing the controls, version-controlled.
- Pilot validation records and a ring-based rollout log.
- Documented exceptions with compensating controls.
- Recurring compliance/drift reports.

## Pitfalls

- ASR rules and command-line auditing break legitimate admin tooling
  and scripts — pilot in audit mode first and build exclusions
  deliberately.
- Credential Guard/HVCI have hardware and driver-compatibility
  requirements — inventory before enforcing.
- Overly aggressive lockout policy enables account-lockout DoS —
  balance with MFA rollout.
- Local-policy edits on domain-joined machines get overwritten by GPO —
  make changes at the right layer.
- Benchmark controls lag new Windows releases — verify applicability
  to your exact OS build.

## References

- CIS Benchmarks for Windows (CIS WorkBench)
- Microsoft Learn: "Security baselines" and Defender/attack-surface-
  reduction documentation
- NIST SP 800-53 (configuration management controls)
- Microsoft Security Compliance Toolkit (baseline GPO references)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
