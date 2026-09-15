# Analyzing Slack Space and File System Artifacts

## Purpose

Recover and interpret data that the file system hides in plain sight: file slack (the unused bytes
between a file's logical end and the end of its last allocated cluster), unallocated clusters, and
deleted-file remnants. This supports investigations where deleted content, overwritten fragments, or
anti-forensic wiping are suspected — extracting whatever the allocation structures still point to.

File slack is particularly valuable because it is created unintentionally: every non-resident file
on a cluster-based file system potentially carries fragments of whatever previously occupied its
final cluster. Attackers who "securely delete" a file often leave its slack untouched.

## When to use

- Deleted files are central to the case (e.g., a suspect emptied the recycle bin before seizure) and
  standard recovery came up short.
- You suspect file slack was used to hide data (steganographic slack hiding) or contains fragments
  of previous file contents.
- Wiping tools were run and you need to assess what remains recoverable in unallocated space.
- Building a timeline of file-system activity where metadata alone is ambiguous.
- Validating whether a "wiped" drive was actually wiped, e.g., after a decommissioning dispute.

## Prerequisites

- Written authorization to examine the media, including the legal basis (consent, warrant, or
  organizational investigation charter) and the scope of files/partitions covered.
- A forensically sound image of the media (bit-for-bit, e.g., via `dcfldd` or FTK Imager) with
  verified hashes (MD5/SHA-1/SHA-256 recorded at acquisition). Work exclusively on the image or a
  working copy — never the original media.
- A documented chain of custody: acquisition date, imaging tool and version, hash values, storage
  location, and every handler's identity.
- Know the file system type (NTFS, FAT32, exFAT, ext4, APFS) before choosing tools — slack and
  unallocated-space mechanics differ per file system.
- Note the storage technology: TRIM-enabled SSDs aggressively zero unallocated pages, which
  fundamentally limits what unallocated-space carving can recover compared to spinning disks.

## Procedure

1. Verify the image. Recompute hashes of your working copy and compare against the acquisition
   record. Record the file system layout: partitions, offsets, and types, using `mmls` (Sleuth Kit)
   or your forensic suite's partition view.
2. Map allocated vs. unallocated space. Run `fls -r -p` on the NTFS/FAT partition to list all file
   entries including deleted ones (marked with `*`), and note the cluster size (`fsstat` reports
   it). Cluster size determines slack geometry: slack per file = cluster size − (file size mod
   cluster size), when the remainder is nonzero.
3. Enumerate unallocated regions precisely. Use `blkls` (Sleuth Kit) to extract the unallocated
   blocks into a separate stream for targeted carving, keeping allocated content out of the carve
   set. Record the block ranges so findings map back to image offsets.
4. Extract file slack for files of interest. For each target file, use `icat` to dump its allocated
   content, then compute which trailing bytes of its final cluster fall beyond the logical EOF —
   those bytes are slack. On NTFS, resident files in the MFT have no slack (no cluster allocated);
   only non-resident files do. Document the inode/MFT record number for each extraction.
5. Carve unallocated space for known file types. Run `bulk_extractor` against the unallocated region
   (or the whole image with allocated-space scanning disabled for speed) to pull emails, URLs, EXIF
   data, and credit-card-patterned strings. In parallel, run a signature carver (e.g., `scalpel`
   with a tuned config, or PhotoRec) for document and image headers/footers.
6. Inspect slack and carve results for case relevance. Search the extracted content with targeted
   keywords (case-specific terms, not broad fishing): `grep -a -i -C 3 "keyword" carved_output/`.
   Review hits in context — a fragment in slack is evidence of prior content, not proof of current
   intent.
7. Check for deliberate slack hiding. Compare slack content against random-data expectations: slack
   that contains structured data (repeated headers, encrypted-looking blobs of uniform size across
   many files) suggests intentional concealment rather than leftover fragments. Note the pattern and
   the files involved.
8. Assess wiping effectiveness if applicable. If a wiping tool was allegedly run, sample unallocated
   space for recoverable structured data; significant recovery contradicts the wipe claim.
   Distinguish a proper multi-pass wipe from a quick format, which leaves nearly everything
   recoverable.
9. Correlate with file-system metadata. Tie recovered fragments to MFT records: file name,
   timestamps (created/modified/accessed/entry-modified), and parent directory. A fragment in
   unallocated space with a matching deleted MFT entry is far stronger than an orphan fragment.
10. Document and hash everything. Hash each extracted artifact, record the source image offset or
    MFT record it came from, the tool and version used, and the exact command line. Add all of it to
    the case evidence log.

## Key tools & commands

- The Sleuth Kit: `mmls image.dd` (partition layout), `fsstat -o <offset> image.dd` (file system
  details including cluster size), `fls -r -p -o <offset> image.dd` (recursive listing with deleted
  entries), `icat -o <offset> image.dd <inode>` (file content extraction), `blkls -o <offset>
  image.dd` (unallocated block extraction), `dls` (deleted-entry listing on FAT).
- `bulk_extractor -o bulk_out image.dd` for automated feature extraction from unallocated space
  (emails, URLs, EXIF).
- `scalpel` / PhotoRec for signature-based file carving from unallocated clusters.
- Autopsy as a GUI front end over Sleuth Kit for timeline correlation and keyword search.
- `dcfldd hash=md5,sha256 of=image.dd if=/dev/sdX` for forensically sound acquisition with hashing.
- `grep -a` for binary-safe string searches through carved output.

## Expected outputs

- Verified image hashes and a partition/file-system map.
- A file listing including deleted entries with MFT/inode numbers.
- Unallocated block ranges extracted via `blkls` with offset mapping.
- Extracted slack contents for files of interest, each hashed and sourced.
- Carved artifacts from unallocated space with signature-match details.
- Keyword-search hit list with context lines.
- An assessment of whether slack content looks like leftover fragments vs. deliberate concealment.
- A wiping-effectiveness assessment (if in scope).
- A complete evidence log: tool versions, command lines, hashes, and source offsets.

## Pitfalls

- Confusing RAM slack (the sector-level pad between EOF and end of sector, historically containing
  memory remnants on old Windows) with file slack (cluster-level); modern Windows zeroes RAM slack,
  so expect zeros there.
- Carving false positives: file headers appear in random data by chance — always validate carved
  files open/render correctly before treating them as evidence.
- Overwriting the evidence: mounting the original media read-write or booting the suspect drive
  destroys exactly the slack and unallocated content you are after. Always work from the image.
- Keyword searches that are too broad produce thousands of hits and waste review time; too narrow
  and you miss obfuscated terms. Iterate.
- NTFS resident files have no slack — don't report "no slack found" as a negative finding for small
  files; it's structural.
- SSD TRIM: on TRIM-enabled solid-state media, unallocated pages may already be zeroed by the
  controller. Calibrate recovery expectations and document the media type.
- Attributing slack fragments to the current file's owner: slack belongs to whoever wrote the
  previous occupant of that cluster, which may be a different user or application entirely.

## References

- Carrier, B. — "File System Forensic Analysis" (Addison-Wesley): the definitive reference on slack
  space, unallocated space, and file system internals.
- The Sleuth Kit documentation (sleuthkit.org) — `fls`, `icat`, `fsstat`, `mmls`, `blkls` usage and
  output interpretation.
- NIST SP 800-86 "Guide to Integrating Forensic Techniques into Incident Response" — evidence
  handling and chain of custody.
- bulk_extractor documentation — feature extractors and unallocated-space workflows.
- Research literature on SSD TRIM effects on forensic recovery — for calibrating expectations on
  flash media.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
