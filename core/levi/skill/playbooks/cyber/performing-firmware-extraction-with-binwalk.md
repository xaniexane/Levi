---
skill_id: cyber_performing_firmware_extraction_with_binwalk
name: Firmware Extraction with Binwalk
description: Extract and inspect embedded firmware images for analysis.
risk: low
permissions: []
requires_confirmation: false
tags: [firmware, forensics, reverse-engineering]
version: 1.0.0
---
# Firmware Extraction with Binwalk

## Purpose

Routers, cameras, and industrial controllers run opaque firmware that
attackers love to backdoor. Binwalk scans a firmware image for embedded
file systems, kernels, and compressed blobs and extracts them for
inspection. This playbook standardizes extraction so analysis starts from
a complete, reproducible file set.

## When to use

- Analyzing a device firmware image for backdoors or vulnerabilities.
- Incident response on a compromised embedded/IoT device.
- Supply-chain verification of vendor-supplied firmware.
- Extracting a file system to hunt for hardcoded credentials or keys.

## Prerequisites

- The firmware image obtained legitimately: vendor download, update
  package, or a forensic dump from a device you own or are authorized
  to examine.
- Binwalk installed with its extraction dependencies (sasquatch,
  jefferson for JFFS2, ubi_reader for UBIFS) on an isolated analysis
  VM.
- Enough disk space: extracted file systems multiply the image size.

## Procedure

1. Record the image hash and source; run `binwalk -E` (entropy) first —
   high-entropy regions suggest encryption or compression and shape
   expectations.
2. Run a signature scan: `binwalk firmware.bin` to list embedded
   offsets: SquashFS, JFFS2, UBIFS, kernels, certificates, and
   compressed archives.
3. Extract recursively: `binwalk -Me firmware.bin` to carve and
   re-scan nested images; review the extraction log for failures that
   need manual follow-up.
4. Handle extraction failures explicitly: failed SquashFS mounts often
   mean non-standard compression — try `sasquatch` variants or extract
   the region manually with `dd` using the reported offset.
5. Inventory the extracted root file system: `/etc/passwd` and
   `/etc/shadow` for accounts and password hashes, init scripts and
   rc.d entries for persistence, and the web root for admin interfaces.
6. Hunt for secrets at scale: grep the extracted tree for `password`,
   `passwd`, `BEGIN PRIVATE KEY`, `aws_secret`, and hardcoded IPs or
   domains; record every hit with its file path.
7. Check binaries for hardening gaps: run `checksec` on key services
   (telnetd, httpd, sshd) for missing PIE, NX, stack canaries, and RELRO.
8. Preserve the extraction: tar the extracted tree with the original
   image and hashes so the analysis is reproducible.

## Expected outputs

- Extracted file-system tree(s) with a complete offset/signature map.
- A secrets inventory: hardcoded credentials, keys, and endpoints found.
- Binary hardening results for exposed services.
- A reproducible extraction package (image + tree + hashes + log).

## Pitfalls

- Treating extraction failures as "nothing there": failed mounts are
  where custom or encrypted partitions hide.
- Analyzing firmware you have no right to reverse: confirm license
  terms and authorization, especially for third-party devices.
- Missing nested images: always use recursive extraction.
- Assuming the extracted file system is the whole story: bootloaders
  and NVRAM defaults deserve their own pass.

## References

- Binwalk documentation (github.com/ReFirmLabs/binwalk)
- NIST SP 800-213, IoT Device Cybersecurity Guidance for the Federal Government
- OWASP Internet of Things testing guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
