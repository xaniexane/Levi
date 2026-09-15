# Analyzing Disk Images with Autopsy

## Purpose

Conduct a structured forensic examination of a disk image in Autopsy — from
ingest configuration to timeline analysis to artifact extraction — producing
defensible findings without altering the evidence, and answering scoped
investigation questions rather than "looking around."

## When to use

- Post-acquisition analysis of a disk image (see the companion acquisition
  playbook) during incident response or digital investigations.
- Triage of a suspect workstation: what ran, what was accessed, what was
  deleted, what left the machine.
- Malware staging analysis: finding droppers, payloads, and persistence
  artifacts on disk.
- Building timelines that correlate filesystem, registry, browser, and
  event-log evidence.
- Data-theft scoping: which files were accessed or exfiltrated in the
  incident window.

See also: acquiring-disk-image-with-dd-and-dcfldd.md

## Prerequisites

- Written authorization from the asset/data owner to examine the image
  contents (which may include personal, privileged, or regulated data —
  scope accordingly).
- Chain-of-custody notes: verify the image hash matches the acquisition
  record *before* opening it in Autopsy; record the verification with
  timestamp.
- A verified forensic image (E01, raw/dd, or VHD) — never the original
  media — plus a workstation with Autopsy, adequate RAM, and sufficient disk
  for the case database (which can rival the image size).
- Case context: the incident window, relevant users, and written
  investigation questions, so analysis stays scoped and defensible.

## Procedure

1. **Verify before you analyze.** Re-hash the image and compare to the acquisition hash log. If it doesn't match, stop — you have an integrity problem, not an analysis task. Record the verification in the case notes with the hash values, not just "verified."
2. **Create the case properly.** New case → meaningful case name/number → add the image as a data source with the correct timezone. Set the timezone to the evidence's locale; timeline errors from wrong timezones are embarrassing, avoidable, and discoverable by opposing counsel.
3. **Configure ingest modules deliberately.** Enable: Hash Lookup (with NSRL to filter known-good), Keyword Search (with case-specific terms prepared in advance — IOCs, project names, attacker tool names), Recent Activity, EXIF parsing, and Extension Mismatch Detection. Disable modules irrelevant to your questions — ingest time is finite and every module adds noise you'll have to triage. Document the enabled set in the case notes.
4. **Let ingest finish before deep analysis.** Monitor the ingest progress bar; analyzing partial results leads to missed evidence and rework. Use the wait productively: refine your keyword list, review the case background, and prepare your triage checklist.
5. **Triage the high-value artifacts first.** Work in this order: (a) execution artifacts — Amcache, Shimcache, Prefetch, UserAssist, BAM/DAM; (b) persistence locations — Run keys, Startup folders, Services, Scheduled Tasks, WMI subscriptions; (c) browser history and downloads; (d) USB/device history and mounted shares; (e) deleted-file recovery in unallocated space. This order answers "what ran and persisted" fastest, which is what incident commanders need first.
6. **Build and filter the timeline.** Use Autopsy's Timeline to narrow to the incident window, then filter by event type (file created, program executed, web visited). Correlate sequences: file creation → execution artifact → network connection → file deletion tells the story of an intrusion better than any single artifact. Export timeline slices for the report.
7. **Run targeted keyword searches.** Beyond the ingest list, search for: IOCs from threat intel (IPs, domains, filenames, mutexes), attacker tool names, and case-specific terms (data keywords for exfiltration scoping). Review every hit in context — a keyword in a browser cache entry means something different than in a deleted document or an unallocated-space carve.
8. **Examine the registry hives.** Load SYSTEM/SOFTWARE/NTUSER.DAT via Autopsy's registry support: review Run keys, Services, typed URLs, mounted devices (USBSTOR), network profiles, and Shimcache remnants. Correlate registry timestamps with the timeline — registry writes are often the most precise execution evidence.
9. **Recover and carve deliberately.** Check unallocated space and file slack for deleted artifacts relevant to your questions (deleted logs, staged archives, wiped tooling). Carving everything produces mountains of false positives — scope carving to file types tied to your investigation questions, and validate carved files (headers, sizes) before treating them as evidence.
10. **Check event logs within the image.**
    Autopsy parses Windows event logs — review Security (logons, process
    creation if enabled), System (service installs, crashes), and
    PowerShell/Operational logs around the incident window.
    Correlate log entries with filesystem and registry findings; mismatches
    (log says X ran, no execution artifact) are themselves investigative
    leads.
11. **Tag, report, and preserve.**
    Tag every finding with Autopsy's tagging as you go (bookmark notable
    items immediately, not at the end — you'll forget).
    Generate the HTML/Excel report, write the analyst narrative linking
    artifacts to conclusions with explicit confidence levels, and export the
    case notes.
    Archive the case database with the image; both are evidence with
    retention requirements.

## Key tools & commands

- Autopsy (Sleuth Kit GUI) — ingest modules, timeline, keyword search,
  registry parsing, event-log parsing, reporting. Honest limits: it's only
  as good as the ingest configuration and the analyst driving it;
  default-everything runs waste time and bury signal.
- The Sleuth Kit CLI (`fls`, `icat`, `mmls`, `fsstat`) — surgical
  extraction when the GUI is clumsy, e.g.
  `icat -o <offset> image.dd <inode> > recovered.bin`.
- Hash sets (NSRL / custom known-good sets) — known-good filtering to
  reduce triage volume; build org-specific sets for your standard builds.
- A hex viewer / SQLite browser — manual verification of any artifact that
  will appear in a report.

## Expected outputs

- A verified, hashed case with completed ingest and documented module
  configuration.
- Tagged findings mapped to each investigation question, with artifact
  paths, timestamps, and confidence levels.
- A correlated timeline of the incident window, exported for the report.
- An Autopsy-generated report plus analyst narrative, archived with the
  image and case database.

## Pitfalls

- Analyzing with the wrong timezone set — every timestamp in your report
  shifts. Set it at case creation and verify against a known event.
- Trusting hash-lookup "known good" blindly: NSRL doesn't know your
  organization's custom tools; verify before dismissing, and maintain
  org-specific sets.
- Keyword searching without context review — hits in pagefile.sys,
  hiberfil.sys, or unallocated space need interpretation, not just counting.
- Forgetting that Autopsy doesn't parse everything: check your version's
  artifact coverage in the release notes and supplement manually (or with
  specialized tools) where needed.
- Scope creep: "while I'm here" analysis of unrelated user data creates
  privacy exposure and muddies the report. Answer the investigation
  questions; note anything else separately for authorization review.

## References

- Autopsy documentation (Basis Technology / Sleuth Kit) — ingest modules,
  timeline, tagging, reporting
- NIST SP 800-86 (forensic analysis phases: collection, examination,
  analysis, reporting)
- SANS / DFIR community Autopsy walkthroughs (artifact triage order)
- Sleuth Kit CLI reference (`fls`, `icat`, `mmls`, `fsstat`) for manual
  extraction

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
