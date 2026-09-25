---
skill_id: utility.docx_mail_merge
name: DOCX Mail Merge
description: Fill a Word template's placeholders from CSV rows, producing one document per row.
risk: moderate
permissions: []
requires_confirmation: true
tags: [word, docx, mail-merge]
version: 1.0.0
---

# DOCX Mail Merge

DOCX Mail Merge takes a template document with {{placeholders}} and a CSV of rows, then produces one finished .docx per row - letters, certificates, labels - without touching the template.

## When to use

- Personalizing the same letter for many recipients.
- Generating certificates from a name list.
- Producing per-row documents from any tabular data.

## Steps

1. Build the template with {{field_name}} placeholders matching your CSV headers exactly.
2. Read the CSV with csv.DictReader and confirm every placeholder has a column.
3. For each row, copy the template in memory, replace every placeholder with the row's values.
4. Save each result under a distinct filename (e.g. letter-<name>.docx).
5. Open two or three outputs and verify the substitutions landed in the right places.

## Honest limits

- Requires the third-party package python-docx (pip install python-docx).
- If a placeholder's text is split across Word's internal runs, naive replacement can miss it - keep placeholders as single unbroken runs in the template.
- Empty CSV cells become empty strings; decide beforehand what a missing value should print as.

Original work authored for LEVI - utilities pack.
