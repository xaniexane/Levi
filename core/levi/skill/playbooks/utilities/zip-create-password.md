---
skill_id: utility.zip_create_password
name: ZIP Create Password
description: Create a password-protected AES-256 ZIP archive with 7-Zip.
risk: moderate
permissions: []
requires_confirmation: true
tags: [zip, archive, encrypt, password]
version: 1.0.0
---

# ZIP Create Password

ZIP Create Password packs files into a ZIP locked with AES-256 encryption, using the 7-Zip command-line tool. The password is taken interactively, never from the command line.

## When to use

- Sending sensitive files where only the recipient may open them.
- Archiving personal documents with a password gate.
- Encrypting a backup before it leaves your machine.

## Steps

1. Stage exactly the files to include; verify the list.
2. Take the password via interactive prompt or environment variable - never as a command-line argument (it leaks into process lists and shell history).
3. Create the archive with 7z using AES-256 and header encryption so filenames are hidden too.
4. Test-extract to a temp location with the password to prove the archive is good.
5. Share the password through a different channel than the archive.

## Honest limits

- Requires the 7-Zip CLI (7z). The standard library's zipfile cannot WRITE encrypted archives - that is a hard limit, not a choice.
- A forgotten password seals the archive permanently.
- ZipCrypto (the old default) is weak; this skill uses AES-256 or it does not run.

Original work authored for LEVI - utilities pack.
