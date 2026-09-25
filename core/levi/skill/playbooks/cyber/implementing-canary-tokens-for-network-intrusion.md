---
skill_id: cyber_implementing_canary_tokens_for_network_intrusion
name: Canary Tokens for Network Intrusion Detection
description: Deploy canary tokens across the network to detect intruders with near-zero false positives.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, detection]
version: 1.0.0
---
## Purpose
Canary tokens are tripwires: credentials, files, URLs, or DNS names that no legitimate user or
system should ever touch. Any interaction is high-fidelity evidence of an intruder (or a curious
insider). This playbook deploys canary tokens across network infrastructure — the cheap, fast
deception layer that catches lateral movement other controls miss.

## When to use
- Adding high-fidelity intrusion detection with minimal cost and maintenance.
- Detecting lateral movement and internal reconnaissance that evades signature controls.
- After incidents where attackers moved undetected through the network for weeks.
- Protecting high-value network segments, jump hosts, and infrastructure devices.
- As the always-on complement to honeypots and EDR.

## Prerequisites
- A token platform (Thinkst CanaryTokens.org, commercial Canary, or self-built) and a notification
  channel (email, webhook to SIEM/SOAR).
- Inventory of placement locations: file shares, internal wikis, network device configs, jump hosts,
  code repos, and cloud consoles.
- Defined response runbook: what the SOC does when a token fires (it's likely a real intrusion —
  treat accordingly).
- Change control awareness: tokens must survive routine maintenance and not be "cleaned up" as
  clutter.
- Legal/HR alignment: tokens may implicate insiders — coordinate with counsel on monitoring notices.

## Procedure
1. **Choose token types for network contexts.** Deploy: fake AWS/cloud credentials in config files
   and wikis, database connection strings in documentation, VPN/RDP credentials in
   password-manager-adjacent notes, internal URLs and hostnames that resolve to monitored
   responders, and DNS canary names in zone files. Each token type catches a different attacker
   behavior.
2. **Place tokens where attackers look.** Prioritize: jump hosts and admin workstations (fake
   credentials in shell history-adjacent files), internal documentation/wikis (connection strings),
   network device backups (SNMP communities, enable secrets — fake), file shares (enticing filenames
   like "vpn-backup-keys.txt"), and code repositories (fake API keys in old commits or config
   examples).
3. **Make tokens believable but useless.** Tokens must look real enough to try (plausible formats,
   realistic hostnames) but be instantly identifiable as fake in your inventory and incapable of
   granting real access (credentials for non-existent accounts, or accounts that alert-and-deny).
   Never use real credentials as tokens.
4. **Wire alerts to the SOC with context.** Each token alert should include: token ID, type,
   placement location, source IP/user, and timestamp — pushed to the SIEM and paged per severity. A
   token firing is a high-priority event: assume intrusion until proven otherwise.
5. **Write the token-response runbook.** On fire: isolate the source host, capture memory/disk if
   warranted, determine how the token was discovered (which tells you where the attacker has been),
   hunt for related activity, and rotate any adjacent real credentials. Document the decision tree —
   analysts shouldn't improvise on a likely-intrusion alert.
6. **Protect tokens from accidental triggering.** Brief IT staff on token locations (without
   revealing exact tokens to everyone), exclude token paths from vulnerability scanners and
   inventory tools where possible, and use tokens that scanners won't touch (e.g., credentials
   requiring interactive use). Track accidental triggers to refine placement.
7. **Rotate and refresh periodically.** Rotate token values every 6-12 months and after any incident
   where tokens may have been discovered. Refresh placements when infrastructure changes (new jump
   hosts, migrated wikis) so coverage follows the environment.
8. **Inventory every token.** Maintain a register: token ID, type, value identifier (not the secret
   itself in plaintext — store retrieval method), placement, owner, deployment date, and rotation
   due. Tokens you can't inventory become mystery alerts.
9. **Measure effectiveness.** Track: time from deployment to first accidental trigger (tune
   placement), true-positive rate (should be near 100% after tuning), and coverage (tokens per
   critical segment). Report token fires as intrusion attempts in security metrics.
10. **Expand thoughtfully.** After network tokens prove value, extend to: cloud consoles (fake
    access keys), SaaS (fake OAuth tokens), and physical spaces (QR codes to canary URLs). Each new
    context follows the same place → alert → runbook → inventory cycle.

## Expected outputs
- Deployed canary tokens across prioritized network locations with a complete inventory register.
- SIEM-integrated alerting with token context and paging for fires.
- A token-response runbook treating fires as likely intrusions.
- Rotation schedule and accidental-trigger tuning records.
- Effectiveness metrics: coverage, true-positive rate, fire-as-intrusion-attempt reporting.

## Pitfalls
- Tokens with real access: a "canary" credential that actually logs in is a backdoor, not a
  tripwire. Tokens must be inert or alert-and-deny.
- Alerting to an unmonitored mailbox: token value is speed — fires must reach the SOC immediately
  with context.
- Placement where scanners trip them: vulnerability scanners touching token URLs create noise that
  trains analysts to ignore fires. Coordinate exclusions.
- No inventory: mystery tokens firing with no placement record waste investigation time and erode
  trust in the program.
- Revealing tokens too broadly: everyone knowing exact token locations defeats insider-detection
  value. Need-to-know placement details.

## References
- Thinkst Canary / CanaryTokens documentation (token types, alerting)
- NIST SP 800-53 SC-36 (honeypots/honeyclients) and SI-4 (monitoring)
- MITRE ATT&CK T1083 (File and Directory Discovery), T1552 (Unsecured Credentials) — behaviors
  tokens detect
- SANS / DFIR community guidance on deception for intrusion detection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
