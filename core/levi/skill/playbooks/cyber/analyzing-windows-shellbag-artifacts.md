# Analyzing Windows Shellbag Artifacts

## Purpose

Reconstruct folder-browsing history from Windows Shellbags: which folders a user opened in Explorer, when, and in what order — including folders on removable media and network shares, and folders that have since been deleted. Shellbags persist in `NTUSER.DAT` and `UsrClass.dat`, making them a durable record of user navigation even when the file system no longer shows the folders.

Shellbags answer the question file-system forensics often can't: not "what files exist," but "where did the user go." In exfiltration and insider cases, the browsing path is frequently more probative than the file list.

## When to use

- Proving a user browsed a specific directory (e.g., a sensitive share, a USB drive's folder tree) during the incident window.
- Recovering the names and structure of deleted folders.
- Reconstructing removable-media usage: which folders were opened on a plugged-in USB device.
- Corroborating file-access claims alongside LNK files, jump lists, and RecentDocs.
- Establishing knowledge and intent: repeated navigation to a staging folder undermines "I didn't know it was there."

## Prerequisites

- Written authorization to examine the endpoint(s), with legal basis and scope documented. Shellbags reveal detailed user behavior — apply privacy handling per organizational policy.
- Forensic images or targeted collections of each in-scope user's `NTUSER.DAT` and `UsrClass.dat` (path: `%APPDATA%\..\Local\Microsoft\Windows\UsrClass.dat`), plus transaction logs for dirty hives. Hash at collection; parse copies.
- Chain-of-custody records: source paths, collection timestamps, collector, hashes.
- Investigation timezone plan: Shellbag timestamps are FILETIME UTC — convert explicitly before merging with local-time evidence.
- The USB connection history and file-access artifacts for the same window, collected in the same pass for correlation.

## Procedure

1. Collect and verify the hives. Copy `NTUSER.DAT` and `UsrClass.dat` for each user in scope from the image, hash the copies, and confirm they open cleanly (merge `.LOG` transaction files for dirty hives). Record the Windows version — Shellbag structures differ between versions.
2. Parse with ShellBagsExplorer. Load the hives in Eric Zimmerman's ShellBagsExplorer, which decodes the `BagMRU` and `Bags` keys (`NTUSER\Software\Microsoft\Windows\Shell\BagMRU` on older Windows; `UsrClass.dat\Local Settings\Software\Microsoft\Windows\Shell\BagMRU` on modern versions). Export the parsed results to CSV.
3. Read the folder entries. For each bag record: the folder path or shell-item name, the BagMRU order (which reflects navigation sequence), and the timestamps (first-interaction and last-write where available). Note entries for removable drives (drive-letter paths with volume context) and network paths (`\\server\share\...`).
4. Identify deleted-folder evidence. Shellbags retain entries for folders deleted from the file system — a bag pointing to a path that no longer exists on disk indicates the folder existed and was browsed. Verify the path's absence on the current image and record it as deleted-folder evidence, not as a live path.
5. Reconstruct navigation sessions. Order bags by timestamp within the incident window to rebuild browsing sessions: which folders were opened, in what sequence, and for how long (approximate from consecutive timestamps). Flag sessions touching sensitive shares, exfiltration-staging folders, or removable-media trees.
6. Assess intent from patterns. Distinguish casual browsing (single brief visit) from deliberate activity (repeated visits, deep tree navigation, visits immediately before file-copy indicators). A user who navigated six levels deep into a restricted share, twice, the day before resigning is telling a different story than a single accidental click — report the pattern.
7. Correlate with companion artifacts. Cross-check: LNK files for files opened from those folders, jump lists for application-side history, Prefetch/UserAssist for Explorer-adjacent execution, and USB connection history for removable-media sessions. A shellbag plus a matching USB arrival plus LNK files from the same drive is a strong composite finding.
8. Check Volume Shadow Copies for historical bags. Older shadow copies may contain `UsrClass.dat` versions with bags since overwritten — compare to recover browsing history the current hive no longer holds.
9. Attribute carefully across users. Confirm each bag's hive-to-user mapping (including service and admin accounts that may have browsed while the user was logged on). Never merge two users' shellbags into one narrative.
10. Document precisely. For each relevant bag: the hive and key path it came from, the folder path, timestamps (UTC with conversion noted), deleted-vs-extant status, and corroborating artifacts. Include the ShellBagsExplorer version and hive hashes.

## Key tools & commands

- ShellBagsExplorer (Eric Zimmerman): load `NTUSER.DAT`/`UsrClass.dat`, browse `BagMRU` trees, export CSV.
- Registry Explorer for manual verification of `BagMRU`/`Bags` key structure when parser output looks anomalous.
- `sha256sum` for hashing hives at acquisition.
- Timeline tools (Plaso/log2timeline or spreadsheet) for merging shellbag timestamps with LNK, USB, and file-system timelines.
- LNK/jump-list parsers (LECmd, JLECmd) for the file-level correlation step.
- Volume Shadow Copy examination via your forensic suite for historical hive versions.

## Expected outputs

- Hashed `NTUSER.DAT`/`UsrClass.dat` copies with acquisition logs.
- ShellBagsExplorer CSV exports per user.
- Folder-browsing entries with paths, order, and timestamps.
- Deleted-folder findings (paths in bags but absent on disk).
- Reconstructed navigation sessions for the incident window with intent-pattern assessment.
- Shadow-copy comparison results (if applicable).
- Correlation results against LNK, jump lists, USB history, and file-system evidence.
- Per-finding records with hive/key provenance, user attribution, and tool versions.

## Pitfalls

- BagMRU order reflects MRU (most-recently-used) ordering, not a perfect chronological log — treat sequence as approximate and lean on timestamps.
- Shellbags record folder views, not file opens: a bag for `E:\staging\` doesn't prove which files inside were touched. Pair with LNK/RecentDocs for file-level claims.
- Explorer view settings (window size, sort order) also live in Bags keys — don't mistake view-state entries for navigation evidence.
- Deleted-folder entries can linger for years; a 2019 bag for a deleted folder is not incident evidence without timestamp correlation to your window.
- Multiple users, multiple hives: attribute each bag to the correct user via the hive it came from — mixing users' shellbags is a fast path to a wrong conclusion.
- Search-indexer and thumbnail processes can create bag-like activity without user navigation; a bag with no plausible user session behind it needs a second look.
- Overstating intent: navigation patterns support an intent argument but don't prove it. Present the pattern and let the totality of evidence carry the conclusion.

## References

- Eric Zimmerman's ShellBagsExplorer documentation — key paths and field reference.
- SANS DFIR Windows artifact references for Shellbag locations across Windows versions.
- Microsoft documentation on the Windows Shell namespace and BagMRU behavior.
- NIST SP 800-86 — forensic evidence handling.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
