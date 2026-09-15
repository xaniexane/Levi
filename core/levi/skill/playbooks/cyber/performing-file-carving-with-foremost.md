---
skill_id: cyber_performing_file_carving_with_foremost
name: File Carving with Foremost
description: Recover deleted files from disk images using header/footer carving.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, file-recovery, disk]
version: 1.0.0
---
# File Carving with Foremost

## Purpose

When file-system metadata is gone — deleted files, formatted partitions,
damaged structures — carving recovers files by their headers and footers
instead of directory entries. This playbook uses Foremost on a forensic
disk image to recover evidence while preserving the original media.

## When to use

- Recovering deleted documents, images, or archives relevant to an
  investigation.
- Examining unallocated space on a disk image for evidence of wiped
  files.
- Triaging removable media where the file system is corrupted.
- Supporting e-discovery when standard recovery tools come up short.

## Prerequisites

- A forensic disk image (dd/E01), never the original media; work on a
  copy and verify hashes before and after.
- Foremost installed on the analysis workstation and familiarity with
  its configuration file (`/etc/foremost.conf`).
- Sufficient scratch space: carved output can exceed the image size.

## Procedure

1. Verify the image hash matches the acquisition record before opening
   it; document the hash in the case notes.
2. Review `foremost.conf`: enable only the file types relevant to the
   investigation to keep output manageable, and note the header/footer
   signatures for any custom types you add.
3. Run Foremost against the image: `foremost -i image.dd -o output_dir`,
   optionally with `-t jpg,doc,pdf` to carve specific types.
4. Review `audit.txt` in the output directory: it records carved file
   offsets, sizes, and signatures — this is your chain-of-custody
   evidence for where each file came from.
5. Triage the carved files: filter by relevance, deduplicate by hash,
   and examine the most probative types first (documents and images
   over caches and thumbnails, unless the case says otherwise).
6. Corroborate findings: match carved files against known hashes,
   timelines, and any surviving file-system metadata (MFT entries,
   journal) to establish context.
7. Handle fragmented files honestly: carving can produce partial or
   merged files — note which recovered files are complete versus
   reconstructed fragments.

## Expected outputs

- Carved file sets organized by type, with per-file offset/size records
  in audit.txt.
- Hash lists of recovered files for deduplication and correlation.
- A recovery report noting completeness and any fragmented results.
- Verified image hashes before and after analysis.

## Pitfalls

- Carving the original media instead of a verified copy.
- Enabling every file type: you will drown in browser cache fragments.
- Presenting a partially carved file as complete evidence.
- Forgetting that file names and timestamps are lost in carving —
  recovery without context needs corroboration.

## References

- Foremost documentation (foremost.conf and man page)
- NIST SP 800-101 guidance on forensic tool handling
- Carrier, B.: File System Forensic Analysis (for carving theory)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
