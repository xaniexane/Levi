---
skill_id: cyber_analyzing_windows_prefetch_with_python
name: Analyzing Windows Prefetch with Python
description: Parse Prefetch files programmatically in Python for timeline building.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows]
version: 1.0.0
---
# Analyzing Windows Prefetch with Python

See also: analyzing-prefetch-files-for-execution-history.md

## Purpose

Parse Windows Prefetch files (`.pf` in `C:\Windows\Prefetch`) with a Python-based workflow to build
execution evidence: which programs ran, how many times, when they last ran, and which files and
directories they touched. A scripted approach scales across hundreds of hosts and plugs directly
into triage pipelines where GUI tools don't fit.

Scripted parsing also gives you auditability: the parsing code is versioned, the transformations are
explicit, and the output is queryable — properties that matter when execution evidence goes into a
report or a legal proceeding.

## When to use

- Triage at scale: parsing Prefetch from dozens of hosts collected during incident scoping.
- Building execution timelines programmatically, merged with other artifacts in a pipeline.
- Environments where only Python (no .NET GUI tools) is available on the analysis workstation.
- Validating or supplementing GUI parser output with an independent implementation.
- Recurring hunts: re-running the same execution-anomaly queries against fresh collections.

## Prerequisites

- Written authorization to examine the endpoints, with legal basis and scope documented.
- Forensic images or targeted collections of `C:\Windows\Prefetch\*.pf` with hashes and
  chain-of-custody records. Parse copies, never the live Prefetch directory on a running suspect
  host.
- Python 3 on the analysis workstation plus a Prefetch parsing library or your own parser (see
  tools). Pin library versions for reproducibility.
- Knowledge of the Prefetch format versions (17, 23, 26, 30 corresponding to XP through Windows
  10/11): field layouts differ, and a parser that misdetects the version misreads every timestamp.
- A reference `.pf` file of known content to validate the parser against before trusting it on
  evidence.

## Procedure

1. Collect and verify. Copy the `.pf` files from each host's image into per-host directories, hash
   them, and record the Windows version of each source host (it determines the expected Prefetch
   format version). Note the Prefetch directory's own limits: Windows caps the folder (typically 128
   entries on client SKUs), so absence of a file is not proof of non-execution.
2. Validate the parser. Run your chosen library against the reference `.pf` and compare the output
   (executable name, run count, timestamps) with a second implementation or the format
   specification. Do not proceed until the validation passes — a silently wrong parser is worse than
   no parser.
3. Set up the Python environment. Create a virtual environment and install your chosen parser (e.g.,
   `pyprefetch` or the forensic libraries that bundle Prefetch support), pinning versions in a
   requirements file: `python3 -m venv pfenv && source pfenv/bin/activate && pip install -r
   requirements.txt`.
4. Parse in batch. Write a small driver script that walks the per-host directories, parses each
   `.pf`, and emits one JSON record per file: executable name, full path, run count, last-run
   timestamps (up to 8 on modern formats), file size, hash of the executable (stored in the Prefetch
   header), and the volume serial. Log parse failures per file rather than aborting the batch.
5. Normalize the output. Convert FILETIME timestamps to UTC ISO-8601, normalize paths to lowercase
   for matching, and tag each record with hostname and collection date. Write the normalized records
   to a single JSONL or SQLite store for querying.
6. Hunt for anomalies. Query the store for: executables run from unusual paths (`\Temp\`,
   `\Users\Public\`, removable drives), known dual-use or hacking tools by name, executables with
   run counts of 1 at odd hours (single-run malware), and Prefetch entries whose embedded executable
   hash doesn't match the on-disk binary (possible replacement after execution).
7. Hunt for timestomping and anti-forensics. Compare Prefetch last-run timestamps against the
   executable's file-system timestamps: a binary whose MFT timestamps are older than its Prefetch
   last-run is normal; the reverse (file "modified" after it supposedly last ran, in ways
   inconsistent with updates) deserves a closer look.
8. Correlate with other execution artifacts. Join on executable name/path with Amcache entries,
   UserAssist, Security 4688 events, and Shimcache: match names case-insensitively and compare
   timestamps. Agreement across artifacts raises confidence; a Prefetch-only finding gets a lower
   confidence tag.
9. Build the timeline. Merge last-run timestamps into the case timeline, bounded by the incident
   window. Flag first-seen executions inside the window — the attacker's tooling debuting on the
   host.
10. Report reproducibly. For each finding: executable, path, run count, last-run times, volume
    serial, corroborating artifacts, and the parser/library version plus the driver script itself
    (store it with the case). Findings without the exact parsing code are hard to defend later.

## Key tools & commands

- Python Prefetch parsers: `pyprefetch` (`pyprefetch <file.pf>` prints parsed fields) or equivalent
  libraries; verify against a known sample before trusting a new library.
- Batch driver pattern: `for f in hosts/*/Prefetch/*.pf; do pyprefetch "$f" >> parsed.jsonl || echo
  "FAIL $f" >> failures.log; done` (adapt to your parser's CLI).
- SQLite/`jq` for querying the normalized store: `jq 'select(.path | test("temp"; "i"))'
  parsed.jsonl`.
- `pytest` for the parser-validation step: codify the reference-file expectations as a test so
  re-validation is one command.
- `sha256sum` for hashing collected `.pf` files.
- Reference: the open Prefetch format documentation to sanity-check parser output on at least one
  file per format version encountered.

## Expected outputs

- Hashed per-host Prefetch collections with source Windows versions.
- A parser-validation record (reference file, expected vs. actual, pass/fail).
- A pinned Python environment (requirements file) and the batch driver script.
- Normalized JSONL/SQLite store of parsed records with UTC timestamps.
- An anomaly list: unusual paths, suspicious tools, single-run executions, hash mismatches.
- Timestomping/anti-forensic check results.
- Correlation results against Amcache/UserAssist/4688/Shimcache.
- A merged execution timeline with confidence tags.
- Per-finding write-ups with parser versions and the driver script archived.

## Pitfalls

- Prefetch is capped and FIFO-evicted: on busy systems the attacker's execution may have been
  evicted. Absence is not exoneration.
- Format-version misparse: feeding a version-30 file to a version-17 code path yields garbage
  timestamps. Validate the version field on every file.
- The embedded executable hash is of the binary at trace time; a later update changes the on-disk
  hash — investigate before crying tamper.
- Run counts saturate and timestamps are last-N-runs only: Prefetch tells you the most recent
  executions, not the first. Don't claim "first ran at" from Prefetch alone.
- Unverified third-party parser libraries: cross-check at least one file per format version against
  a second implementation or the format spec.
- Filenames are truncated to 29 characters plus hash in the `.pf` name: `POWERSHELL.EXE-<hash>.pf`
  collisions across different paths are resolved by the embedded full path, not the filename. Always
  read the embedded path.
- Volume serial in the Prefetch header refers to the volume at trace time; drive letters get
  reassigned. Correlate with MountedDevices before attributing to a device.

## References

- Open documentation of the Windows Prefetch file format (version 17/23/26/30 layouts).
- pyprefetch / Python forensic parser library documentation.
- Microsoft documentation on the Prefetch/Superfetch mechanism and its limits.
- NIST SP 800-86 — forensic evidence handling and reproducibility.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
