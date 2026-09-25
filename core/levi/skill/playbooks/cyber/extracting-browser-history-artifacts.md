---
skill_id: cyber_extracting_browser_history_artifacts
name: Extracting Browser History Artifacts
description: Forensically collect and analyze browser history, cache, and session artifacts from Chrome, Edge, and Firefox for investigations.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, artifacts, investigation]
version: 1.0.0
---
## Purpose

Browser artifacts — history, downloads, cookies, sessions, cache, and
form data — reconstruct what a user (or malware operating as the user) did
on the web: sites visited, files downloaded, credentials used, and
timestamps. This playbook covers forensically sound collection and
analysis of Chromium-based (Chrome/Edge) and Firefox artifacts.

## When to use

- Insider-threat or data-exfiltration investigations (webmail, cloud
  storage, paste sites).
- Malware triage: browsers are common C2 and staging channels.
- HR/legal investigations requiring web-activity reconstruction.
- Incident scoping: determining whether a phishing link was clicked and
  what followed.

## Prerequisites

- Legal/HR authorization for user-activity review; confirm the
  investigation's scope and privacy constraints before accessing content.
- Forensic copies of the profile directories (never analyze the live
  profile in place if the machine is evidence).
- Tools: SQLite browser, Hindsight or Autopsy, and a timeline tool.
- Note of the system timezone and the browser's timestamp formats
  (WebKit microseconds vs. Unix epoch vs. PRTime).

## Procedure

1. **Preserve the profiles.** Copy the full profile directories
   (Chrome/Edge `User Data`, Firefox `Profiles`) from a forensic image
   or via a forensically sound collection. Record hashes of the copied
   files for chain of custody.
2. **Handle locked databases.** Chromium locks its SQLite databases while
   running; work from the copy. If the copy is locked or WAL files are
   present, include the `-wal`/`-shm` files and checkpoint before
   querying, or use a forensic parser that handles them.
3. **Parse history and downloads.** Query `History` (urls, visits,
   visit_source) for the browsing timeline and `History` downloads
   tables for downloaded files, source URLs, and completion state.
   For Firefox, parse `places.sqlite` (moz_places, moz_historyvisits)
   and `downloads.sqlite`/annotations.
4. **Examine cookies and sessions.** Review `Cookies` for session tokens
   (useful for session-hijack scoping — handle as sensitive), and
   `Current Session`/`Session Storage` (LevelDB in newer Chromium) for
   open tabs at acquisition time. Firefox: `sessionstore.jsonlz4`.
5. **Check cache and form data.** Carve the cache for retrieved content
   (pages, images, scripts) that may no longer be in history; review
   `Web Data` (autofill) and `Login Data` (stored credentials — encrypted
   with OS key material; note the dependency rather than attempting
   decryption without authority).
6. **Correlate with system artifacts.** Align browser timestamps with
   prefetch/SRUM (Windows), download-folder MAC times, proxy/firewall
   logs, and DNS cache to validate the timeline and catch anti-forensic
   deletion.
7. **Look for anti-forensics.** Gaps in history with intact cache,
   cleared downloads with surviving files, private/incognito usage
   (limited artifacts — check DNS cache and memory instead), and
   history-deletion tools in execution artifacts.
8. **Report with caveats.** Present the reconstructed timeline with
   timestamp-source notes, distinguish visited vs. cached vs. typed URLs
   (visit_source/transition types), and flag any interpretation limits.

## Expected outputs

- Hashed forensic copies of browser profiles with chain-of-custody
  notes.
- A browsing timeline: URLs, visit counts, typed vs. linked navigation,
  downloads with source URLs and hashes.
- Session/cookie inventory relevant to the investigation scope.
- A findings report with timestamp caveats and anti-forensic
  observations.

## Pitfalls

- Analyzing the live profile modifies access times and may trigger
  sync — always work from a copy.
- Timestamps differ by browser and table; converting wrong (WebKit epoch
  vs. Unix epoch) shifts events by decades — verify with a known event.
- Synced history blends devices: a URL in history may have been visited
  on another device — check sync metadata before attributing.
- Login Data decryption needs the OS user key; on a dead-box image you
  may need the user's DPAPI master key — plan for this early.
- Private browsing leaves minimal disk artifacts; do not conclude
  "nothing happened" — check network and memory sources.

## References

- Hindsight project documentation (Chromium forensics)
- Autopsy documentation: web artifact analyzers
- Mozilla documentation: Firefox profile file formats
- NIST SP 800-86: Guide to Integrating Forensic Techniques into
  Incident Response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
