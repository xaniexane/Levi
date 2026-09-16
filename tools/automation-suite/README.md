# Ultimate-Automation-Suite

A collection of small, dependency-free automation utilities. Everything is
**stdlib-only** (Python 3) or **POSIX shell + coreutils** — no pip packages,
no network calls, no installers.

## Safety rule

**Every script that can change, move, or copy data defaults to dry-run /
report mode and does nothing destructive unless you pass an explicit flag**
(`--apply`, `--move-dupes`). Nothing here deletes user data outright:
duplicates are quarantined, edits keep `.bak` files, and backups are
additive snapshots.

## Layout

```
Ultimate-Automation-Suite/
├── README.md
├── Core/                    # file wrangling
│   ├── smart_file_organizer.py
│   ├── multi_error_file_fixer.py
│   ├── file_debugger.py
│   ├── bulk_file_editor.sh
│   ├── duplicate_finder.sh
│   └── backup_rotator.sh
├── Forensics/
│   └── advanced_browser_carver.py
├── WiFi/
│   └── wifi_network_audit.sh
├── Security/
│   └── security_audit.sh
├── External/
│   └── external_drive_backup.sh
└── Productivity/
    ├── focus_timer.py
    └── quick_note.sh
```

## Core

### smart_file_organizer.py
Sort files in a directory into subfolders by category
(`images/ documents/ audio/ video/ archives/ code/ other/`).

```bash
python3 Core/smart_file_organizer.py ~/Downloads            # dry-run: prints plan
python3 Core/smart_file_organizer.py ~/Downloads --apply    # perform the moves
```
Hidden files are skipped, name collisions become `name_1.ext`, and every
applied move is appended to `<target>/moves_receipt.log`.

### multi_error_file_fixer.py
Iteratively repairs Python files using **only safe whitespace fixes**
(trailing whitespace, tabs→spaces in indentation, missing final newline),
re-running the compiler after each pass. Backs up to `<file>.bak` first.
Real syntax errors are reported as `file:line: message` and the tool stops —
it never guesses at logic.

```bash
python3 Core/multi_error_file_fixer.py broken.py another.py
```

### file_debugger.py
Read-only diagnostic report for any file: size, sha256, text-vs-binary,
encoding guess, line endings, line/word/byte counts, plus a syntax check
for `.py` files.

```bash
python3 Core/file_debugger.py mystery.dat
```

### bulk_file_editor.sh
Literal (non-regex) find/replace across files.

```bash
./Core/bulk_file_editor.sh ./src "TODO" "DONE" --ext py            # dry-run preview
./Core/bulk_file_editor.sh ./src "TODO" "DONE" --ext py --apply    # write (+ .bak each)
```

### duplicate_finder.sh
Find duplicates by sha256.

```bash
./Core/duplicate_finder.sh ~/Photos                        # report groups
./Core/duplicate_finder.sh ~/Photos --move-dupes            # quarantine all but newest
```
`--move-dupes` moves extras into `<dir>/duplicates/` — it never deletes.

### backup_rotator.sh
Rotating snapshots: `<backup_root>/snap-YYYYMMDD-HHMMSS/`.
Seeds each snapshot with hardlinks from the previous one (`cp -al`) so
unchanged files share disk space; falls back to a full copy. Keeps the
newest N (default 7), prunes older.

```bash
./Core/backup_rotator.sh ~/Documents /mnt/backup/docs 7
```

## Forensics

### advanced_browser_carver.py
Read-only Chrome/Chromium history extraction. Copies the live `History`
SQLite DB to a temp file first (the locked live DB is never opened or
modified) and writes `urls.csv` + `report.json` to an output dir.
Local only — no network.

```bash
python3 Forensics/advanced_browser_carver.py --output ./carve
python3 Forensics/advanced_browser_carver.py --profile ~/.config/chromium/Default
```

## WiFi

### wifi_network_audit.sh
Lists nearby networks (SSID, signal, channel, security) via `nmcli`,
falling back to `iwlist`. **Report only — never connects to anything.**

```bash
./WiFi/wifi_network_audit.sh
```

## Security

### security_audit.sh
Defensive local checklist, report only: listening TCP/UDP ports, recent
failed SSH logins (best effort), world-writable files under `$HOME`,
last logins. Changes nothing.

```bash
./Security/security_audit.sh
```

## External

### external_drive_backup.sh
Back up source dirs to an external drive with rsync. Refuses to run unless
the destination is actually a mounted filesystem (typo protection).

```bash
./External/external_drive_backup.sh --dest /mnt/usb ~/Photos ~/Docs          # dry-run
./External/external_drive_backup.sh --dest /mnt/usb ~/Photos ~/Docs --apply  # copy
```

## Productivity

### focus_timer.py
Pomodoro timer with a live countdown; appends completed sessions to a CSV log.

```bash
python3 Productivity/focus_timer.py --work 25 --break 5 --cycles 4
python3 Productivity/focus_timer.py --work 50 --break 10 --cycles 2 --log ~/focus.csv
```

### quick_note.sh
Append a timestamped note to today's markdown file
(`Productivity/notes/YYYY-MM-DD.md`).

```bash
./Productivity/quick_note.sh "remember to rotate backups"
echo "idea: offline-first everything" | ./Productivity/quick_note.sh
```

## Testing

Every script ships tested. The test procedure used at build time:

```bash
# syntax checks
python3 -m py_compile Core/*.py Forensics/*.py Productivity/*.py
bash -n Core/*.sh WiFi/*.sh Security/*.sh External/*.sh Productivity/*.sh
# functional tests ran against fixture data in /tmp/suite-test/
```

## License

Free to use and modify. Built for the LEVI project; stdlib-only forever.
