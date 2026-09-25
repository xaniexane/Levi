---
skill_id: cyber_detecting_pass_the_hash_attacks
name: Detecting Pass-the-Hash Attacks
description: Detect Pass-the-Hash lateral movement in Windows authentication logs.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, lateral-movement, detection]
version: 1.0.0
---
## Purpose

Pass-the-Hash (PtH) lets attackers authenticate as a user using only the NTLM hash — no password cracking needed. It is a staple of Windows lateral movement. This playbook gives defenders practical PtH detection: the logon patterns that reveal it, how to separate it from legitimate NTLM use, and the response steps that actually stop it.

## When to use

- You need lateral-movement detection for Windows credential-reuse techniques.
- A SIEM rule on 4624 Type 3 logons needs tuning for PtH specifically.
- Threat hunting after a suspected hash-dumping incident (LSASS access observed).
- Validating that credential-theft mitigations (Credential Guard, tiering) are effective.

## Prerequisites

- Windows Security logs: Event ID 4624 (logon) with Logon Type and Authentication Package fields, 4672 (special privileges), and 4648 where applicable.
- NTLM auditing enabled to distinguish NTLM from Kerberos authentications.
- Inventory of where NTLM is legitimately required (legacy apps) vs. where Kerberos should be used.
- Admin tiering model (or plan): which accounts may log on where.

## Procedure

1. Know the PtH signature. Pass-the-Hash appears as NTLM (not Kerberos) network logons (Type 3) where the authenticating host presents a hash: look for 4624 Type 3 with Authentication Package NTLM, the account logging on to hosts it doesn't normally access, and logons using privileged accounts (Domain Admins, local Administrator) from workstations. The absence of a preceding interactive logon or ticket request on the source is supporting evidence.
2. Filter NTLM by expected vs. unexpected. Baseline legitimate NTLM: legacy applications, some printers/scanners, and specific service flows. Alert on NTLM network logons that deviate: NTLM used where Kerberos is the norm for that service, NTLM logons to servers from user workstations, and NTLM authentications for accounts that normally use Kerberos. The deviation, not NTLM itself, is the signal.
3. Correlate with the credential-theft precursor. PtH requires a stolen hash — hunt backward from the PtH logon for LSASS access, dumping tooling, or DCSync on the source host in the preceding hours/days. A PtH alert with a confirmed dumping precursor is high-confidence compromise; without one, investigate the source host for how the hash was obtained.
4. Detect at scale with aggregation. Query for: single accounts with NTLM Type 3 logons to many distinct hosts in a window (lateral fan-out), hosts receiving NTLM logons from many distinct privileged accounts (collection point), and first-seen (account, source, target) NTLM triples involving privileged accounts.
5. Respond as credential compromise. Reset the passwords of accounts used in PtH (they're burned), hunt for where else those hashes were used, isolate source hosts, and check for persistence the attacker established with the stolen access. Re-imaging without credential resets leaves the attacker holding valid hashes.
6. Eliminate the conditions: enforce Kerberos where possible and restrict NTLM via GPO, deploy Credential Guard/LSA Protection to block hash extraction, implement admin tiering so a workstation hash can't reach tier-0, and remove standing privileged access. PtH dies when hashes can't be stolen and can't travel.

## Expected outputs

- PtH detection rules: NTLM-deviation logons, privileged-account NTLM fan-out, first-seen triples.
- Legitimate-NTLM baseline with per-application documentation.
- Precursor-correlation procedure: dumping → PtH chaining.
- Credential-reset and tiering remediation plan.

## Pitfalls

- NTLM is still legitimate in many environments — alerting on all NTLM is unusable; alert on deviations.
- PtH and legitimate admin NTLM look identical in a single event; context (account, source, target, precursor) decides.
- Attackers can also pass-the-ticket with Kerberos — PtH coverage alone leaves a gap; pair with ticket-anomaly detection.
- Resetting only the observed account misses others harvested from the same host — scope the credential exposure.
- Blocking NTLM without application testing breaks legacy systems — phase restrictions with testing.

## References

- MITRE ATT&CK T1550.002 (Use Alternate Authentication Material: Pass the Hash) — https://attack.mitre.org/techniques/T1550/002/; Microsoft Learn: NTLM auditing and restricting NTLM; NIST SP 800-63B (authenticator compromise and recovery)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
