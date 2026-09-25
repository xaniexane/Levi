# LEVI Document Skills

LEVI-native, stdlib-only document skills: read and create `.docx`,
`.xlsx`, and `.pptx` files, plus best-effort text extraction from
`.pdf`. No third-party libraries, no paid APIs, fully local — free core
forever. All examples below are synthetic.

## Skill ids

| Skill | What it does | Risk |
|---|---|---|
| `doc_read` | Read text from `.docx` / `.xlsx` / `.pptx` / `.pdf` (PDF best-effort) | LOW |
| `docx_create` | Create a `.docx` from title + paragraphs + tables | LOW |
| `xlsx_create` | Create an `.xlsx` from headers + data rows | LOW |
| `pptx_create` | Create a `.pptx` deck from title + slides | LOW |
| `pdf_extract` | Best-effort text extraction from a PDF | LOW |

All five are LOW risk with `requires_confirmation=False`: they only
read files the user names and write new files the user names. No
network, no exfiltration, no destructive acts.

## How it works

`.docx`, `.xlsx`, and `.pptx` are zip archives of XML (OOXML). LEVI
builds and parses the minimal valid parts itself with `zipfile` +
`xml.etree` — no other product's code or branding is involved.

## CLI

```bash
# Read any supported format
levi doc read report.docx
levi doc read data.xlsx --json
levi doc read deck.pptx
levi doc read scan.pdf

# Create
levi doc write docx out.docx --title "Q3 Summary" \
  --paragraph "Revenue grew." --paragraph "Costs flat." \
  --table "Item,Qty;Bolts,400"

levi doc write xlsx out.xlsx --header Name --header Qty \
  --row "Bolts,400" --row "Nuts,900"

levi doc write pptx out.pptx --title "Kickoff" \
  --slide "Goals|Ship the release;Learn from users" \
  --slide "Risks|Scope creep"
```

## Format capabilities (and honest limits)

**DOCX** — read: paragraphs in document order, tables as rows × cells.
Write: title (`Title` style), plain paragraphs, simple tables. Not
covered: styles beyond the title, images, headers/footers, tracked
changes, embedded objects.

**XLSX** — read: first worksheet's headers + data rows; strings via the
shared-string table, numbers as numbers, booleans as booleans, sparse
cells reconstructed from cell references. Write: single sheet, strings
deduplicated in the shared-string table. Not covered: formulas (stored
values are read as-is), formatting, merged cells, charts.

**PPTX** — read: shape text per slide in presentation order. Write:
title slides and title-plus-bullet slides; a minimal but valid master /
layout / theme chain is generated so decks open in PowerPoint,
LibreOffice, and Google Slides. Not covered: images, notes, animations,
embedded media.

**PDF — best-effort only.** The extractor decodes `FlateDecode` content
streams and reads the `Tj` / `TJ` text-showing operators, unescaping
literal `(...)` and hex `<...>` strings. It does **not**:

- reconstruct layout or reading order (columns and tables come out flat),
- OCR scanned images — an image-only PDF yields *no text*, reported
  honestly as empty, never invented,
- handle every filter or custom font encoding — unsupported content is
  skipped, and subset-encoded glyphs may decode to wrong characters,
- decrypt anything — **encrypted PDFs are refused** with a clear error.

Treat PDF output as an extraction aid for search and indexing, never as
a faithful rendering of the document.

## Module map

- `core/levi/docs/docx.py` — `.docx` read/create
- `core/levi/docs/xlsx.py` — `.xlsx` read/create
- `core/levi/docs/pptx.py` — `.pptx` read/create
- `core/levi/docs/pdf.py` — best-effort PDF text extraction
- `core/levi/docs/skills.py` — `DOC_SKILLS` registration pack
- `core/levi/docs/cli.py` — `levi doc` command logic
- `tests/test_doc_skills.py` — hermetic round-trip + synthetic-PDF tests
