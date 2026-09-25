---
skill_id: sys_linux_cron_systemd
name: Linux cron and systemd
description: Scheduled tasks and services: cron for periodic jobs, systemd for everything serious.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, os]
version: 1.0.0
---
# Linux cron and systemd

## Purpose

Scheduled tasks and services: cron for periodic jobs, systemd for everything serious.

## Overview

cron runs commands on a schedule. crontab -e edits your table; each line is minute hour day-of-month month day-of-week plus the command (0 2 * * * runs daily at 02:00). Cron's environment is minimal - PATH is tiny and no shell profile loads - so use absolute paths and set needed variables at the top of the crontab. Output mails to the owner (or vanishes); redirect to a log file deliberately. systemd is the modern service manager: units describe services (.service), timers (.timer, cron's successor with calendar expressions and jitter), mounts, and more. systemctl start/stop/enable/status controls units; journalctl -u name reads their logs - no more hunting log files. A minimal service unit sets ExecStart, Restart=on-failure, and a dedicated User=. Timers beat cron for anything needing dependencies, randomized delays (RandomizedDelaySec), or 'run if missed during downtime' (Persistent=true). Debugging order for a dead service: systemctl status (exit code), journalctl -u (logs), then run ExecStart by hand. Prefer systemd for services; cron remains fine for simple user-level periodic scripts.

## Quick reference

- crontab -e; fields: min hour dom month dow. 0 2 * * * = daily 02:00.

- Cron env is minimal: absolute paths, set vars at the top.

- Redirect cron output to logs deliberately; default mails it.

- systemctl start/stop/enable/status; journalctl -u name for logs.

- Service unit: ExecStart, Restart=on-failure, dedicated User=.

- systemd timers: cron successor with jitter + Persistent missed runs.


## Worked example

A cron line and a systemd service + timer:

```
# crontab: backup daily at 02:30, log to file
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * /opt/backup.sh >> /var/log/backup.log 2>&1

# /etc/systemd/system/backup.service
[Unit]
Description=Daily backup
[Service]
Type=oneshot
User=backup
ExecStart=/opt/backup.sh

# /etc/systemd/system/backup.timer
[Unit]
Description=Run backup daily
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
```

- Cron needs PATH set: its default is minimal.

- Type=oneshot + timer: the systemd-native cron replacement.

- Persistent=true runs the job if the machine was off at schedule time.


## Common mistakes

- Relative paths and unqualified commands in crontab.
  Fix: Absolute paths everywhere; set PATH at the top of the crontab.

- No output handling: failures mail root or vanish silently.
  Fix: Redirect to a log file and monitor it.


## Quick checks

Q: My cron job works by hand but not from cron - why?
A: Environment. Cron has a tiny PATH, no profile, and a different cwd. Use absolute paths, set PATH/variables in the crontab, and log output so you can see the actual error.


Q: cron or systemd timer for a new periodic job?
A: systemd timer when you want logging via journalctl, dependencies, jitter, or catch-up runs. cron for quick user-level scripts where those do not matter.


## Mental model

cron is an alarm clock: simple, rings on schedule, knows nothing about whether you are home. systemd is a building manager: it starts services, restarts them when they fail, keeps their logs, and its timers are alarm clocks that ring even if the power was out (Persistent).
