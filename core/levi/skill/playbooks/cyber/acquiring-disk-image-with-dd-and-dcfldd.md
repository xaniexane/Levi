---
skill_id: cyber_acquiring_disk_image_with_dd_and_dcfldd
name: Acquiring Disk Images with dd and dcfldd
description: Forensically sound disk imaging with dd/dcfldd: write-blocking, hashing, and chain of custody.
risk: moderate
permissions: [evidence.acquire]
requires_confirmation: true
tags: [forensics]
version: 1.0.0
---
# Acquiring Disk Images with dd and dcfldd

## Purpose

Produce a forensically sound, bit-for-bit image of a storage device using
`dd` or `dcfldd`, with hashing and documentation sufficient for the image to
be defensible as evidence in incident response, internal investigation, or
legal proceedings.

## When to use

- First response to a compromised workstation or server where disk
  forensics will follow.
- Creating a working copy so analysis never touches the original media.
- Imaging failing drives where a single careful pass matters (pair with
  write-blocking and, for bad sectors, `ddrescue` instead).
- Any matter where chain of custody and hash verification will be
  scrutinized — assume all of them.
- Preserving a system state before remediation actions (reimaging, password
  resets) destroy evidence.

## Prerequisites

- Written authorization from the asset/data owner to image the device and
  handle its contents (which may include personal or regulated data).
- Chain-of-custody form started: device identifiers (make, model, serial),
  source hash, destination, collector, timestamps — fill it as you go, not
  after.
- A hardware or software write blocker on the source device whenever the
  original media (not a live logical volume) is being read.
- Destination storage with capacity ≥ source device, formatted with a
  filesystem supporting large files (ext4, NTFS, exFAT); verify with `df -h`
  before starting.
- Boot the examiner workstation from a trusted forensic environment; never
  image from the suspect OS itself if avoidable.
- Enough time: plan for the device's actual read speed, not the interface's
  theoretical maximum.

## Procedure

1. **Identify the source device unambiguously.** List block devices and confirm serials before touching anything:
   ```bash
   lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN
   sudo fdisk -l
   ```
   Triple-check `/dev/sdX` — writing to the wrong device destroys evidence. When in doubt, physically disconnect other drives. Record the exact device node and serial in your notes.
2. **Attach through a write blocker** (hardware preferred). If software-only, remount read-only and confirm with `blockdev --getro /dev/sdX` returning `1`. Document which method you used — "hardware write blocker" reads better in court than "I was careful."
3. **Hash the source before imaging** (proves the acquisition captured the device as found):
   ```bash
   sudo dcfldd if=/dev/sdX hash=sha256 hashlog=source_hash.txt
   ```
   With plain `dd`, hash separately. Note: hashing multi-terabyte sources takes significant time — start early and parallelize preparation work.
4. **Acquire with dcfldd (preferred).** It hashes on the fly, logs progress, and can split output:
   ```bash
   sudo dcfldd if=/dev/sdX of=evidence/case042_disk.img \
     hash=sha256 hashlog=evidence/case042_hash.log \
     bs=64K conv=noerror,sync status=on
   ```
   - `conv=noerror,sync` keeps going past read errors, padding bad sectors with zeros — note errors in your log; they are findings, not noise.
   - For multi-file splits add `split=4G splitformat=aa` (useful for FAT32 destinations or evidence systems with file-size limits).
   - `bs=64K` is a reasonable throughput default; larger blocks speed healthy drives but worsen granularity around bad sectors.
5. **If only plain dd is available**, replicate the essentials manually:
   ```bash
   sudo dd if=/dev/sdX of=evidence/case042_disk.img bs=64K \
     conv=noerror,sync status=progress
   sha256sum evidence/case042_disk.img | tee evidence/image_hash.txt
   ```
   Then compare against the source hash from step 3. `status=progress` gives periodic throughput output — log it as evidence of an uninterrupted run.
6. **Verify the image.** Re-hash the image file and confirm it matches the source hash exactly. Also verify the image size equals the source device size (`blockdev --getsize64` on both, compared in bytes). A hash match with a size mismatch means a truncated copy — investigate before proceeding.
7. **Handle partial or interrupted runs.** If acquisition is interrupted, do not simply re-run over the same output file — that risks a mixed image. Either resume with `seek`/`skip` calculated precisely (document the math) or start fresh. When in doubt, start fresh; storage is cheaper than doubt.
8. **Record everything.** Log the exact command lines, start/end times, tool versions (`dcfldd --version`), hashes, byte counts, throughput, and any read errors into the case notes and chain-of-custody form. Your notes should let a stranger reproduce the acquisition exactly.
9. **Secure the image.** Set restrictive permissions (`chmod 600`), store on encrypted media, log every subsequent access, and keep the original image pristine — work only on copies from this point forward. If the matter may go legal, consider a second independent hash by a second examiner.
10. **Handle failing media.**
    If `dd`/`dcfldd` stalls on bad sectors, stop and switch to `ddrescue`
    with a logfile so passes can resume:
    ```bash
    sudo ddrescue -d -r3 /dev/sdX evidence/rescue.img evidence/rescue.log
    ```
    Do not repeatedly hammer a dying drive with plain dd.
    Document the rescue logfile's bad-sector map as part of the acquisition
    record.

## Key tools & commands

- `dcfldd` — dd with built-in hashing (`hash=sha256`), progress
  (`status=on`), split output, and logging; the default choice for forensic
  acquisition.
- `dd` — universal fallback; pair with `status=progress` and separate
  hashing via `sha256sum`.
- `ddrescue` — for damaged media; resumable, logfile-driven recovery with
  bad-sector mapping.
- `lsblk`, `fdisk -l`, `blockdev` — device identification and size/readonly
  verification.
- `sha256sum` — hash generation and verification (SHA-256 is the current
  defensible default; record MD5 too only if policy requires).

## Expected outputs

- A bit-for-bit image file (or split set) whose SHA-256 matches the source
  device hash, with byte-count verification.
- `hashlog` / hash files for source and image, plus tool-version and timing
  records.
- Completed chain-of-custody entries: who, what, when, which commands,
  which hashes.
- A notes entry documenting any read errors, bad sectors, interruptions,
  or anomalies encountered.

## Pitfalls

- `of=` pointing at the wrong device is the classic catastrophic error —
  verify with `lsblk` immediately before every run, and consider wrapper
  scripts requiring typed confirmation of the target serial.
- Imaging a live, mounted filesystem gives you a "smeared" image (files
  changing mid-copy). Boot forensic media or at minimum remount read-only;
  document which you did.
- `conv=noerror,sync` silently zero-fills unreadable sectors — always review
  how many errors occurred; a heavily errored image may need `ddrescue`
  treatment and the gaps documented as limitations.
- Forgetting to hash the *source* before/while imaging leaves you unable to
  prove the image matches the original state.
- Destination filesystem limits: FAT32's 4GB file cap will silently
  truncate — use `split=` or a proper filesystem, and verify sizes afterward
  regardless.
- NVMe devices and hardware RAID present naming quirks (`/dev/nvme0n1`,
  RAID members vs. logical volume) — image the right layer for your
  investigative question and document the choice.

## References

- dcfldd documentation (hash, split, and logging options)
- GNU coreutils `dd` manual (`conv`, `status=progress` semantics)
- GNU ddrescue manual (logfile-driven recovery workflow)
- NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident
  Response" (acquisition principles)
- SWGDE best practices for digital forensic acquisition (write-blocking,
  hashing)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
