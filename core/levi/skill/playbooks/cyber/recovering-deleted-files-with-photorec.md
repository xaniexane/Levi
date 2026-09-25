---
skill_id: cyber_recovering_deleted_files_with_photorec
name: Recovering Deleted Files with PhotoRec
description: Carve deleted files from forensic disk copies with PhotoRec during investigations, preserving evidence integrity.
risk: moderate
permissions: []
requires_confirmation: true
tags: [forensics, recovery, disk]
version: 1.0.0
---
## Purpose
When files are deleted but not yet overwritten, carving tools like PhotoRec can recover them by file signature rather than filesystem metadata. This playbook covers forensically sound recovery: work only on copies, carve to separate media, and document everything for chain of custody. It is used in incident response and data recovery investigations, never as routine file undeletion on live systems.

## When to use
- Incident response requiring recovery of attacker-deleted logs or data.
- Investigating suspected data destruction or anti-forensics activity.
- Recovering accidentally deleted evidence from a forensic copy.
- Validating whether deleted sensitive data is still recoverable from retired media.

## Prerequisites
- Bit-for-bit forensic image of the source media, hash-verified (never work on the original).
- PhotoRec/TestDisk installed on the analysis workstation.
- Separate destination storage with capacity exceeding the expected carved output.
- Authorization for the recovery, and chain-of-custody forms if evidence is involved.

## Procedure
1. Confirm you are working on a verified copy; record source and copy hashes in the case notes.
2. Identify the filesystem and partition layout so PhotoRec scans the correct region.
3. Run PhotoRec against the image, selecting target file types relevant to the investigation to reduce noise.
4. Direct all recovered output to the separate destination volume, never back onto the source image.
5. Sort carved files by type and review; carved files lose names and timestamps, so content review is required.
6. Hash recovered files of interest and correlate them with the investigation timeline.
7. Document the tool version, options, source hashes, and output hashes in the case file.
8. Securely wipe working copies when the case closes, per retention policy.
9. Photograph media labels and connections before imaging to support chain of custody.
10. Run a second carving pass with different file-type selections if the first pass misses expected data.
11. Verify carved file integrity by opening samples; headers alone do not prove usability.

## Expected outputs
- Carved file set organized by type, with hashes and review notes.
- Case documentation: tool version, options, source and output hashes.
- Assessment of what was and was not recoverable, with reasons.
- Chain-of-custody photo log of source media.
- Carving pass log with file-type selections and hit counts per pass.
- Integrity spot-check results for recovered files of interest.

## Pitfalls
- Carved files lose original names, paths, and timestamps; content review cannot be skipped.
- Heavily fragmented or partially overwritten files carve as corrupt; set expectations early.
- Running recovery tools on the live original destroys evidence and further data.
- Large volumes produce enormous output; filter by file type before carving everything.
- File carving cannot recover original filenames; manage stakeholder expectations early.
- SSDs with TRIM make carving largely futile; check the media type before promising results.
- Encrypted volumes must be decrypted first; carving ciphertext is pointless.
- Carving on a failing drive can finish it off; image failing media with ddrescue before any carving pass.

## References
- CGSecurity PhotoRec documentation.
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response.
- SANS FOR508 advanced incident response concepts.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
