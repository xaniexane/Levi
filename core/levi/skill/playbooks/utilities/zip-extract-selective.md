---
skill_id: utility.zip_extract_selective
name: ZIP Extract Selective
description: Extract only the archive entries you choose, with zip-slip path protection.
risk: moderate
permissions: []
requires_confirmation: true
tags: [zip, archive, extract]
version: 1.0.0
---

# ZIP Extract Selective

ZIP Extract Selective lists an archive's contents, lets you pick entries by name pattern, and extracts just those - validating every output path so a malicious archive cannot write outside your target folder.

## When to use

- Pulling one file out of a huge archive.
- Extracting only .csv files from a data bundle.
- Safely opening an archive from an untrusted source.

## Steps

1. List the archive entries and confirm which match your selection pattern.
2. For each chosen entry, resolve its output path and reject anything escaping the target directory (zip-slip guard).
3. Extract the selected entries; prompt for the password if the archive is encrypted.
4. Verify the extracted files are present and intact.

## Honest limits

- Standard library zipfile is enough for listing and extraction.
- The zip-slip check is mandatory, not optional - archives from strangers get no trust.
- Encrypted entries need the password; without it they stay sealed.

Original work authored for LEVI - utilities pack.
