# Analyzing Linux System Artifacts

## Purpose

Even without malware samples, a Linux host records what happened: logins,
command history, scheduled jobs, file timestamps, and service journals. This
playbook shows how to collect and correlate these system artifacts into a
timeline of user and attacker activity during an investigation.

## When to use

- Scoping a suspected Linux compromise when no malware has been found yet.
- Building a timeline of attacker activity from host artifacts.
- Insider-threat or policy-violation reviews (with proper authorization).
- Validating EDR/SIEM alerts with on-host ground truth.

## Prerequisites

- Written authorization to examine the host and user activity data; command
  histories and login records are privacy-sensitive — confirm scope with
  legal/HR where required.
- Forensic copies, not live queries, for anything you will rely on: image the
  disk or copy artifacts with hashes; live `last`/`history` output is
  volatile and attacker-modifiable.
- A timeline tool (Plaso/log2timeline) on the analysis workstation for
  merging heterogeneous artifacts.

## Procedure

1. Capture volatile state first: `last`, `lastb`, `w`, `ss -tulpn`, `ps auxf`,
   and `systemctl list-units --failed` — then move to disk artifacts.
2. Collect authentication artifacts: `/var/log/auth.log` (Debian) or
   `/var/log/secure` (RHEL), plus `/var/log/wtmp` (`last -f`), `/var/log/btmp`
   (`lastb`), and `/var/log/lastlog` (`lastlog`). Note successful logins from
   unusual IPs/times and brute-force runs in `lastb`.
3. Collect user-activity artifacts per account: `~/.bash_history` (note it is
   truncated and easily edited — corroborate), `~/.ssh/known_hosts` and
   `authorized_keys` (new keys = persistence), and shell configs (`.bashrc`,
   `.profile`) for injected commands.
4. Collect persistence artifacts: `/etc/crontab`, `/etc/cron.d/*`,
   `/var/spool/cron/*`, systemd units in `/etc/systemd/system/` (compare
   against vendor units), and `/etc/rc.local`.
5. Collect identity artifacts: `/etc/passwd`, `/etc/shadow`, `/etc/group`,
   `/etc/sudoers` and `/etc/sudoers.d/` — new UID-0 accounts, NOPASSWD
   additions, and unexpected sudoers entries.
6. Collect service logs: `journalctl --since <date>` (or `/var/log/syslog`,
   `/var/log/messages`), web-server access/error logs, and SSH daemon logs;
   correlate with the auth timeline.
7. Build a filesystem timeline with Plaso: `log2timeline.py --storage-file
   case.plaso /mnt/evidence` then `psort.py` to export a sorted CSV.
   Focus on MACB timestamps in attacker-relevant paths (`/tmp`, `/dev/shm`,
   web roots, home directories).
8. Hunt for timestomping: files whose mtime/ctime ordering is impossible
   (ctime newer than mtime after claimed "old" modification) or clusters of
   files with identical timestamps in odd locations.
9. Merge everything into one master timeline: logins → commands → file
   modifications → persistence → exfiltration indicators (large outbound
   transfers in firewall/proxy logs).
10. Write findings as: what happened, when (UTC), by which account/process,
    with the artifact cited for each assertion.

## Key tools & commands

- `last`, `lastb`, `lastlog` — login history from wtmp/btmp/lastlog.
- `journalctl --since/--until`, `--unit` — systemd journal queries.
- `log2timeline.py` / `psort.py` / `pinfo.py` — Plaso timeline generation.
- `stat`, `find -newermt`, `ls -l --time-style=full-iso` — timestamp inspection.
- `ss -tulpn`, `lsof -i` — listening sockets and open files (volatile).
- `aureport --auth --summary -i` — authentication summary cross-check.

## Expected outputs

- Master timeline (CSV) merging logins, commands, file events, and service logs.
- Attacker activity narrative with per-claim artifact citations.
- Persistence mechanisms found, with removal/rotation recommendations.
- Gaps noted explicitly (e.g., "bash_history absent — possibly cleared").

## Pitfalls

- `~/.bash_history` is written at shell exit and trivially edited or
  unset (`unset HISTFILE`) — never treat its absence as proof of inactivity.
- Timestamps in different timezones across logs; normalize everything to UTC
  before sequencing events.
- Timestomping defeats naive "recently modified" hunts — use ctime/inode
  change times and Plaso's full MACB set, not mtime alone.
- Live-host queries (`ps`, `ss`) reflect the current moment only and can be
  deceived by rootkits — pair with disk/memory forensics.
- Over-collecting user data beyond the authorized scope; stick to the
  accounts, hosts, and time window in the authorization.

## References

- Plaso documentation (plaso.readthedocs.io)
- MITRE ATT&CK: T1078 (Valid Accounts), T1053.003 (Cron), T1033-adjacent
  system-owner discovery via artifacts
- NIST SP 800-86 (forensic artifact handling)
- Linux man pages: `last(1)`, `journalctl(1)`, `stat(1)`

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
