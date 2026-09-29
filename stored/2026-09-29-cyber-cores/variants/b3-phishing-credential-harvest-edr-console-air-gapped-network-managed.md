---
skill_id: cyber_b3_phishing_credential_harvest_edr_console_air_gapped_network_managed
name: Phishing Credential Harvest Defense for EDR Consoles in Air-Gapped Networks (Managed Maturity)
description: "Phishing Credential Harvest defense playbook for EDR Consoles in Air-Gapped Networks at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, phishing, soc, edr, endpoint, air-gap, ot, high-security, maturity-managed]
version: 1.0.0
---
# Phishing Credential Harvest Defense for EDR Consoles in Air-Gapped Networks (Managed Maturity)

## Purpose

Users are lured to lookalike login pages (often via adversary-in-the-middle kits that relay MFA) and submit credentials. The defender's job: find who clicked, who submitted, and whether sessions were hijacked even where MFA appeared to hold. Applies to EDR Consoles in Air-Gapped Networks at Managed maturity.

## When to use

- Email gateway logs show a burst of messages with lookalike domains, newly registered domains, or QR-code lures pointing at a credential-harvest kit URL.
- Proxy/DNS logs show visits to the kit domain followed within minutes by logons from unusual IPs or impossible-travel pairs for the same user.
- AiTM kits leave telltales: logon session created without a matching MFA challenge event, or token replay from datacenter IP ranges.
- Lens: Best telemetry: raw process/network telemetry + detection history + sensor health inventory. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Full process trees with command lines, hashes, and network connections for suspect hosts and Detection and response action history (isolations, kills, quarantines); run `# conceptually (EDR APIs differ):` then `edr-cli hunt process --hostname <host> --since 24h --tree`.
3. **Analyze.** Pull the kit URL from the email, fetch it in a sandbox, and extract the credential-post endpoint and any session-cookie exfiltration to scope which submissions completed. Then: For each submitter, check for concurrent sessions: revoke all refresh tokens and list OAuth app consents granted in the phish window.
4. **Contain and harden.** Move to phishing-resistant MFA (FIDO2/WebAuthn); TOTP and push MFA fall to AiTM relay. Asset layer: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without revoking sessions leaves the attacker logged in via stolen tokens.
- Blaming the clicker instead of fixing the control gap guarantees a repeat with a better lure.

## References

- MITRE ATT&CK: T1566.002 (Initial Access: Phishing: Spearphishing Link)
- Vendor logging and hardening baselines for EDR Consoles; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
