# Analyzing Security Logs with Splunk

See also: analyzing-windows-event-logs-in-splunk.md

## Purpose

Run structured, repeatable investigations of security events inside Splunk: from a detection alert or hypothesis to a scoped, evidence-backed conclusion about what happened, on which hosts, over what time window. This playbook covers the SPL workflow for triage, correlation, and timeline building across firewall, proxy, IDS, authentication, and endpoint sourcetypes.

The emphasis is on reproducibility. Every query is saved with its time range and result count so another analyst — or an auditor — can re-run the investigation and reach the same conclusion.

## When to use

- A SIEM alert fires (IDS signature, authentication anomaly, suspicious process) and needs human triage.
- Threat hunting: testing a hypothesis such as "beaconing to rare external domains in the last 7 days."
- Post-incident scoping: enumerating affected hosts/users after a confirmed compromise.
- Building or tuning detections: validating that a new SPL query catches true positives at an acceptable noise level.
- Shift handoff: packaging an in-progress investigation so the next analyst continues rather than restarts.

## Prerequisites

- Written authorization defining the investigation scope: which indexes/sourcetypes you may query, the time range, and whether user-identifying fields may be exported. Investigations touching employee activity data may need HR/legal sign-off.
- Splunk access with a role that can read the relevant indexes; confirm the search head's timezone settings and the time range picker behavior (Splunk defaults can silently exclude the last minutes).
- A case record (ticket/ID) to attach queries, result counts, and conclusions to — every finding should be reproducible from the saved SPL.
- Chain-of-custody awareness: exported event samples are evidence; record the SPL, time range, and export time for each pull.
- Baseline familiarity with your environment's normal traffic (backup windows, scanner IPs, service accounts) to keep triage fast.

## Procedure

1. Establish the time window and scope. Convert all timestamps to the investigation timezone and set `earliest`/`latest` explicitly in every query (e.g., `earliest=-7d@d latest=now`) rather than relying on the picker. Note the data sources you will cover and the ones you know are missing.
2. Start with a broad count. Run a high-level query over the alert's index to see volume and time distribution: `index=ids earliest=-24h | timechart span=1h count by signature`. A sudden spike or a lone blip both tell you something before you drill in.
3. Pivot on the alert's entities. Extract src_ip, dest_ip, user, host, and process from the alert, then search each across all security indexes: `index=* (src_ip=10.0.5.21 OR user=jdoe) earliest=-7d | stats count by index sourcetype`. This surfaces the same entity's activity in firewall, proxy, auth, and endpoint data.
4. Build the timeline. Correlate with `transaction` or manual sequencing: `index=* earliest=-24h (host=WS042 OR user=jdoe) | sort _time | table _time index sourcetype src_ip dest_ip user action`. Read it chronologically and annotate: first anomaly, lateral movement candidates, exfiltration-shaped flows.
5. Test the hypothesis statistically. For beaconing, compute inter-arrival jitter: `index=proxy dest_ip=<suspect> | sort _time | streamstats current=f last(_time) as prev by dest_ip | eval delta=_time-prev | stats avg(delta) stdev(delta) count by dest_ip`. Low standard deviation at regular intervals is the classic beacon signature.
6. Enrich with lookups. Join internal asset inventory and threat-intel lookups: `| lookup asset_inventory ip as src_ip OUTPUT hostname owner` and `| lookup threat_intel dest_ip OUTPUT threat_name confidence`. Record lookup file versions so enrichment is reproducible.
7. Check for data movement. Where exfiltration is in scope, aggregate bytes by destination: `index=firewall earliest=-7d | stats sum(bytes_out) as out by dest_ip | sort - out | head -20`, and compare against the host or user's historical baseline before calling anything anomalous.
8. Scope the blast radius. Enumerate every host and user that touched the malicious indicator: `index=* <indicator> earliest=-30d | stats dc(host) as hosts dc(user) as users values(host) as host_list`. This becomes the containment list.
9. Validate before concluding. Check for benign explanations (scheduled tasks, backup agents, vulnerability scanners) by comparing against the change-management calendar and known-good baselines. Confirm with at least one independent data source (e.g., endpoint process data corroborating a proxy alert).
10. Turn validated hunts into detections. Convert the final query into a saved search or correlation search with an appropriate cron schedule, throttling, and severity. Record the expected true-positive rate and the tuning notes so the next analyst knows why the thresholds are what they are.
11. Package for handoff. If the investigation spans shifts, write a handoff note in the ticket: current hypothesis, queries already run (with result counts), open questions, and the next three steps. The next analyst should not re-run your work to understand it.
12. Save and document. Save the final SPL as a report or alert, attach all queries and row counts to the case ticket, and write the conclusion in the ticket: what happened, confidence level, affected assets, and recommended containment. Export any evidence samples with query metadata.

