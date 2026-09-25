---
skill_id: cyber_detecting_ransomware_encryption_behavior
name: Detecting Ransomware Encryption Behavior
description: Detect ransomware by its encryption behavior: file I/O patterns, entropy, and canary files.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, detection, endpoint]
version: 1.0.0
---
## Purpose

Ransomware's encryption phase is loud at the filesystem level even when the binary is novel: mass file renames, extension changes, entropy spikes, and ransom notes. This playbook builds behavior-based ransomware detection that catches encryption in progress — focused on stopping the blast radius when prevention fails.

## When to use

- You need last-line-of-defense ransomware detection on endpoints/servers.
- EDR file-monitoring is available but no ransomware-specific rules exist.
- A ransomware incident revealed encryption ran undetected for hours.
- Protecting file servers and backup infrastructure specifically.

## Prerequisites

- Endpoint/file telemetry: Sysmon Event ID 11 (file creation), EDR file-modification events, or FIM (file integrity monitoring) on critical shares.
- Ability to compute or approximate file entropy / detect mass rename patterns.
- Canary files deployed on high-value shares (honeypot documents).
- Network-share audit logging for file-server coverage.

## Procedure

1. Detect mass file modification patterns. Alert on: high rates of file renames/extensions changes per host in short windows, writes with high-entropy content to user document directories, original files being deleted after encrypted copies appear, and ransom-note filenames (known patterns) appearing on disk. Tune thresholds per host role — file servers legitimately modify many files; user workstations don't.
2. Deploy and monitor canary files. Place attractive canary documents (named like real files) across shares and endpoints; any modification to a canary is a high-confidence ransomware signal. Alert on canary access/modification/deletion immediately — canaries often fire before mass encryption completes, buying containment time.
3. Watch the encryption precursors. Ransomware typically: deletes shadow copies (vssadmin/bcdedit), disables recovery, kills databases/security products, then encrypts. Alert on shadow-copy deletion and recovery-disabling commands as pre-encryption signals — these buy the most valuable response time because they precede data loss.
4. Correlate with the delivery chain. Encryption doesn't start the incident: hunt backward for initial access (phishing, exposed RDP/VPN), lateral movement, and data exfiltration (double extortion). A ransomware alert should automatically trigger exfiltration hunting — assume data theft until ruled out.
5. Respond with speed-optimized containment. On confirmed encryption behavior: isolate the host(s) immediately (automated isolation if available), identify patient zero and the encryption start time, determine which shares/data are affected, preserve the ransomware binary and ransom note for analysis, and engage the incident response plan — including the backup-restoration and ransom-decision governance (never pay without legal/executive process).
6. Harden the recovery position: immutable/offline backups tested by restore drills, network segmentation limiting share access, application allowlisting on servers, and phishing-resistant MFA on remote access. Detection limits damage; recoverability determines survival.

## Expected outputs

- Behavioral ransomware rules: mass-rename/entropy alerts, canary monitoring, pre-encryption precursor alerts.
- Canary deployment map with monitoring and alert routing.
- Speed-containment runbook: isolation, scoping, evidence preservation, IR engagement.
- Backup immutability and restore-test records.

## Pitfalls

- Threshold-only rules without canaries and precursors detect encryption late — layer all three.
- File servers and backup systems have legitimate bulk-modification patterns — tune per role.
- Ransom-note filename matching alone misses novel variants; pair with behavior rules.
- Isolating the encrypting host without finding patient zero and lateral spread leaves active ransomware elsewhere.
- Paying ransom without exhausting recovery options and legal review is a governance failure — decide the policy before an incident.

## References

- MITRE ATT&CK T1486 (Data Encrypted for Impact) — https://attack.mitre.org/techniques/T1486/; CISA StopRansomware guidance (cisa.gov/stopransomware); NIST SP 800-61 Rev. 2 (incident handling)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
