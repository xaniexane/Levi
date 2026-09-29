---
skill_id: cyber_b3_lolbins_abuse_identity_provider_sso_air_gapped_network_developing
name: Living-off-the-Land Binaries Abuse Defense for SSO Identity Providers in Air-Gapped Networks (Developing Maturity)
description: "Living-off-the-Land Binaries Abuse defense playbook for SSO Identity Providers in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, defense-evasion, identity, sso, authentication, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Living-off-the-Land Binaries Abuse Defense for SSO Identity Providers in Air-Gapped Networks (Developing Maturity)

## Purpose

Attackers use built-in tools (certutil, bitsadmin, mshta, rundll32, wmic) for download, execution, and exfiltration — no malware to signature. Defense is behavioral: baseline normal LOLBin usage and alert on anomalous parents, arguments, and network activity. Applies to SSO Identity Providers in Air-Gapped Networks at Developing maturity.

## When to use

- LOLBins spawned by Office apps, browsers, or scripts with network arguments (certutil -urlcache, bitsadmin /transfer) — parents that never legitimately drive them.
- Encoded or obfuscated arguments, downloads to temp/appdata, or LOLBin-initiated outbound connections.
- Rare LOLBins (mshta, regsvr32, cmstp) executing at all in environments that never use them legitimately.
- Lens: Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Authentication logs per application (success/failure, MFA method, device, location) and Application assignment and provisioning logs; new SSO integrations; run `# conceptually (IdP APIs differ):` then `idp-cli logs auth --user <upn> --last 7d --format table | head -25`.
3. **Analyze.** Reconstruct the full command line — the arguments reveal intent (download URL, payload path, execution method). Then: Check whether the LOLBin fetched a second stage; if so, the investigation continues at the downloaded payload.
4. **Contain and harden.** Application control policies blocking LOLBin network/download primitives where unused; constrained language mode for PowerShell. Asset layer: Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking a LOLBin outright and breaking admin workflows — constrain by parent and argument, not by existence.
- Missing LOLBin use on Linux/macOS (curl, wget, python) while hunting Windows only.

## References

- MITRE ATT&CK: T1218 (Defense Evasion: System Binary Proxy Execution)
- Vendor logging and hardening baselines for SSO Identity Providers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
