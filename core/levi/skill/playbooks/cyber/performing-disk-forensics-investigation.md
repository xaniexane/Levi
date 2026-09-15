---
skill_id: cyber_performing_disk_forensics_investigation
name: Disk Forensics Investigation
description: Analyze forensic disk images to reconstruct user activity, malware presence, and event timelines.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, disk, investigation]
version: 1.0.0
---

## Purpose

Disk forensics answers what happened on a system: which files were created, modified, or deleted; what executed and when; and what the user (or attacker) did. Working from a forensically acquired image (never the original), this playbook covers the analysis workflow: filesystem examination, artifact parsing, timeline construction, and malware triage. It pairs with the acquisition playbook — this one starts when the verified image is in hand.

## When to use

- Analyzing an image acquired from a suspected compromised workstation or server.
- Insider-threat investigations requiring user-activity reconstruction.
- Malware triage: determining what a sample did to the filesystem.
- Data-theft investigations: what was accessed, copied, or deleted.
- Any case where a defensible, documented analysis of disk contents is required.

## Prerequisites

- A verified forensic image (hash matches acquisition record) and a working copy — the original image stays pristine.
- Analysis platform: Autopsy, or a Linux workstation with Sleuth Kit, plus artifact parsers for the target OS.
- Known-good baselines where available: gold images, software inventory, or NSRL hash sets for filtering known files.
- Case documentation: objectives, scope, and the questions the analysis must answer.
- Legal authorization for the data on the disk, which may include personal or privileged material.

## Procedure

1. **Verify and mount read-only.** Re-hash the working copy against the acquisition record, then mount or load it read-only in your analysis tool. Record tool versions. Never write to the evidence image.
2. **Survey the filesystem.** Establish the OS, partition layout, and filesystem types. List top-level directories, check for additional partitions or encrypted volumes (note them for follow-up — do not attempt to break encryption without legal authority), and review installed software against the expected baseline.
3. **Filter the known.** Hash files and filter against known-good sets (NSRL) to reduce the corpus to unknown and interesting files. This turns millions of files into a reviewable set; document the filter sets used.
4. **Build a super-timeline.** Generate a filesystem timeline (fls/mactime or Autopsy's timeline) combining file MAC times with parsed artifacts: event logs, registry hives, browser history, USB device history, prefetch/shimcache, and shell histories. Sort by time and anchor on the incident window.
5. **Examine persistence and execution artifacts.** Check: autorun locations, scheduled tasks, services, WMI subscriptions, startup folders, browser extensions, and recently executed programs (prefetch, shimcache, BAM/DAM). Attackers and malware both need persistence — this is where they live.
6. **Reconstruct user and attacker activity.** Correlate: logon events, file access to sensitive data, USB insertions, cloud-sync activity, and deleted-file recovery (carve unallocated space for key file types). Distinguish the legitimate user's patterns from anomalous activity by time, location, and behavior.
7. **Triage suspicious binaries.** Extract unknown executables, hash them, check against threat intel, and submit to sandboxes as needed. Determine first-seen timestamps, execution evidence, and what the binary touched — then decide whether deeper malware analysis is warranted.
8. **Answer the case questions in writing.** For each investigative question (was data exfiltrated? when was malware installed? who did what?), state the conclusion, the evidence supporting it, and its strength. Separate confirmed findings from reasonable inferences, and note what the disk cannot answer.

## Expected outputs

- Verified working copy with documented tool versions and hash checks.
- Filtered file corpus (known-good removed) with suspicious files extracted.
- A super-timeline covering the incident window, combining filesystem and artifact sources.
- Persistence, execution, and user-activity findings with evidentiary citations.
- A written report answering the case questions, graded by confidence.

## Pitfalls

- Analyzing the original image instead of a working copy — one write destroys defensibility.
- Timestamp tunnel vision: MAC times can be manipulated (timestomping); corroborate with logs and artifacts.
- Ignoring unallocated space and volume shadow copies — deleted and previous-version data often holds the key findings.
- Over-relying on antivirus hits on the image; AV misses plenty, and its detections need the same timeline corroboration as everything else.
- Writing conclusions the evidence does not support — "consistent with" and "proves" are different claims.

## References

- NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident Response"
- Sleuth Kit and Autopsy documentation (timeline analysis, file recovery)
- SANS FOR500-style Windows artifact references (registry, prefetch, event logs)
- "File System Forensic Analysis" (Carrier) for filesystem fundamentals
- SWGDE best practices for forensic analysis and reporting
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
