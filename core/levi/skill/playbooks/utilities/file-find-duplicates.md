---
skill_id: utility.file_find_duplicates
name: File Find Duplicates
description: Find duplicate files by content hash and report them - never deletes anything.
risk: low
permissions: []
requires_confirmation: false
tags: [files, duplicates, hash]
version: 1.0.0
---

# File Find Duplicates

File Find Duplicates walks a directory tree, hashes every file with SHA-256 (streamed in chunks), groups files with identical hashes, and displays the groups with sizes. It is strictly read-only: deletion is a human decision made elsewhere.

## When to use

- Finding wasted space from duplicated downloads.
- Checking whether two folders hold the same files.
- Auditing a photo library for exact copies.

## Steps

1. Walk the target directories, skipping symlinks or noting them explicitly.
2. Hash each file in chunks so large files do not exhaust memory.
3. Group paths by digest; display groups of two or more with file sizes.
4. Report total duplicate bytes reclaimable - then stop. Deletion is not this skill's job.

## Honest limits

- Standard library only (hashlib, pathlib).
- Identical hash means identical content for practical purposes; identical size alone does not.
- This skill reports only. Anything that deletes needs your explicit separate decision.

Original work authored for LEVI - utilities pack.