## Key tools & commands

- Splunk Search Processing Language (SPL): `index`, `sourcetype`, `search`, `stats`, `timechart`, `transaction`, `streamstats`, `lookup`, `eval`, `where`, `table`, `sort`, `spath` (for JSON fields).
- Example triage query for failed logons: `index=wineventlog EventCode=4625 earliest=-24h | stats count by Account_Name, Workstation_Name | where count > 10`.
- Example rare-domain hunt: `index=proxy earliest=-7d | stats dc(user) as users count by dest_domain | where users < 3 | sort count`.
- Example byte-outlier check: `index=firewall earliest=-7d | stats sum(bytes_out) as out by src_ip | eventstats avg(out) as avg stdev(out) as sd | where out > avg+3*sd`.
- `btool` on the search head (`splunk btool inputs list`) to verify which inputs are actually enabled — a sourcetype you assume exists may never have been onboarded.
- `| metadata type=sourcetypes index=<name>` to confirm what data actually exists in an index before building queries on it.
- Splunk lookup editor or CSV lookups for asset and threat-intel enrichment.
- Saved searches / reports for turning validated queries into recurring detections.

## Expected outputs

- A documented time window, scope statement, and list of covered/missing data sources.
- The saved SPL queries used at each step, with result counts.
- A chronological event timeline with annotated key events.
- Enrichment results (asset owner, threat-intel matches) with lookup versions.
- Data-movement analysis with baseline comparison.
- A blast-radius list of affected hosts and users.
- New or tuned detections created from validated hunts, with tuning notes.
- A shift-handoff note (if applicable) and a written conclusion in the case ticket: findings, confidence, recommended actions.

## Pitfalls

- Implicit time ranges: a query without `earliest`/`latest` inherits the UI picker's default, which may not be what the investigation needs. Always set them explicitly.
- Index gaps: missing sourcetypes (an un-onboarded endpoint log) create false negatives that look like clean results. Verify coverage with `btool` and `| metadata`.
- `transaction` on huge datasets is slow and memory-hungry; prefer `stats`/`streamstats` sequences for large time windows.
- Enrichment lookups that are stale: a threat-intel CSV from last quarter will miss this week's IOCs. Record and check lookup freshness.
- Jumping to containment on a single alert without the benign-explanation check — backup software and scanners mimic attacker patterns constantly.
- Correlating on IP alone behind NAT or DHCP: an internal IP at 09:00 may be a different host by 14:00. Join on host identity where available, and bound time windows tightly.
- Saving a hunt as a detection without throttling: a query that returns 500 rows in triage becomes a 500-alert-per-hour nightmare on a schedule.

## References

- Splunk Search Reference (docs.splunk.com) — authoritative SPL syntax for `stats`, `timechart`, `transaction`, `streamstats`.
- Splunk "Search Manual" — best practices for search performance and time-range handling.
- Splunk Enterprise Security Content Update (ESCU) — reference detection patterns to compare your hunts against.
- MITRE ATT&CK data sources mapping — aligning log types to technique detection (e.g., T1078 Valid Accounts → authentication logs).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
