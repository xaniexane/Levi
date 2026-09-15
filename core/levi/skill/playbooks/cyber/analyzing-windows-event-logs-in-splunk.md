# Analyzing Windows Event Logs in Splunk

See also: analyzing-security-logs-with-splunk.md

## Purpose

Investigate Windows security events at scale inside Splunk: authentication activity, process
creation, account management, and lateral-movement indicators across the fleet. This playbook gives
the core SPL patterns for the Windows Event Log sourcetypes (`WinEventLog:Security`,
`WinEventLog:System`, `WinEventLog:Application`, Sysmon) and the triage workflow that turns them
into findings.

Windows logs are the highest-volume, highest-value telemetry in most enterprises — and the easiest
to misread. The playbook's guardrails (coverage checks, field-name verification, baseline
allowlists) exist because every one of these queries fails silently without them.

## When to use

- Triage of authentication alerts: brute force, password spraying, impossible-travel logons.
- Hunting lateral movement: remote logons, PsExec/WMI usage, new service creation across hosts.
- Incident scoping: every host a compromised account touched, every account that touched a
  compromised host.
- Validating endpoint detections with independent Windows telemetry.
- Building scheduled detections from validated hunt queries.

## Prerequisites

- Written authorization for the investigation scope: which hosts/OUs, what time range, and whether
  account-identifying data may be exported. Windows logs are rich in personal identifiers — confirm
  the privacy handling with HR/legal where required.
- Splunk access to the Windows event indexes with the Universal Forwarder inputs confirmed healthy
  (`index=_internal source=*splunkd* "WinEventLog"` errors, or the deployment server's forwarder
  management view). Missing forwarders create blind hosts.
- A case ticket to attach SPL, result counts, and conclusions to; every exported event sample gets
  its query and time range recorded.
- Baseline knowledge of your environment's normal patterns (service accounts that log on everywhere,
  admin jump hosts) to avoid false positives.
