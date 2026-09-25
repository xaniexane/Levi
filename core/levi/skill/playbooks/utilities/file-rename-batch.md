---
skill_id: utility.file_rename_batch
name: File Rename Batch
description: Rename many files by a pattern with a dry-run preview and explicit confirmation.
risk: moderate
permissions: []
requires_confirmation: true
tags: [files, rename, batch]
version: 1.0.0
---

# File Rename Batch

File Rename Batch renames files according to a rule you define - prefix, suffix, or regex replacement - but always shows the full old-to-new mapping as a dry run first, and only renames after you confirm.

## When to use

- Adding a date prefix to a folder of exports.
- Normalizing photo filenames to a sequence.
- Fixing a systematic typo across many filenames.

## Steps

1. List the target files and define the rename rule precisely.
2. DRY RUN: display every old name next to its proposed new name - all of them, not a sample.
3. Check for collisions (two files landing on the same name) and resolve them before proceeding.
4. Only after explicit confirmation, rename with pathlib; report each rename.
5. Verify the directory listing afterward.

## Honest limits

- There is no undo button - the dry-run preview IS the safety mechanism. Read it fully.
- Never rename across filesystems or into another directory in the same pass; keep the batch to renames.
- Hidden files and extensions need explicit rules, or they get mangled.

Original work authored for LEVI - utilities pack.
