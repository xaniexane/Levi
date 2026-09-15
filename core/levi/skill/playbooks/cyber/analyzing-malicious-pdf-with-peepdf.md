# Analyzing Malicious PDFs with peepdf

## Purpose

Malicious PDFs exploit readers through embedded JavaScript, malicious actions
(`/OpenAction`, `/Launch`), and embedded files. peepdf is an interactive Python
tool for dissecting PDF internals object by object. This playbook shows how to
use it to determine whether a PDF is malicious and extract its payloads and
IOCs — statically, without opening the file in a reader.

## When to use

- A suspicious PDF arrived via email, download, or web alert.
- Triage of a PDF flagged by the email gateway or EDR.
- Extracting embedded JavaScript, URLs, or dropped files for IOCs.

See also: analyzing-pdf-malware-with-pdfid.md

## Prerequisites

- Written authorization for malware handling; work in an isolated lab.
- The PDF hashed on receipt with chain of custody.
- peepdf installed (`peepdf` console script from the joxeankoret/peepdf
  project) plus a text editor for reviewing extracted streams.
- Never open the PDF in Adobe Reader, browser, or any rendering viewer during
  analysis — parse structure only.

## Procedure

1. Get a structural overview without rendering: run `pdfid.py suspicious.pdf`
   first (sibling playbook) to count risky elements (`/JavaScript`, `/JS`,
   `/OpenAction`, `/EmbeddedFiles`, `/Launch`, `/XFA`), then open peepdf:
   `peepdf suspicious.pdf`.
2. In the peepdf console, run `info` for metadata (author, creator, creation
   date — often faked, but useful for clustering) and `tree` to see the object
   graph with suspicious nodes flagged.
3. Inspect the catalog and pages objects for `/OpenAction` and `/AA`
   (additional actions) entries — these trigger code on open without user
   interaction beyond opening the file.
4. Examine JavaScript: `object <id>` on `/JS` objects, then
   `js_analyse` to extract and beautify the script. Look for heap-spray loops, shellcode unescaping,
   and calls to vulnerable API methods (`util.printf`, `Collab.getIcon`).
5. Dump encoded streams: `stream <id>` shows the decoded content; use
   `rawobject <id>` if you need the raw bytes. Extract embedded files via
   `object` on `/EmbeddedFiles` nodes and save them for separate analysis.
6. Search across objects for IOCs: `search <term>` for `http`, IP patterns,
   `.exe`, or `cmd`; `xor_search` for obfuscated strings in streams.
7. Check filters and encoding chains (`/Filter /FlateDecode`, ASCIIHex, etc.)
   — multiple nested encodings are a deliberate obfuscation signal.
8. Correlate version targeting: `metadata`/`info` shows the PDF version and
   the producer; match the exploited API against known reader CVEs to assess
   which reader versions are vulnerable.
9. Save findings: export decoded JS and embedded files with hashes, record
   the object IDs where each artifact was found, and write the verdict.
10. If the PDF uses XFA forms, inspect the XFA XML for embedded scripts and
    data-exfiltration URLs — XFA is a separate scriptable attack surface inside
    the PDF, invisible to `/JavaScript`-focused review.
11. Scope fleet exposure: match the PDF's targeted reader behavior against the
    reader versions deployed in your environment to determine who is vulnerable.

## Key tools & commands

- `peepdf <file>` — interactive PDF analysis console.
- `tree`, `info`, `metadata` — structure, stats, and document metadata.
- `object <id>`, `stream <id>`, `rawobject <id>` — object/stream inspection.
- `js_analyse` — JavaScript extraction and analysis.
- `search <term>`, `xor_search <term>` — string hunting across objects.
- `pdfid.py <file>` — quick risky-element triage (sibling playbook).

## Expected outputs

- Verdict: malicious / suspicious / benign, with object IDs cited.
- Extracted artifacts: decoded JavaScript, embedded files (hashed), URLs.
- IOC list and reader-version exposure assessment.
- Recommended blocks and hunt queries (hash, URL, JS constants).

## Pitfalls

- Relying on metadata (author/dates) for attribution — trivially forged;
  use for clustering, not conclusions.
- Missing multi-stage payloads: the JS often downloads stage two — extract
  the URL but detonate it only in the sandbox under separate approval.
- `js_analyse` can miss heavily obfuscated scripts; manually review streams
  flagged by `tree` as suspicious.
- Opening the PDF in a viewer "to confirm" — this is detonation. Never do it.
- Benign PDFs also contain `/JavaScript` (forms); maliciousness is in what
  the script does, not its mere presence.
- XFA-based payloads hide from object-tree review focused only on `/JavaScript`
  — check `/XFA` entries explicitly.
- Forgetting to hash extracted embedded files before sending them onward —
  maintain chain of custody for every artifact you carve out.

## References

- peepdf documentation (github.com/joxeankoret/peepdf)
- PDF specification (ISO 32000) — object model and action types
- MITRE ATT&CK: T1204.002 (Malicious File), T1203 (Exploitation for Client
  Execution)
- Didier Stevens' PDF analysis tooling notes (for pdfid complement)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
