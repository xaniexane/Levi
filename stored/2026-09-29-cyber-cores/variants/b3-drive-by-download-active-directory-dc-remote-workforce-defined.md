---
skill_id: cyber_b3_drive_by_download_active_directory_dc_remote_workforce_defined
name: Drive-By Download Defense for Active Directory Domain Controllers in Remote Workforce (Defined Maturity)
description: "Drive-By Download defense playbook for Active Directory Domain Controllers in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, windows, identity, active-directory, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Drive-By Download Defense for Active Directory Domain Controllers in Remote Workforce (Defined Maturity)

## Purpose

Visiting a compromised or malicious page silently downloads malware via browser or plugin exploits. Patching and browser isolation remove the opportunity; proxy logs reveal the exposure. Applies to Active Directory Domain Controllers in Remote Workforce at Defined maturity.

## When to use

- Browser spawning unexpected child processes or writing executables to temp/downloads without user download action.
- Proxy logs showing visits to compromised sites followed by executable downloads, often via redirect chains.
- Exploit-kit patterns: rapid plugin version probing, obfuscated JavaScript, then payload fetch.
- Lens: Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log Kerberos events (4768 TGT requests, 4769 service tickets, 4771 pre-auth failures) and Directory-service change events (5136/5137) and replication metadata (repadmin /showobjmeta); run `repadmin /showrepl | Select-String -Pattern 'error|fail' -Context 2` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4769} -MaxEvents 200 | Group-Object {$_.Properties[0].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Reconstruct the redirect chain from proxy logs to identify the compromised page or malvertising source. Then: Determine whether the payload executed: browser process tree and EDR execution events after the download timestamp.
4. **Contain and harden.** Automatic browser and OS patching; remove or sandbox legacy plugins (Java, Flash-era); consider browser isolation for high-risk users. Asset layer: Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming the user 'must have clicked something' — drive-bys need no click, so user interviews mislead.
- Cleaning the endpoint without blocking the compromised site that will re-infect the next visitor.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise)
- Vendor logging and hardening baselines for Active Directory Domain Controllers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
