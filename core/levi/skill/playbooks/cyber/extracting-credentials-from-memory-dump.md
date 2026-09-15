---
skill_id: cyber_extracting_credentials_from_memory_dump
name: Recovering Credentials from Memory Dumps
description: Forensically recover credential material (hashes, tickets, keys) from an acquired memory image using Volatility-class tools, with privacy safeguards.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, memory, credentials]
version: 1.0.0
---
## Purpose

Volatile memory frequently holds credential material — NTLM hashes, Kerberos
tickets, DPAPI master keys, browser session tokens, and occasionally
plaintext passwords — that is essential for scoping an intrusion (what the
attacker could have stolen) and for recovery (what must be rotated). This
playbook covers recovering that material from an already-acquired memory
image using memory-forensics frameworks, with strict handling rules for the
sensitive output.

## When to use

- Post-compromise scoping: determining which credentials were present in
  memory on a breached host and therefore must be considered compromised.
- Credential-theft investigations (suspected Mimikatz-style tooling):
  confirming what was accessible.
- Forensic recovery of keys needed to decrypt other artifacts (DPAPI
  master keys for browser/login-data decryption).
- Building the rotation list after an incident: memory contents define
  the minimum rotation scope.

## Prerequisites

- A forensically acquired memory image (this playbook starts from the
  image file, not from live acquisition) with documented chain of custody.
- Legal/HR authorization: memory contains the user's private data —
  confirm scope before extracting credentials.
- Memory-forensics tooling (Volatility 3 with Windows symbol support,
  or equivalent) and knowledge of the image's OS profile.
- An encrypted, access-controlled location for outputs — recovered
  credentials are handled like live secrets.

## Procedure

1. **Verify the image.** Confirm the image hash matches acquisition
   records, identify the OS profile/version, and record the acquisition
   timestamp — credential material is time-sensitive (tickets expire,
   sessions rotate).
2. **Enumerate processes and sessions.** List processes and logged-on
   sessions to map which users and services were active at acquisition;
   this bounds whose credentials may be present.
3. **Recover Windows credential material.** Run the framework's
   credential-recovery plugins (hashdump/lsadump equivalents, cached
   domain credentials) against the image. Record hashes — do not crack
   them unless the investigation explicitly requires it and is
   authorized; possession of hashes already proves exposure.
4. **Extract Kerberos tickets and DPAPI keys.** Recover service tickets
   and TGTs (they show what the account could access) and DPAPI master
   keys (needed to decrypt other user artifacts). Note ticket lifetimes
   to judge whether stolen tickets are still usable.
5. **Check high-value processes.** Examine LSASS-adjacent memory,
   browser processes (session cookies/tokens), and any credential-manager
   processes for additional material. Document findings per process.
6. **Assess attacker-accessible material.** Determine which of the
   recovered credentials an attacker with the observed access level could
   plausibly have obtained — this is the scoping deliverable that drives
   the rotation plan.
7. **Build the rotation list.** Every credential present in memory on a
   compromised host is treated as compromised: user passwords, service
   accounts, Kerberos tickets (force password resets to invalidate),
   API keys, and session tokens. Prioritize domain admin and service
   accounts.
8. **Protect and purge the output.** Store recovered material encrypted
   with strict access control, share only on a need-to-know basis, and
   securely delete working copies once the rotation is confirmed —
   your forensic output must not become a second credential leak.

## Expected outputs

- An inventory of credential material recovered from the image, by user
  and type (hash, ticket, key, token).
- A compromise assessment: which credentials the attacker could have
  obtained.
- A prioritized credential-rotation plan with completion tracking.
- Secure handling records and deletion confirmations for working copies.

## Pitfalls

- Memory images are full of PII — scope the extraction to the
  investigation and avoid browsing unrelated user data.
- Cracking hashes escalates legal and policy risk; default to
  treating hashes as compromised rather than cracking them.
- Ticket and session material decays fast — acquire memory early in an
  incident; a days-old image may understate exposure.
- Symbol/profile mismatches produce garbage output — verify the OS
  profile before trusting plugin results.
- Forgetting to purge working copies turns your forensic workstation
  into a credential store — build deletion into the workflow.

## References

- Volatility 3 documentation (Windows credential-recovery plugins)
- MITRE ATT&CK: T1003 (OS Credential Dumping)
- NIST SP 800-86: Guide to Integrating Forensic Techniques into
  Incident Response
- Microsoft Learn: "Credential Guard" and LSASS protection guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
