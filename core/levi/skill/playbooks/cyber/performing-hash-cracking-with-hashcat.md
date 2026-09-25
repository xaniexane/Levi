---
skill_id: cyber_performing_hash_cracking_with_hashcat
name: Password Hash Auditing with Hashcat
description: Audit password strength by cracking hashes you are authorized to test.
risk: low
permissions: []
requires_confirmation: false
tags: [passwords, auditing, credentials]
version: 1.0.0
---
# Password Hash Auditing with Hashcat

## Purpose

Hash-cracking tools are dual-use: attackers use them to break stolen
hashes, defenders use them to prove a password policy is failing. This
playbook takes the defensive side — auditing hashes you are authorized
to test (your own AD database, a breach-assessment engagement) to measure
real password strength and drive policy change. Never crack hashes you do
not own or have written permission to test.

## When to use

- Password-strength audits during a security assessment (with written
  authorization).
- Demonstrating to leadership that the current policy produces
  crackable passwords.
- Validating that a new passphrase policy actually improved resistance.
- Post-breach analysis of your own leaked hashes to scope user impact.

## Prerequisites

- Written authorization to possess and crack the specific hash set, and
  a defined handling and destruction plan for the hashes and any
  recovered plaintexts.
- Hashes extracted securely (e.g. NTDS.dit via authorized DC backup,
  never exfiltrated over the Internet in cleartext).
- Hashcat on a controlled machine with GPU drivers; wordlists
  (rockyou, breach compilations you may legally use) and rules.

## Procedure

1. Confirm scope in writing: which hash set, who authorized it, and the
   retention and destruction date for hashes and cracked results.
2. Identify the hash type (`hashcat --identify` or known format) and
   select the matching mode; verify a known test vector cracks before
   the real run.
3. Start with cheap attacks: dictionary with common wordlists, then
   rule-based mutations (best64, d3ad0ne-style rules) — most weak
   passwords fall here.
4. Escalate methodically: combinator attacks, targeted masks based on
   the organization's password policy (e.g. `?u?l?l?l?l?d?d?s`), and
   only then broader brute force on remaining hashes.
5. Track metrics, not just plaintexts: percentage cracked per attack
   phase and time-to-crack distribution — this is the evidence for
   policy change.
6. Protect results fiercely: cracked passwords are credentials — store
   encrypted, limit access to the assessment team, and never include
   plaintexts in reports; report statistics and example patterns only.
7. Recommend the fix the data supports: length-based passphrases,
   breached-password screening at creation, and MFA — not just "more
   complexity."
8. Destroy the working set: securely delete hashes, wordlists with
   results, and potfiles on the agreed date and document destruction.

## Expected outputs

- Crack-rate statistics per attack phase (not a plaintext dump).
- A policy assessment: what the data proves about current password
  strength.
- Recommendations: passphrase policy, screening, MFA rollout.
- Documented secure destruction of hashes and results.

## Pitfalls

- Cracking without written authorization: possession of someone else's
   hashes plus a cracker is indistinguishable from attack preparation.
- Emailing or ticketing cracked plaintexts: they are live credentials.
- Concluding "policy is fine" from a short run: weak attacks
   under-measure the risk, so size the effort to the question asked.
- Keeping the potfile indefinitely: it becomes a credential database
   you must protect forever.

## References

- NIST SP 800-63B, Digital Identity Guidelines (memorized secrets)
- Hashcat documentation (hashcat.net/wiki)
- CISA guidance on password and MFA best practices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
