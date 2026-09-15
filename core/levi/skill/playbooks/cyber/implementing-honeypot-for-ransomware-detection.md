---
skill_id: cyber_implementing_honeypot_for_ransomware_detection
name: Honeypot Deployment for Ransomware Detection
description: Deploy honeypots and canary files to detect ransomware early — before mass encryption completes.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, ransomware]
version: 1.0.0
---
## Purpose
Ransomware announces itself by encrypting files — by the time EDR or users notice, damage is
extensive. Honeypots for ransomware detection flip this: canary files and shares that ransomware
encrypts first (alphabetically-first filenames, tempting network shares), monitored in real time,
trigger alerts within seconds of encryption starting — early enough to isolate hosts before the real
data is gone. This playbook deploys that early-warning layer.

## When to use
- Adding early ransomware detection beyond EDR behavioral signatures.
- After ransomware incidents where dwell or encryption time was long.
- Protecting file servers and high-value endpoints in ransomware-targeted sectors (healthcare,
  education, manufacturing).
- As the deception complement to backups, segmentation, and EDR.
- When tabletop exercises reveal slow ransomware detection as a gap.

## Prerequisites
- File servers and representative endpoints identified for canary placement.
- Real-time file-monitoring capability (EDR FIM, OS audit, or honeypot platform) with alerting
  latency measured in seconds to minutes.
- An automated or rapid isolation capability (EDR isolate, NAC quarantine, firewall rule) — early
  warning without fast containment is just earlier bad news.
- Backup and recovery verified independently (detection doesn't replace recovery).
- SOC runbook for ransomware alerts: this is a page-immediately scenario.

## Procedure
1. **Design the canary layout.** On each protected file server/share: plant canary files with names
   that sort first (e.g., `!_aaa_do_not_touch.docx`, `000_canary.xlsx`) in multiple directories,
   plus canary directories. Ransomware typically enumerates alphabetically or breadth-first —
   canaries get hit in the first seconds. Vary file types (Office docs, PDFs) to match what
   ransomware targets.
2. **Deploy monitoring with real-time alerting.** Monitor canary files for: modification, renaming,
   encryption (entropy change), and deletion — via EDR file-integrity, Windows auditing, or a
   dedicated honeypot tool. Alert latency target: under 60 seconds from first canary touch to SOC
   notification. Test the latency; tune until it's met.
3. **Wire automatic containment.** On canary alert: automatically isolate the host (EDR network
   isolation), disable the user session's SMB access, and snapshot the affected share if possible.
   Automation is the point — human triage takes minutes ransomware uses to encrypt thousands of
   files. Define the auto-containment scope carefully to avoid self-inflicted outages (test
   extensively).
4. **Write the ransomware response runbook.** On alert: confirm (check canary + EDR telemetry for
   ransomware behaviors), isolate affected hosts (auto + manual verification), identify patient zero
   and the entry vector, assess encryption scope, engage the incident commander, and begin recovery
   evaluation (backups vs. scope). Include the ransom-payment decision framework (law-enforcement
   coordination, legal — decided in advance, not during).
5. **Protect the canaries from discovery.** Canary files must look ordinary (realistic sizes, recent
   timestamps, normal-looking content) and be excluded from backups indexing, AV scans that might
   quarantine them, and user cleanup efforts. Brief IT staff on their existence (not exact locations
   for everyone). Attackers who identify canaries avoid them — realism matters.
6. **Cover endpoints as well as servers.** Deploy canary files in user profile directories
   (Documents, Desktop) on high-value endpoints via GPO/login script. Endpoint canaries catch
   ransomware that starts on workstations before reaching shares — the earliest possible signal.
7. **Integrate with EDR and SIEM.** Correlate canary alerts with: EDR ransomware-behavior
   detections, mass file-modification telemetry, shadow-copy deletion (vssadmin/bcdedit — classic
   ransomware prep), and disabled recovery agents. The canary is the tripwire; correlation confirms
   and scopes.
8. **Test with safe simulations.** Periodically (quarterly): simulate canary-file modification in a
   controlled manner and verify the full chain — detection, alert, auto-isolation, SOC response —
   completes within targets. Also tabletop the full ransomware scenario annually with
   backups-restore verification.
9. **Maintain and rotate.** Refresh canary files periodically (timestamps, names) so they don't
   stand out as stale; add canaries to new shares/servers as they're provisioned (automate via
   GPO/script); remove canaries from decommissioned shares. Coverage must follow the environment.
10. **Report as early-warning metrics.** Track: canary coverage (shares/endpoints protected), alert
    latency (touch-to-notify), auto-containment success rate, and exercise results. The program's
    value proposition: minutes saved vs. EDR-only detection — measure it.

## Expected outputs
- Canary files/directories deployed on file servers and high-value endpoints, realistic and
  monitored in real time.
- Sub-60-second alerting wired to automatic host isolation.
- A ransomware response runbook (confirm → contain → scope → recover) with pre-decided
  ransom-payment framework.
- SIEM/EDR correlation (shadow-copy deletion, mass modification) and quarterly simulation tests.
- Coverage and latency metrics reported as early-warning performance.

## Pitfalls
- Alert without containment: knowing about ransomware 10 minutes earlier without auto-isolation just
  documents faster encryption. Automation is mandatory.
- Canaries that look fake: zero-byte files with odd names get ignored by smart ransomware and
  cleaned by tidier users. Realism is the control's effectiveness.
- Monitoring latency in minutes: ransomware encrypts thousands of files per minute. If your alert
  pipeline takes 15 minutes, the canaries are archaeology.
- Forgetting endpoints: server-only canaries miss workstation-originated ransomware until it reaches
  shares. Both layers.
- Detection without recovery: early warning still needs verified, isolated, tested backups. The two
  programs are co-required.

## References
- CISA ransomware guidance (detection, response, recovery)
- NIST SP 800-61 (incident handling — ransomware scenarios)
- MITRE ATT&CK T1486 (Data Encrypted for Impact)
- Vendor/community honeypot tooling documentation (canary-file deployment patterns)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
