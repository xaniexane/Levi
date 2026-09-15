# Analyzing Linux Audit Logs for Intrusion

## Purpose

The Linux Audit daemon (`auditd`) records security-relevant syscalls — process
execution, file access, privilege changes, network connections — with the
fidelity needed to reconstruct an intrusion. This playbook shows how to write
useful audit rules, search the logs with `ausearch`/`aureport`, and trace an
attacker's path through a Linux host.

## When to use

- Investigating a suspected Linux intrusion: find initial execution, lateral
  movement, and persistence on the host.
- Validating whether a vulnerability (e.g., a web-shell upload) was exploited.
- Building host-level detections to complement EDR coverage.

## Prerequisites

- Written authorization to access the host's audit logs; audit data records
  user activity and may be subject to privacy/workplace-monitoring rules —
  confirm with legal/HR where required.
- Root access (audit logs are root-readable); the audit ruleset in effect
  during the incident (`/etc/audit/rules.d/` + `auditctl -l` output at the time).
- Chain of custody: copy `/var/log/audit/audit.log*` with hashes before analysis.

## Procedure

1. Confirm what was being audited during the incident window:
   `auditctl -l` (live rules) and the files in `/etc/audit/rules.d/`.
   If `execve` and key file watches were not enabled, scope your conclusions
   accordingly — absence of evidence is not evidence of absence.
2. Preserve the logs: copy `audit.log` and rotated `audit.log.*`, hash them,
   and work on the copies.
3. Get an overview with `aureport`:
   `aureport --start <date> --summary -i` for event-type counts, then
   `aureport --auth --summary -i` for authentication anomalies and
   `aureport --avc` for SELinux denials.
4. Trace process execution around the suspected compromise:
   `ausearch -m EXECVE -ts <start> -te <end> -i`
   Look for shells spawned by web-server users, interpreters (`python`, `perl`)
   with `-c` one-liners, and binaries executed from `/tmp`, `/dev/shm`, `/var/tmp`.
5. Follow the session: pick the suspicious PID/auid and run
   `ausearch --pid <pid> -i` and `ausearch --session <ses> -i` to see everything
   that process and login session did.
6. Check for persistence and privilege changes:
   - `ausearch -m ADD_USER,DEL_USER,ADD_GROUP -i` (account changes)
   - watches on cron: rules like `-w /etc/crontab -p wa -k cron`
   - `ausearch -k <your-key>` for any custom keys (e.g., `-k identity` on
     `/etc/passwd`, `-k modules` on `init_module`/`finit_module` syscalls).
7. Look for credential access: reads of `/etc/shadow` (`-w /etc/shadow -p r`),
   and `EXECVE` of dumping tools.
8. Correlate network activity: `ausearch -m SOCKADDR` or type=NETFILTER_PKT if
   enabled, cross-checked with firewall and NetFlow/proxy logs.
9. Reconstruct the timeline: merge `ausearch` output (use `-i` for readable
   timestamps, then convert to UTC) with auth logs (`/var/log/auth.log` /
   `secure`) and web-server access logs.
10. Harden the ruleset afterward: ensure permanent rules cover `execve`,
    identity files, cron, kernel-module loading, and time-change syscalls
    (`adjtimex`, `settimeofday` — attackers change clocks to poison logs).

## Key tools & commands

- `ausearch -m EXECVE -ts today -i` — today's process executions, interpreted.
- `ausearch -k <key> --start <date>` — search by rule key.
- `ausearch --pid <pid>`, `--ppid`, `--session`, `--uid`, `--auid` —
  pivoting on process identity.
- `aureport --auth --summary -i`, `aureport --file --summary -i` — summaries.
- `auditctl -l` / `/etc/audit/rules.d/*.rules` — active and persistent rules.
- `augenrules --load` — compile rules.d into the active ruleset.
- Example rule: `-a always,exit -F arch=b64 -S execve -k exec`

## Expected outputs

- Intrusion timeline: initial execution → actions → persistence, with audit
  event IDs cited.
- List of attacker processes, files touched, accounts changed.
- IOCs extracted (binary hashes, IPs, dropped-file paths).
- Ruleset gap analysis and hardened `rules.d` additions.

## Pitfalls

- `auditd` was not running or rules were minimal during the incident — check
  `service auditd status` history and say so explicitly rather than
  over-interpreting silence.
- Log rotation may have deleted the window; check `max_log_file` settings and
  archived logs before concluding.
- High-volume `execve` auditing can drop events under load (`lost` counter in
  `auditd` status) — note any backlog failures.
- auid (audit UID) vs uid: `auid` tracks the original login user through `su`/
  `sudo` — use `--auid` to attribute actions to the real user.
- Timestamps are epoch by default; always use `-i` or convert, and normalize
  to UTC before merging with other sources.

## References

- `auditd(8)`, `ausearch(8)`, `aureport(8)`, `auditctl(8)` man pages
- MITRE ATT&CK: T1059 (Command and Scripting Interpreter), T1548 (Abuse
  Elevation Control Mechanism), T1136 (Create Account)
- Red Hat "System Auditing" documentation (audit rule examples)
- CIS Linux Benchmarks (auditd configuration controls)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
