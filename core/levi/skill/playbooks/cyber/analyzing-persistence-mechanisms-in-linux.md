---
skill_id: cyber_analyzing_persistence_mechanisms_in_linux
name: Analyzing Persistence Mechanisms in Linux
description: Enumerate Linux persistence: systemd, cron, rc files, and kernel modules.
risk: low
permissions: []
requires_confirmation: false
tags: [linux, malware-analysis]
version: 1.0.0
---
# Analyzing Persistence Mechanisms in Linux

## Purpose

Systematically enumerate every common Linux persistence location — systemd units, cron, rc scripts, shell profiles, SSH keys, kernel modules, and containers — to find attacker footholds on a compromised host.

## When to use

- A Linux host is confirmed or suspected compromised and you must ensure complete eviction, not just killing the visible process.
- Post-incident hardening review of a rebuilt host's persistence surface.
- Threat hunting: sweeping fleets for known persistence patterns.

## Prerequisites

- Written authorization; work from a forensic image or a live host you are authorized to inspect (prefer offline image analysis to avoid tipping off the attacker).
- Root-level access or a mounted image; baseline knowledge of the distribution's defaults.
- Chain-of-custody if evidence will be used beyond internal remediation.

## Procedure

1. Check systemd for rogue or modified units — the most common modern persistence:
   `systemctl list-unit-files --type=service --state=enabled`
   Inspect anything unfamiliar: `systemctl cat <name>` and verify the `ExecStart` binary's hash and path. Also check user units in `~/.config/systemd/user/` and timers: `systemctl list-timers --all`.
2. Review cron at every level:
   `cat /etc/crontab; ls -la /etc/cron.d/ /etc/cron.hourly/ /etc/cron.daily/; for u in $(cut -f1 -d: /etc/passwd); do crontab -u $u -l 2>/dev/null; done`
   Flag entries calling scripts in `/tmp`, `/dev/shm`, or with base64/curl pipes.
3. Inspect shell startup files for all users: `~/.bashrc`, `~/.bash_profile`, `~/.profile`, `/etc/profile`, `/etc/bash.bashrc`, plus `/etc/profile.d/`. Look for appended lines invoking hidden binaries.
4. Check SSH persistence: `~/.ssh/authorized_keys` for every user (unknown keys = backdoor accounts), and `/etc/ssh/sshd_config` for `PermitRootLogin`, rogue `AuthorizedKeysFile`, or added `Match` blocks.
5. Look for new or modified user accounts: `cat /etc/passwd` — UID 0 duplicates, unfamiliar names; check `/etc/shadow` for passwordless or recently changed entries (field timestamps).
6. Review init scripts and rc.local: `/etc/rc.local`, `/etc/init.d/` — legacy but still abused.
7. Inspect kernel modules: `lsmod` against the distribution baseline; check `/etc/modules-load.d/` and `/etc/modprobe.d/` for forced loads.
8. Check shared-library preloads: `/etc/ld.so.preload` — any entry here is a major red flag (userland rootkit technique).
9. Review package manager integrity: `rpm -Va` or `debsums -c` / `dpkg -V` to find modified system binaries; reinstall confirmed-tampered packages from trusted media.
10. Look at containers and scheduled jobs outside cron: `docker ps -a`, `kubectl get cronjobs --all-namespaces`, `atq`, and `systemd` timers from step 1.
11. Check network-level persistence: rogue `iptables`/`nftables` rules, systemd-networkd configs, and `/etc/hosts` modifications pointing legitimate names at attacker IPs.
12. Check for malicious PAM modules and NSS configuration: additions under `/etc/pam.d/` and changes to `/etc/nsswitch.conf` enable credential interception at login.
13. Review sudoers for privilege persistence: `visudo -c` to validate, then inspect `/etc/sudoers` and `/etc/sudoers.d/` for NOPASSWD grants to unexpected users.
14. Inspect udev rules in `/etc/udev/rules.d/` — device-triggered command execution is a rarely checked persistence vector.
15. Check cron alternatives: `at` jobs (`atq`), `anacron` (`/etc/anacrontab`), and batch queues — attackers use the scheduler you forgot.
16. Review `/etc/security/access.conf` and MOTD scripts: modified access controls or login scripts can hide or enable access.
17. Inspect shared-object hijacking beyond `ld.so.preload`: writable directories in `/etc/ld.so.conf.d/` and `LD_LIBRARY_PATH` in service unit environments.
18. Check `/etc/cron.allow` and `/etc/cron.deny`: restrictive files that vanished indicate tampering with the scheduling policy itself.
19. Review kernel command-line parameters (`/proc/cmdline`): malicious `init=` entries or module parameters persist across reboots.
20. Check for lingering sessions: `loginctl list-sessions` and `who` — an attacker session may still be active.
21. For each finding, record: location, content, file timestamps, owning package (or "not owned by any package"), and hash. Remove only after evidence preservation, and re-verify after reboot that nothing returns.

