---
skill_id: cyber_implementing_file_integrity_monitoring_with_aide
name: File Integrity Monitoring with AIDE
description: Deploy AIDE file integrity monitoring on Linux: baselined, tuned, and SOC-integrated.
risk: low
permissions: []
requires_confirmation: false
tags: [linux, fim]
version: 1.0.0
---
## Purpose
Attackers modify binaries, plant persistence, and tamper with configs — changes that are invisible
unless something recorded the "before" state. AIDE (Advanced Intrusion Detection Environment)
creates cryptographic baselines of files and reports deviations: the tripwire for unauthorized
change on Linux. This playbook deploys AIDE with proper baselines, tuned rules, and alerting that
analysts actually read.

## When to use
- Meeting FIM requirements (PCI DSS 11.5, CIS, SOC 2) on Linux systems.
- Detecting unauthorized changes to binaries, libraries, and configurations.
- After incidents involving trojaned binaries or persistence mechanisms.
- As the integrity layer for critical servers (bastions, PKI, build systems, databases).
- Complementing EDR: AIDE catches changes EDR might miss on static infrastructure.

## Prerequisites
- Linux hosts with AIDE installable (package or source) and a secure location for the baseline
  database.
- Defined monitoring scope per host class: which paths matter (binaries, configs, startup) vs. which
  churn legitimately.
- A central log/SIEM destination for AIDE reports.
- Change-control integration: planned changes (patching) must not generate "incident" noise.
- Secure storage for the baseline DB and config: if attackers can modify the baseline, FIM is void.

## Procedure
1. **Install and configure per host class.** Define AIDE configs: strict rules (hash + permissions +
   ownership) for binaries and critical configs; lighter rules (permissions/ownership only) for logs
   and volatile paths. One config per host class (web server, database, bastion) — not
   one-size-fits-all.
2. **Build the baseline on known-good systems.** Initialize the database on freshly built, verified
   hosts (from golden images, post-hardening, pre-production). Record the baseline creation: image
   version, date, builder. A baseline built on a compromised host blesses the compromise —
   provenance matters.
3. **Protect the baseline database.** Store it offline or on read-only/append-only media where
   possible; at minimum, on a separate hardened host with restricted access, plus signed copies.
   Verify database integrity before each check run. An unprotected baseline is the first thing
   attackers target.
4. **Schedule checks appropriately.** Daily checks for critical systems, more frequent (hourly) for
   the most sensitive paths via targeted runs, less for static infrastructure. Balance detection
   latency against I/O load — full-filesystem checks on busy hosts are expensive; scope wisely.
5. **Tune out legitimate churn.** Whitelist package-manager paths during updates (or run checks
   around maintenance windows), exclude logs and caches, and normalize expected changes (logrotate,
   tmp). Every recurring false positive gets a rule, not a shrug — noise kills FIM programs.
6. **Integrate with change control.** Planned changes (patching, config deploys) should trigger:
   pre-change note, post-change baseline update, and suppressed alerting during the window.
   Unplanned changes outside windows are the alerts that matter — the process makes them visible.
7. **Alert with context to the SOC.** Ship AIDE reports to the SIEM: changed files with before/after
   hashes, permissions, and timestamps. Alert priority: binary/library changes (investigate
   immediately), config changes outside windows (investigate), expected-path changes (log).
   Correlate with EDR and auth logs.
8. **Define the investigation workflow.** On unexpected change: isolate if warranted, compare
   against package manager (rpm -V / debsums) to distinguish legitimate updates from tampering,
   check for persistence mechanisms, and determine the change vector. Document the decision tree —
   analysts shouldn't improvise on integrity alerts.
9. **Update baselines deliberately.** After authorized changes, regenerate the baseline with
   change-ticket reference recorded. Baseline updates require approval (two-person for critical
   systems) — casual baseline updates are how tampering gets blessed.
10. **Report integrity posture.** Metrics: hosts with current baselines, check success rate,
    unexpected-change counts with disposition, mean time to investigate, and baseline-age.
    Quarterly: review rule coverage against new software and attack techniques (are we monitoring
    the paths attackers actually use?).

## Expected outputs
- AIDE deployed per host class with scoped, tuned rules and known-good baselines.
- Protected baseline storage with integrity verification.
- Change-control-integrated check scheduling and baseline-update workflow.
- SIEM alerting with prioritized investigation procedures.
- Integrity-posture metrics and quarterly coverage reviews.

## Pitfalls
- Baseline on untrusted hosts: garbage in, blessed compromise out. Build baselines from verified
  golden images.
- Unprotected baseline database: attackers modify it to hide their changes. Offline/signed storage
  is the requirement, not a nicety.
- Monitoring everything: full-filesystem checks are slow and noisy. Scope to security-relevant
  paths.
- No change-control integration: every patch Tuesday becomes an "incident." Planned-change handling
  separates signal from noise.
- Casual baseline updates: "just re-init" after every alert trains the team to bless tampering.
  Approved, ticketed updates only.

## References
- AIDE documentation (configuration, rule syntax, database management)
- NIST SP 800-53 SI-7 (software, firmware, and information integrity)
- PCI DSS v4.0 Requirement 11.5 (file-integrity monitoring)
- CIS Benchmarks (FIM-relevant configuration guidance)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
