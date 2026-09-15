---
skill_id: cyber_hunting_for_data_staging_before_exfiltration
name: Hunting for Data Staging Before Exfiltration
description: Catch the pre-exfiltration staging phase: bulk collection, archive creation, and staging-directory activity on endpoints and shares.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, exfiltration, dfir]
version: 1.0.0
---
## Purpose

Attackers rarely exfiltrate file-by-file — they collect, compress, and
often encrypt data into staging locations first. This staging phase is
noisier and more detectable than the exfiltration itself. This playbook
covers hunting for staging: bulk file access, archive creation, and
staging-directory patterns on endpoints and file shares.

## When to use

- During incident response: staging artifacts reveal what the attacker
  targeted before (or whether) exfiltration occurred.
- Proactive hunting for collection behaviors (T1005/T1074) on
  high-value systems.
- Insider-threat investigations involving data aggregation.
- After detecting exfiltration: work backward to characterize the
  staged dataset.

## Prerequisites

- Endpoint telemetry: file-auditing or EDR file-access events, process
  creation with command lines, and Sysmon file-create events.
- File-share auditing (Windows 4663/5145 or storage-level audit logs)
  for sensitive shares.
- Knowledge of where crown-jewel data lives and who normally accesses
  it in bulk (backup accounts, analytics pipelines).
- Baselines for legitimate bulk operations (backups, ETL jobs).

## Procedure

1. **Identify the crown jewels.** List the shares, databases, and
   directories holding sensitive data. Staging hunts focus here first —
   bulk access to these locations is the highest-value signal.
2. **Hunt bulk access.** Query for accounts or processes reading large
   numbers of files from sensitive shares in short windows, especially
   outside the normal backup/ETL service accounts and schedules.
   Flag interactive users doing backup-scale reads.
3. **Hunt archive creation.** Look for archiving tools (7-Zip, WinRAR,
   tar, PowerShell Compress-Archive) executed with arguments indicating
   bulk compression, particularly with password/encryption flags, and
   output files appearing in temp, public, or web-accessible
   directories.
4. **Hunt staging directories.** Identify directories accumulating
   large archives or copied data inconsistent with their purpose:
   `C:\Windows\Temp`, `C:\PerfLogs`, user Downloads/Desktop folders, or
   newly created directories with data-aggregation patterns. Check for
   recently created large files fleet-wide.
5. **Correlate collection with access.** Tie staging artifacts to the
   source: which shares were read, which accounts were used, and
   whether access was interactive, via a compromised service, or through
   lateral movement. This maps the collection path.
6. **Determine staged vs. exfiltrated.** Compare staged archive hashes
   and sizes against egress telemetry — a staged archive with no
   matching upload may mean exfiltration was interrupted (still an
   incident, but a different notification calculus). Preserve staged
   files as evidence of intent and scope.
7. **Scope the data impact.** Work with data owners to characterize the
   staged dataset: record types, record counts, and regulatory
   categories. This drives breach-notification decisions.
8. **Build staging detections.** Alert on archive-tool execution with
   encryption flags outside approved tooling, bulk reads of sensitive
   shares by interactive users, and large-file creation in known
   staging locations. Add to recurring hunts.

## Expected outputs

- Staging findings: hosts, accounts, staged files (hashes, sizes),
   and source data locations.
- A staged-vs-exfiltrated determination with evidence.
- Data-impact characterization with data-owner sign-off.
- New collection/staging detections with tuning notes.

## Pitfalls

- Backup and ETL jobs look exactly like staging — baseline them
   precisely (account, schedule, destination) before alerting.
- Attackers delete staged archives after exfiltration — check
   unallocated space and USN journal / file-create logs, not just
   current files.
- Encrypted archives cannot be content-inspected — characterize by
   source data accessed, not by archive contents.
- Focusing only on endpoints: database bulk exports (SELECT INTO
   OUTFILE, bcp) are server-side staging — include DB audit logs.
- Staging on cloud storage (S3 buckets, SharePoint) needs cloud audit
   logs — extend the hunt beyond on-prem.

## References

- MITRE ATT&CK: T1005, T1074.001/.002 (collection and staging)
- NIST SP 800-86: forensic techniques in incident response
- Vendor EDR/file-auditing documentation
- Data-classification and breach-notification regulatory guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
