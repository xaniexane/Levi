---
skill_id: cyber_b3_oauth_consent_phishing_ids_ips_sensor_on_prem_datacenter_optimized
name: OAuth Consent Phishing Defense for IDS/IPS Sensors in On-Premises Datacenter (Optimized Maturity)
description: "OAuth Consent Phishing defense playbook for IDS/IPS Sensors in On-Premises Datacenter at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, network, ids, on-prem, datacenter, maturity-optimized]
version: 1.0.0
---
# OAuth Consent Phishing Defense for IDS/IPS Sensors in On-Premises Datacenter (Optimized Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to IDS/IPS Sensors in On-Premises Datacenter at Optimized maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: alert logs with full packet captures for high-severity events + sensor health metrics. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Signature alert logs with triggering packet payloads; anomaly-detection baselines and deviations and PCAP ring buffers for incident windows; sensor placement/coverage maps; run `# Suricata/Snort style triage:` then `jq -c 'select(.alert.severity<=2) | {ts:.timestamp, sig:.alert.signature, src:.src_ip, dst:.dest_ip}' /var/log/suricata/eve.json | tail -20`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: Sensors on SPAN/TAP at every trust boundary; signature sets auto-updated; TLS inspection feeding sensors. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for IDS/IPS Sensors; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
