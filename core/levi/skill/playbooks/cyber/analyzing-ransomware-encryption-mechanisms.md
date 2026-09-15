# Analyzing Ransomware Encryption Mechanisms

## Purpose

Determine how a ransomware sample encrypts files — algorithm, key management, file targeting, and weaknesses — from isolated lab analysis, to assess decryptor feasibility and scope recovery options. Analysis only; no live-system decryption attempts without tested backups.

## When to use

- A ransomware incident is active and leadership needs to know whether decryption without payment is plausible.
- Triage of a new sample or variant: identifying the family by its crypto implementation.
- Supporting law-enforcement/victim guidance with a technical assessment of the encryption.

## Prerequisites

- Written authorization for malware handling; strictly isolated lab (no network route, snapshots ready).
- The sample hashed; detonate only on sacrificial VMs with canary files of known content.
- Crypto knowledge baseline: symmetric vs. asymmetric, common libraries (Windows CNG, OpenSSL, mbedTLS).
- Never pay or negotiate from the lab — this playbook is technical analysis, not incident negotiation.

## Procedure

1. Hash the sample and identify the family via existing intel — known families with known flaws save weeks of work.
2. Prepare canary files: documents, images, and databases with known plaintext content and varied extensions on the sacrificial VM. Snapshot first.
3. Detonate and observe targeting: which directories are skipped (Windows, Program Files), which extensions are hit, and whether network shares/mapped drives are enumerated.
4. Capture the ransom note and any dropped key files; record filenames, locations, and contents — notes often name the algorithm (verify, don't trust).
5. Identify the crypto API statically: import table entries (`BCryptEncrypt`, `CryptEncrypt`, `EVP_`, `mbedtls_`) reveal the library; constants and S-boxes in the binary hint at the algorithm (AES, ChaCha20, RSA).
6. Dynamically trace key handling in the lab debugger: where is the symmetric key generated (CSPRNG?), is it unique per file or per victim, and how is it protected (RSA-encrypted blob appended to files? exfiltrated?).
7. Examine encrypted canary files: compare plaintext vs. ciphertext to find the exact transformation — appended extensions, header/footer markers, encrypted-key blobs, and whether file headers or full contents are encrypted (partial encryption is faster and sometimes flawed).
8. Test for implementation flaws: hardcoded keys/IVs, reused nonces, ECB mode, keys left in memory or in dropped files, and unencrypted backups (shadow copies deleted? check).
9. Check for wiper behavior: some "ransomware" destroys keys or overwrites without recoverable encryption — distinguish before promising recovery.
10. Assess decryptor feasibility: per-file unique keys protected by RSA-2048+ with no flaw = no decryption; hardcoded key or weak RNG = build and test a decryptor on copies of encrypted canaries only.
11. Check for interrupted-encryption states: partially encrypted files and ransom notes in some directories but not others mean the process was killed mid-run — these hosts may hold recoverable originals from interrupted writes.
12. Test shadow-copy and backup-deletion claims empirically in the lab-cloned environment (`vssadmin list shadows`, backup repository checks) rather than trusting the ransom note.
13. Record the exact ransom-note filenames and appended extensions — these are high-value fleet-hunt pivots.
14. Analyze the ransom note for OPSEC mistakes: contact emails, onion addresses, and wallet addresses are intelligence — record them without engaging.
15. Check for double-encryption markers: layered extensions and multiple ransom notes indicate two families ran — compounding recovery difficulty.
16. Test whether newly created files still get encrypted: a live encryptor process changes the priority from "recover" to "isolate first."
17. Check the binary's PDB path for attribution: leftover debug paths sometimes name the builder's environment.
18. Look for configuration files dropped alongside the binary: affiliate IDs and targeting options live there.
19. Test file-type targeting empirically: place canaries of each claimed type and confirm which actually get encrypted.
20. Compare data-theft claims in the note against actual exfiltration evidence — notes exaggerate.
21. Document the full mechanism: algorithm(s), mode, key lifecycle, file markers, targeting rules, and the flaw analysis with evidence.
22. Hand the assessment to the recovery team with a clear verdict: decryptable (with method), partially recoverable (which file types), or not decryptable — plus the IOCs for containment.

## Key tools & commands

- Lab debugger (x64dbg, WinDbg) — tracing key generation and crypto calls.
- `strings`, PE import analysis — crypto API identification.
- Wireshark/dumpcap in the lab — key exfiltration traffic (if any).
- Python (`cryptography` lib) — testing hypotheses against canary plaintext/ciphertext pairs.
- YARA — family identification by code patterns.
- Volatility `windows.memmap --dump` — recovering keys from memory dumps.
- `photorec` — recovering deleted originals when encryption overwrote files in place.
- `vssadmin list shadows` (lab clone) — empirically verifying backup-deletion claims.
- Snapshot/revert — sacrificial VM lifecycle.

## Expected outputs

- Family identification (or "novel variant" determination).
- Encryption mechanism report: algorithm, mode, key lifecycle, file markers.
- Flaw analysis with evidence for/against decryptability.
- Tested decryptor (if feasible) validated on canary copies — never run untested tools on production data.
- Interrupted-encryption assessment (recoverable originals from killed runs).
- Ransom-note filenames and appended extensions as fleet-hunt pivots.
- Clear recovery verdict for leadership and the recovery team.

## Pitfalls

- Trusting the ransom note's crypto claims — verify empirically.
- Attempting decryption on original evidence — always work on copies.
- Missing wiper behavior and promising recovery that is impossible.
- Analyzing on a networked host — modern ransomware spreads to shares fast.
- Confusing "partial encryption" speed optimizations with flaws — test before claiming.
- Fake decryptors distributed as malware — only use vetted sources such as No More Ransom.
- Paying does not guarantee working keys — factor that into the verdict honestly.
- Testing decryptors on originals instead of copies — a failed run can destroy the only copy.
- Ransom notes threatening DDoS or harassment — note it, don't engage.
- Assuming one key per victim — some families use per-file keys with different protection.
- Re-detonating on the same VM and overwriting canary evidence — snapshot discipline.
- Forgetting to check for Linux/ESXi variants of the same family in mixed estates.
- Declaring "not decryptable" without checking No More Ransom first.
- Running the sample with internet access "just to see" — key exfil completes in seconds.
- Forgetting to snapshot before detonation — no clean re-runs.
- Not testing whether the decryptor handles partial encryption.
- Missing the Linux/ESXi variant — check all platforms in the estate.
- Forgetting to image the patient-zero host before remediation.
- Reusing canary filenames across runs — collisions confuse the analysis.
- Confusing wiper behavior with failed encryption — check for key exfiltration first.
- Partial or intermittent encryption defeating full-file carving assumptions.
- Per-file keys wrapped by a master key — recover the wrapping, not each file key.
- Memory holds keys only during the encryption window — capture RAM mid-incident.
- Assuming no decryption is possible — check NoMoreRansom for the exact variant first.
- Key material lingers in crash dumps and hibernation files — collect them before reboot.

See also: analyzing-ransomware-network-indicators.md

## References

- MITRE ATT&CK T1486 (Data Encrypted for Impact), T1029 (Scheduled Transfer), T1490 (Inhibit System Recovery)
- CISA #StopRansomware guidance: https://www.cisa.gov/stopransomware
- No More Ransom — vetted decryptors: https://www.nomoreransom.org
- FBI FLASH alerts on ransomware variants (public)
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