## Key tools & commands

- `systemctl list-unit-files`, `systemctl cat`, `systemctl list-timers --all` — systemd persistence.
- `crontab -u <user> -l`, `/etc/cron.d/*` — cron review.
- `ls -la ~/.ssh/authorized_keys` (all users) — SSH key backdoors.
- `cat /etc/ld.so.preload` — library preload rootkits.
- `rpm -Va` / `dpkg -V` — package integrity verification.
- `lsmod`, `/etc/modules-load.d/` — kernel module persistence.
- `visudo -c` — validate the sudoers configuration before and after review.
- `ls -la /etc/udev/rules.d/` — device-triggered persistence.
- `grep -R` over `/etc/pam.d/` — PAM module additions.
- AIDE (`aide --check`) — file-integrity monitoring for ongoing assurance.
- `docker ps -a`, `atq` — container and at-job persistence.

## Expected outputs

- Complete persistence inventory: every finding with location, content, timestamps, hash.
- Package-ownership verdict per modified binary.
- Evidence-preserved copies of all persistence artifacts.
- PAM, sudoers, and udev findings with content and timestamps.
- Removal actions taken and post-reboot verification results.
- Hardening recommendations for the persistence surface found abused.

## Pitfalls

- Killing the malware process but missing its systemd timer — it comes back on schedule.
- Checking only root's cron and missing a service account's user crontab.
- Trusting `ls` output on a live compromised host — userland rootkits lie; prefer offline image analysis or static binaries.
- Forgetting containers: a malicious container with host mounts survives host-level cleanup.
- Removing persistence before preserving evidence — image first, clean second.
- Breaking sudo with a bad edit — always use `visudo`, never edit the file directly.
- Trusting package-manager verification when the package database itself may be tampered — verify from offline media.
- Skipping the reboot verification — some persistence only triggers on boot.
- Racing the attacker: re-added persistence while you clean — isolate the host first.
- Reinstalling packages from a compromised mirror — verify package signatures.
- Missing cron for deleted users — check `/var/spool/cron/` directly.
- Overlooking `~/.config/autostart` on Linux desktops — GUI session persistence.
- Documenting findings without hashes — hashes make the record defensible.
- Checking only systemd and missing SysV init on older distros.
- Forgetting `~/.profile` vs. `~/.bashrc` — login vs. interactive shells differ.
- Not checking root's `authorized_keys` separately — the highest-value target.
- Overlooking `cron.allow` semantics — its absence changes everything.
- Trusting `systemctl is-enabled` on a compromised host — verify unit files directly.
- Missing kernel-module persistence via initramfs — rebuild and compare.
- Checking only systemd — cron, at, shell rc files, and `ld.so.preload` are classics too.
- Container persistence via restarted images — the host, not the container, is the anchor.
- Timestamps lie — verify with the package manager (`rpm -V`, `debsums`), not mtime.
- Overlooking user-level units in `~/.config/systemd/user/`.
- Kernel-mode rootkits hiding the persistence — cross-check from a live image or memory dump.
- SSH `authorized_keys` in non-standard homes — enumerate all users, not just root.

## References

- MITRE ATT&CK T1543.002 (Systemd Service), T1053.003 (Cron), T1098 (Account Manipulation), T1556 (Modify Authentication Process), T1574.006 (Dynamic Linker Hijacking)
- Linux-PAM documentation: https://linux-pam.org
- systemd.unit man page — service unit reference
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide
- Distribution hardening guides (CIS Benchmarks for Linux)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