- Confirmation that command-line logging is enabled via GPO ("Include command line in process
  creation events") — without it, 4688 command-line hunts are blind.

## Procedure

1. Verify log health first. Check forwarder coverage and event volume per host before trusting a
   negative result: `index=wineventlog earliest=-24h | stats count by host | where count < 100`.
   Hosts with near-zero volume are blind spots, not clean hosts. Also confirm the EventCodes you
   need are actually collected (some shops filter 4688 for volume).
2. Verify field names. Run `index=wineventlog EventCode=4688 earliest=-1h | fieldsummary` (or `|
   table * | head 1`) to confirm the actual field names in your TA — `Account_Name` vs. `user`,
   `New_Process_Name` vs. `process` — before building queries on assumed names.
3. Triage authentication failures. Hunt password spraying and brute force on EventCode 4625:
   `index=wineventlog EventCode=4625 earliest=-24h | stats dc(Account_Name) as users count by src_ip
   | where users > 5` (spraying: many users, one source) and `| stats count by Account_Name src_ip |
   where count > 20` (brute force: many attempts, one account). Exclude known scanner IPs.
4. Review successful logons in context. For EventCode 4624, filter to interesting Logon_Types: Type
   10 (RDP), Type 3 (network), and Type 2 (interactive) outside business hours or on servers:
   `index=wineventlog EventCode=4624 Logon_Type=10 earliest=-7d | stats count by Account_Name
   Workstation_Name src_ip`. First-time RDP sources per account deserve review.
5. Hunt process-creation anomalies. If 4688 (or Sysmon EventCode 1) is collected: look for LOLBins
   and unusual parents — `index=wineventlog (EventCode=4688 OR EventCode=1) earliest=-24h | stats
   count by New_Process_Name Parent_Process_Name | sort - count` — and review command lines
   containing encoded PowerShell (`-enc`, `-EncodedCommand`), `certutil -decode`, or `mshta`.
6. Track account and privilege changes. Review EventCodes 4720 (account created), 4728/4732/4756
   (group membership), 4672 (special privileges assigned), and 7045 (service installed, System log):
   `index=wineventlog EventCode IN (4720, 4728, 4732, 4756, 4672, 7045) earliest=-7d | table _time
   host EventCode Account_Name TargetUserName`. New privileged accounts and new services are
   persistence until proven otherwise.
7. Hunt lateral movement patterns. Look for: the same account logging on (4624 Type 3/10) to many
   hosts in a short window, `psexec`-service names in 7045, and WMI-originated process creation
   (parent `WmiPrvSE.exe`). Chain the logons chronologically per account to reconstruct the movement
   path.
8. Scope laterally. From a compromised account or host, enumerate every logon and process event:
   `index=wineventlog (Account_Name=compromised OR host=compromised) earliest=-30d | stats
   values(host) as hosts values(Account_Name) as accounts by _time` — then expand to each newly
   found host iteratively. Two hops usually bounds the incident.
9. Correlate with network data. Join the Windows findings against firewall/proxy indexes on IP and
   time: confirm that a suspicious RDP logon (4624 Type 10) aligns with an external source IP in the
   firewall log, and that process-creation of a downloader aligns with the proxy log's download
   event.
10. Promote validated hunts to detections. Convert the final queries into scheduled saved searches
    with throttling, severity, and baseline allowlists (service accounts, scanners). Record expected
    true-positive rates and tuning notes so future analysts understand the thresholds.
11. Conclude and hand off. Write the ticket up: timeline of malicious authentication/process events,
    affected hosts and accounts, the persistence mechanisms found (with EventCode evidence), and
    containment actions (disable accounts, isolate hosts, reset credentials). Save the SPL as a
    report for reuse.

## Key tools & commands

- Core SPL patterns: 4625 spray/brute-force aggregations, 4624 Logon_Type pivots, 4688/Sysmon-1
  process/command-line hunts, 4720/4728/4732/4756/4672/7045 change tracking.
- `index=wineventlog EventCode=4688 earliest=-1h | table _time host Account_Name New_Process_Name
  CommandLine Parent_Process_Name` — the standard process-creation review shape (field names vary by
  TA; verify with `| fieldsummary`).
- Splunk's `fieldsummary` and `| metadata type=hosts index=wineventlog` for coverage checks.
- Lookup enrichment: `| lookup ad_users sAMAccountName as Account_Name OUTPUT department title` for
  account context; asset inventory lookups for host ownership.
- `eventstats` for per-entity baselining, e.g. flagging accounts whose daily 4624 count deviates
  from their own history.
- Saved searches turning validated hunts into scheduled alerts.

## Expected outputs

- A forwarder/event-volume health check with blind hosts identified.
- A field-name verification record for the TA in use.
- Authentication triage results: spraying/brute-force candidates with evidence.
- Anomalous logon findings (RDP/network/interactive outliers).
- Process-creation findings with command-line evidence.
- Account/privilege/service change findings.
- Lateral-movement reconstruction: per-account movement paths.
- A lateral-movement scope: hosts and accounts, two hops out.
- Network-log correlation confirming or refuting each finding.
- Promoted detections with throttling, allowlists, and tuning notes.
- A written conclusion with containment actions and reusable saved searches.

## Pitfalls

- Field-name drift: the Splunk Add-on for Windows vs. other TAs name fields differently
  (`Account_Name` vs. `user`, `New_Process_Name` vs. `process`). Run `| fieldsummary` on your data
  before building queries.
- 4688 command-line logging must be enabled by GPO ("Include command line in process creation
  events") — without it, the field is empty and your hunt is blind. Verify, don't assume.
- Service accounts and vulnerability scanners generate enormous 4624/4625 volume; build allowlists
  from the baseline before alerting.
- Logon Type 3 (network) is extremely noisy in Windows environments — filter to sensitive hosts or
  pair with another indicator.
- Timezone mismatches between Splunk's `_time` and the ticket timeline: confirm the search head
  timezone and state it in findings.
- DHCP reassignment: an IP attributed to a host on Monday may belong to another host on Friday.
  Bound time windows tightly and prefer host identity over IP.
- Alerting on 4624 Type 10 without baselining admin jump hosts: legitimate admins RDP constantly.
  First-seen (account, source) pairs are the signal, not RDP itself.

## References

- Microsoft documentation: Event IDs 4624, 4625, 4688, 4720, 4728, 4732, 4756, 4672, 7045 — what
  each event records.
- Splunk Add-on for Microsoft Windows documentation — sourcetypes, field names, and inputs
  configuration.
- MITRE ATT&CK: T1078 (Valid Accounts), T1021 (Remote Services), T1059.001 (PowerShell) mapped to
  these EventCodes.
- NSA/SANS Windows logging guidance for enabling command-line auditing via GPO.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
