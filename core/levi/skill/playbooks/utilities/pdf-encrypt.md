---
skill_id: utility.pdf_encrypt
name: PDF Encrypt
description: Lock a PDF with a user password and an owner password using AES encryption.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, encrypt, security]
version: 1.0.0
---

# PDF Encrypt

PDF Encrypt seals a PDF so it opens only with the user password, while the owner password controls printing and editing permissions. The sealed copy is a new file.

## When to use

- Sending a sensitive report where only the recipient should open it.
- Archiving personal documents with a password gate.
- Restricting editing on a PDF you distribute.

## Steps

1. Choose two passwords: a user password (to open) and a stronger owner password (permissions). Do not reuse a password you use elsewhere.
2. Load the PDF with pypdf's PdfWriter and call encrypt() with both passwords.
3. Write the encrypted copy to a new file.
4. Test it: open with the user password (works), open without it (refused), and confirm editing is restricted.
5. Deliver the password to the recipient through a different channel than the file.

## Honest limits

- Requires the third-party package pypdf (pip install pypdf).
- A forgotten password seals the file permanently - there is no backdoor and no recovery.
- Encryption guards content, not all metadata; truly sensitive filenames should be renamed first.
- Use AES (pypdf's default); the older RC4 option is weak and should not be chosen.

Original work authored for LEVI - utilities pack.
