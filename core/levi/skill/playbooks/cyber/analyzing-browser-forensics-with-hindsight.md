# Analyzing Browser Forensics with Hindsight

## Purpose

Extract and interpret Chromium-based browser history, downloads, cookies,
and session artifacts using Hindsight to reconstruct user activity for
investigations — phishing clicks, data-exfiltration uploads, session-cookie
theft, and C2-adjacent browsing — with manually verified, report-grade
findings.

## When to use

- Incident response needs a timeline of what a user did in the browser
  before a compromise.
- Investigating suspected data exfiltration via web uploads, personal
  webmail, or file-sharing sites.
- HR/legal-authorized insider investigations involving web activity.
- Corroborating phishing: confirming the user actually clicked the malicious
  link and what happened next (redirects, downloads, credential entry).
- Infostealer triage: determining which sites' stored credentials and
  cookies were exposed.

## Prerequisites

- Written authorization from the asset/data owner (and HR/legal for
  user-activity investigations) to examine browser profile data, which is
  highly personal and often privileged.
- Chain-of-custody notes: hash the copied profile directories, record
  collection time and method before analysis.
- A forensic copy of the browser profile (e.g.,
  `%LOCALAPPDATA%\Google\Chrome\User Data\Default\`), never the live profile
  — Chrome locks its SQLite databases while running, and live access risks
  altering timestamps.
- Hindsight installed on the analysis workstation plus a SQLite browser for
  manual verification of key findings.
- The incident window and the questions to answer, so timeline filtering
  stays scoped.

## Procedure

1. **Acquire the profile forensically.**
   From a disk image or live collection, copy the entire profile directory.
   Record SHA-256 hashes of the copied files.
   If Chrome is running on a live host, prefer Volume Shadow Copy or
   memory-safe collection over killing the browser mid-session — killing it
   can corrupt the very databases you need.
2. **Run Hindsight against the copy:**
   ```bash
   hindsight.py -i /evidence/chrome_profile -o /evidence/hindsight_out \
     -f xlsx
   ```
   Hindsight parses History, Downloads, Cookies, Login Data metadata,
   Preferences, Secure Preferences, and session files into a unified
   timeline.
   Review its log for parse errors — a corrupt History file is itself worth
   noting (possible anti-forensics).
3. **Reconstruct the timeline around the incident window.**
   Filter the Hindsight output to ±24 hours around the event (wider for
   slow-burn insider cases).
   Identify: phishing-link visits (URL + visit time + transition type —
   typed, link click, download, form submit), subsequent redirect chains,
   and any file downloads with full URLs and hashes.
4. **Examine downloads in detail.**
   The Downloads table gives target paths, URLs, referrers, MIME types, and
   interrupt reasons.
   Correlate downloaded file hashes with the files actually on disk — a
   download record with no on-disk file suggests deletion or
   execution-and-cleanup.
   Check Chrome's danger-flag metadata for what the browser itself thought
   of the file.
5. **Review cookies and storage for session theft.**
   List cookies by host for the incident window; session cookies for
   corporate apps appearing alongside attacker-infrastructure visits support
   session-hijack hypotheses.
   Check Local Storage / IndexedDB entries via Hindsight's parsed output
   for tokens and session identifiers an infostealer would target.
6. **Check autofill and login metadata.**
   Hindsight surfaces saved-login metadata (origin URLs and usernames, not
   passwords) — which sites have stored credentials tells you what an
   infostealer would have harvested.
   Cross-reference with credential-theft alerts and force resets for the
   exposed accounts.
7. **Look for anti-forensics.**
   Check for history deletion (gaps inconsistent with browsing patterns),
   recently cleared download records, or profile timestamps suggesting
   cleanup tools ran.
   The absence of expected artifacts in an otherwise active profile is a
   finding — document it.
8. **Verify critical findings manually.**
   For any timeline entry that will appear in a report, open the underlying
   SQLite database (e.g., `History`) and confirm the URL, timestamp
   conversion (Chrome's WebKit epoch: microseconds since 1601-01-01 UTC),
   and visit count yourself.
   Tool output is a lead; the database is the evidence.
9. **Correlate with other sources.**
   Join browser timestamps with proxy/firewall logs (did the visit actually
   egress?), EDR (was a downloaded file executed?), and email (which message
   contained the link?).
   A browser record of a click with no network egress may indicate a blocked
   or failed attempt — still worth reporting, with the caveat stated.
10. **Document and report.**
    Produce a clean timeline: time (UTC, converted correctly), URL, action
    (visit/download/form submit/upload), and evidence source per row.
    Separate confirmed user actions from inferred ones, note profile gaps
    explicitly, and include verification notes for the highest-stakes
    entries.

## Key tools & commands

- Hindsight (`hindsight.py -i <profile> -o <out> -f xlsx|jsonl|sqlite`) —
  automated Chromium artifact parsing into timelines. Honest limits: it
  parses known schema versions; very new Chrome builds may need an updated
  Hindsight release.
- DB Browser for SQLite — manual verification of History/Downloads/Cookies
  tables; the report-grade check.
- Profile-location knowledge — Chrome, Edge
  (`...\Microsoft\Edge\User Data\`), Brave, Opera, and Chromium variants
  keep profiles in predictable `%LOCALAPPDATA%` paths.
- Timeline tools (Plaso/log2timeline, Timesketch) — merge browser findings
  into a super-timeline with filesystem and event-log data.

## Expected outputs

- A parsed Hindsight timeline (spreadsheet/JSONL) covering the incident
  window, with filters documented.
- A verified activity narrative: confirmed clicks, downloads, uploads,
  form submissions, and credential-store exposure.
- Manually verified database excerpts for report-grade findings, with
  timestamp-conversion notes.
- Correlated evidence joins (proxy, EDR, email) with gaps explicitly noted,
  not silently omitted.

## Pitfalls

- Chrome timestamps are microseconds since 1601-01-01 UTC — converting by
  hand incorrectly is a classic error; let the tool convert, then
  sanity-check one value against a known event.
- Sync: a signed-in Chrome profile merges history from the user's other
  devices. Attribute activity to *this host* only with corroborating local
  evidence (downloads to local paths, local EDR execution records).
- Incognito leaves little in History but may leave DNS cache, pagefile, or
  memory traces — absence of History is not absence of browsing. Check
  those secondary sources before concluding.
- Analyzing the live profile while Chrome runs yields locked/incomplete
  databases. Always work on a copy, and hash the copy.
- Extension activity (password managers, malicious extensions) also lives in
  the profile — don't ignore the Extensions directory when session theft is
  suspected.

## References

- Hindsight documentation (Obsidian Forensics) — supported artifacts and
  output formats
- Chromium docs: profile directory structure and SQLite schemas (History,
  Downloads, Cookies)
- SANS / DFIR community write-ups on Chromium forensics timestamp handling
- NIST SP 800-86 (forensic analysis principles applied to browser artifacts)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
