---
skill_id: sys_linux_tar_rsync
name: Linux tar and rsync
description: Archiving with tar and syncing with rsync: moving trees of files correctly.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux tar and rsync

## Purpose

Archiving with tar and syncing with rsync: moving trees of files correctly.

## Overview

tar bundles directory trees into one file (optionally compressed): tar -czf out.tar.gz dir/ creates, tar -tzf out.tar.gz lists, tar -xzf out.tar.gz extracts. Flags: c create, x extract, t list, z gzip, f file (must be last before the name). Modern tar auto-detects compression on extract, so tar -xf works for most. Exclude with --exclude='*.log'. Preserve permissions with -p on extract as root. rsync syncs trees efficiently - it transfers only differences: rsync -avz src/ dst/. The trailing slash matters enormously: src/ copies the contents, src copies the directory itself. -a archive mode (permissions, times, symlinks), -v verbose, -z compress in flight, --delete removes destination files absent from source (mirror mode - double-check direction first), -n/--dry-run previews. -e ssh is default for remote paths. Checksums (-c) verify by content instead of size+time when correctness beats speed. Defensive habits: extract tarballs into an empty directory (tarbombs and absolute paths are real), verify --delete direction with dry-run, and keep one known-good backup before destructive syncs.

## Quick reference

- tar -czf out.tar.gz dir/: create. -tzf: list. -xzf: extract.

- rsync -avz src/ dst/: sync. Trailing slash on src/ = contents, not dir.

- --delete mirrors (dangerous): dry-run with -n first.

- --exclude skips patterns. -c verifies by checksum.

- Extract tarballs into empty dirs (tarbombs/absolute paths are real).


## Worked example

Archive, list, and mirror safely:

```
# Create and verify:
tar -czf site-2026-09-22.tar.gz --exclude='*.log' site/
tar -tzf site-2026-09-22.tar.gz | head

# Extract into a fresh dir:
mkdir restore && tar -xzf site-2026-09-22.tar.gz -C restore

# Mirror to backup, preview first:
rsync -avz --delete -n site/ backup:/srv/site/
rsync -avz --delete site/ backup:/srv/site/
```

- --exclude keeps logs out of the archive.

- -C restore: extract into a fresh directory, never over live files blindly.

- -n dry-run shows what --delete would remove before it happens.


## Common mistakes

- --delete with source and destination swapped: mirrored the wrong way.
  Fix: Dry-run (-n) first; --delete destroys what is missing from source.

- Extracting an untrusted tarball as root in /: absolute paths overwrite.
  Fix: List first, extract into an empty dir, inspect, then move.


## Quick checks

Q: Why did rsync create an extra nested directory?
A: Trailing slash: `rsync -a src dst` creates dst/src; `rsync -a src/ dst` copies the contents into dst. Pick deliberately every time.


Q: tar extracted files all over my cwd - what happened?
A: A tarbomb: the archive had no top-level directory. Always list (-t) first and extract into a fresh directory with -C.


## Mental model

tar is packing a suitcase: everything for the trip in one labeled bag. rsync is a meticulous housekeeper who compares two rooms and moves only what changed - but tell it which room is the master, or it will 'tidy' the wrong one (--delete).
