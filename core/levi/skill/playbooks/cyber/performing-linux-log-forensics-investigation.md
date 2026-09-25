---
skill_id: cyber_performing_linux_log_forensics_investigation
name: Linux Log Forensics Investigation
description: Investigate intrusions using Linux system and application logs.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, linux, logs]
version: 1.0.0
---
# Linux Log Forensics Investigation

## Purpose

Linux systems record intrusions across many logs — auth, syslog, auditd,
web server, and application logs — but only if you know where to look
and how to correlate them. This playbook structures a log-driven
investigation of a suspected Linux compromise, from preservation to
timeline.

## When to use

- A Linux server shows compromise indicators (unknown processes,
  unexpected outbound traffic, defacement).
- Validating EDR or IDS alerts with on-host log evidence.
- Scoping how long an attacker had access and what they touched.
- Post-incident review of detection gaps in Linux logging.

## Prerequisites

- Authorization to examine the host's logs, including user activity
  data.
- Forensic copies of logs (or centralized copies in the SIEM) —
  investigate copies, not live files an attacker may be modifying.
- Time synchronization verified: confirm the host's clock against a
  trusted source before building timelines.

## Procedure

1. Preserve logs first: copy `/var/log/auth.log` (or secure),
   `/var/log/syslog`, auditd logs, and application logs to the
   analysis workstation with hashes; snapshot the VM if possible.
2. Establish the anchor: find the earliest suspicious event — a
   successful login from an unusual IP, a new user creation, a web
   shell request — and treat it as the tentative intrusion start.
3. Review authentication logs: successful and failed SSH logins,
   new users/groups, sudo usage, and SSH key additions to
   authorized_keys; flag logins outside normal hours or geographies.
4. Examine auditd trails: execve of suspicious binaries, writes to
   cron, systemd units, and profile scripts, and network connect
   syscalls from unexpected processes.
5. Correlate application logs: web access logs around the anchor time
   for exploit patterns, SQL injection, or webshell access; check
   for log gaps that suggest tampering.
6. Check for log tampering: missing time ranges, truncated files,
   cleared histories, and journald vacuuming — the absence of logs
   is itself evidence.
7. Build the timeline: merge host logs with firewall, proxy, and SIEM
   data into one chronological view; each attacker action should have
   at least one corroborating source.
8. Determine scope and persistence: list all access vectors used,
   persistence mechanisms installed, and data accessed — this drives
   the containment and eradication plan.

## Expected outputs

- A correlated timeline from initial access to discovery.
- Findings per log source with evidence citations.
- A scope statement: access vectors, persistence, data impact.
- Logging-gap recommendations for detection improvement.

## Pitfalls

- Investigating live logs on a compromised host: assume the attacker
   can see and alter them — work from preserved copies.
- Ignoring clock skew: a host five minutes off breaks correlation
   with network logs.
- Stopping at the first finding: check for additional access vectors
   and persistence before declaring scope.
- Overlooking rotated or compressed logs: the intrusion may predate
   the current log files.

## References

- NIST SP 800-61, Computer Security Incident Handling Guide
- NIST SP 800-92, Guide to Computer Security Log Management
- Linux auditd documentation (auditctl, ausearch, aureport)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
