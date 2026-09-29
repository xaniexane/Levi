---
skill_id: cyber_b3_phishing_credential_harvest_siem_platform_on_prem_datacenter_managed
name: Phishing Credential Harvest Defense for SIEM Platforms in On-Premises Datacenter (Managed Maturity)
description: "Phishing Credential Harvest defense playbook for SIEM Platforms in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, phishing, soc, siem, monitoring, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Phishing Credential Harvest Defense for SIEM Platforms in On-Premises Datacenter (Managed Maturity)

## Purpose

Users are lured to lookalike login pages (often via adversary-in-the-middle kits that relay MFA) and submit credentials. The defender's job: find who clicked, who submitted, and whether sessions were hijacked even where MFA appeared to hold. Applies to SIEM Platforms in On-Premises Datacenter at Managed maturity.

## When to use

- Email gateway logs show a burst of messages with lookalike domains, newly registered domains, or QR-code lures pointing at a credential-harvest kit URL.
- Proxy/DNS logs show visits to the kit domain followed within minutes by logons from unusual IPs or impossible-travel pairs for the same user.
- AiTM kits leave telltales: logon session created without a matching MFA challenge event, or token replay from datacenter IP ranges.
- Lens: Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Detection rule hit history for the incident's indicators across the full retention window and Ingestion gap reports: which sources stopped logging and when (coverage blind spots); run `# conceptually (SIEM query languages differ):` then `index=* <indicator> earliest=-30d | stats count by sourcetype`.
3. **Analyze.** Pull the kit URL from the email, fetch it in a sandbox, and extract the credential-post endpoint and any session-cookie exfiltration to scope which submissions completed. Then: For each submitter, check for concurrent sessions: revoke all refresh tokens and list OAuth app consents granted in the phish window.
4. **Contain and harden.** Move to phishing-resistant MFA (FIDO2/WebAuthn); TOTP and push MFA fall to AiTM relay. Asset layer: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without revoking sessions leaves the attacker logged in via stolen tokens.
- Blaming the clicker instead of fixing the control gap guarantees a repeat with a better lure.

## References

- MITRE ATT&CK: T1566.002 (Initial Access: Phishing: Spearphishing Link)
- Vendor logging and hardening baselines for SIEM Platforms; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
