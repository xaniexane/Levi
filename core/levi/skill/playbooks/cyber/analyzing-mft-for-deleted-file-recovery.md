# Analyzing the MFT for Deleted File Recovery

## Purpose

Recover evidence of deleted files — names, sizes, timestamps, and data-run locations — from the NTFS Master File Table ($MFT), and carve file content from unallocated clusters when the directory entries are gone.

## When to use

- An attacker or insider deleted logs, payloads, or exfiltrated archives and you need to prove they existed.
- Timeline reconstruction: file creation/modification times survive in MFT records even after deletion.
- You have a forensic disk image (E01/raw); never parse the MFT of a live suspect disk in place if you can avoid it.

## Prerequisites

- Written authorization; chain-of-custody for the disk image with verified hashes.
- A forensic copy of the volume (E01, raw/dd) mounted read-only or parsed offline.
- Tools: `analyzeMFT.py` or `MFTECmd`, `sleuthkit` (`fls`, `icat`), a hex viewer, and optionally `Autopsy`.
- Basic NTFS knowledge: MFT record = 1024 bytes, entries flagged in-use vs. unallocated.

## Procedure

1. Verify the image hash, then locate and extract the $MFT:
   `mmls image.E01` to find the NTFS partition offset, then
   `icat -o <offset> image.E01 0 > mft.bin` (inode 0 is $MFT).
   Alternatively parse in place with `MFTECmd -f image.E01 --vss` style workflows or mount read-only.
2. Parse the MFT into a structured timeline:
   `python analyzeMFT.py -f mft.bin -o mft.csv`
   or `MFTECmd.exe -f mft.bin --csv ./out --csvf mft.csv`
3. Open the CSV and filter for deleted entries: records where the in-use flag is cleared (`IsDirectory`/`InUse` = False) but the filename attribute remains.
4. Sort by timestamps. Focus on the four NTFS timestamps per record ($STANDARD_INFORMATION vs $FILE_NAME) — a mismatch between SI and FN times is a timestomping indicator.
5. Search for filenames of interest: deleted archives, `.log` files in wiped directories, payload names from threat intel:
   `grep -i "mimikatz\|sekurlsa\|\.rar$\|\.7z$" mft.csv`
6. For each deleted record of interest, note its MFT record number, parent directory reference, and data runs (cluster extents).
7. Attempt content recovery with `icat` using the record number:
   `icat -o <offset> image.E01 <mft-record-number> > recovered.bin`
   This works when clusters have not been reallocated; check the output size against the MFT-recorded file size.
8. If `icat` returns nothing (clusters overwritten), fall back to file carving over unallocated space:
   `blkls -o <offset> image.E01 > unallocated.bin` then run `scalpel` or `photorec` against it with headers for your target types.
9. Recover resident files directly: small files live inside the MFT record itself ($DATA resident) — parse them from the record bytes with a hex viewer.
10. Reconstruct the directory path using parent MFT references, walking up until you hit record 5 (root).
11. Build the timeline: merge MFT timestamps with USN Journal (`fsutil usn` parsed offline or `MFTECmd` USN output) and `$LogFile` entries to confirm deletion events.
12. Parse the USN Journal for file operations the MFT no longer shows: extract `$UsnJrnl` with
    `icat -o <offset> image.E01 <usn-record-number> > usnjrnl.bin`
    parse it with a USN parser, and match delete/rename entries against your MFT timeline.
13. Check Volume Shadow Copies for older MFT versions: enumerate shadows with `vshadowinfo`, mount the oldest covering the window with `vshadowmount`, and repeat the MFT parse — deleted records often survive there intact.
14. Examine `$LogFile` for transactional traces of the deletion when the USN Journal is inconclusive or has wrapped.
15. Search for Alternate Data Stream (ADS) references in the MFT: malware hides payloads in ADS; enumerate streams per record with `istat` and extract suspicious ones with `icat`.
16. Build a super-timeline: merge MFT, USN, `$LogFile`, and carving results into one CSV sorted by timestamp for the final report.
17. Hash every recovered file (SHA-256), scan it in the malware lab, and record its provenance: MFT record number, parent path, timestamps, recovery method.

## Key tools & commands

- `mmls image.E01` — partition layout and offsets.
- `icat -o <offset> image.E01 <inode>` — extract file content by MFT record number.
- `fls -o <offset> -d image.E01` — list deleted directory entries.
- `blkls -o <offset> image.E01` — extract unallocated space for carving.
- `analyzeMFT.py -f mft.bin -o mft.csv` — MFT to CSV timeline.
- `MFTECmd.exe -f <mft> --csv <dir>` — Eric Zimmerman's MFT parser with rich output.
- `scalpel` / `photorec` — header-based file carving of unallocated space.
- `fsstat -o <offset> image.E01` — filesystem metadata overview.
- `istat -o <offset> image.E01 <mft-num>` — detailed metadata for a single MFT record.
- `ffind -o <offset> image.E01 <inode>` — resolve a record number back to its path.
- `vshadowinfo` / `vshadowmount` (libvshadow) — access Volume Shadow Copies for older MFT versions.
- USN Journal parsers — file-operation history beyond what the MFT retains.
- Autopsy — GUI timeline combining MFT, USN, and carving results.

## Expected outputs

- `mft.csv` full MFT timeline with deleted records flagged.
- List of recovered files with SHA-256 hashes, original paths, and timestamps.
- Timestomping candidates (SI/FN mismatch) documented.
- Carving results from unallocated space with hit counts by file type.
- USN Journal deletion/rename events matched to the MFT timeline.
- VSS comparison: which deleted records survived in shadow copies and which did not.
- Findings memo: what was deleted, when, and what content was recoverable.

## Pitfalls

- Parsing the live disk instead of an image — the OS keeps changing the MFT under you.
- Assuming a deleted MFT record means recoverable content; clusters get reallocated quickly on busy volumes.
- Trusting $STANDARD_INFORMATION timestamps alone — check $FILE_NAME times for timestomping.
- Forgetting VSS snapshots: `vssadmin`-style copies may hold older MFT versions with intact deleted records.
- Recovering malware payloads to an uncontained location — treat every recovered binary as live.
- USN Journal wraparound silently losing the history you need — check journal size and age first.
- Attackers disabling VSS (T1490) — verify shadows exist before assuming the VSS route is available.
- Carving false positives on fragmented files — validate carved output against expected sizes and magic bytes.

## References

- Sleuth Kit documentation: https://www.sleuthkit.org/sleuthkit/docs.php
- Eric Zimmerman's MFTECmd documentation
- libvshadow documentation (VSS access)
- Carrier, B. — "File System Forensic Analysis" (Addison-Wesley)
- MITRE ATT&CK T1070.004 (File Deletion), T1070.006 (Timestomp), T1490 (Inhibit System Recovery)
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
