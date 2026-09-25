---
skill_id: sys_linux_disk_memory_tools
name: Linux Disk and Memory Tools
description: Seeing where space and RAM go: df, du, free, and friends.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux Disk and Memory Tools

## Purpose

Seeing where space and RAM go: df, du, free, and friends.

## Overview

df -h shows filesystem usage per mount (human-readable); df -i shows inode usage - a 'full' disk with free space is usually exhausted inodes from millions of tiny files. du -sh dir summarizes a tree; du -sh * | sort -h finds the hogs; ncdu gives an interactive browser for the same hunt. Deleted-but-open files still occupy space (the handle is held): lsof | grep deleted finds them; restarting the holder or truncating via : > /proc/<pid>/fd/<n> reclaims it. free -h shows RAM: 'available' is the real free-ish number (reclaimable cache included), not 'free'. Buffers/cache are the kernel using spare RAM for speed - not a leak. vmstat 1 and top/htop show live pressure; swapping (si/so columns active) means RAM exhaustion, and the OOM killer will start sacrificing processes - check dmesg. iostat/iotope cover disk throughput when I/O is the bottleneck. Habits: monitor inodes as well as bytes, keep /var/log rotated (logrotate), never let /tmp fill on shared systems, and investigate before rm -rf on a full disk - know what the space is first.

## Quick reference

- df -h: per-mount usage. df -i: inode usage - check when 'full' but bytes free.

- du -sh * | sort -h: find the hogs. ncdu: interactive hunt.

- Deleted-but-open files hold space: lsof | grep deleted.

- free -h: trust 'available', not 'free'. Cache is not a leak.

- Swapping (vmstat si/so) = RAM exhaustion; dmesg shows OOM kills.


## Worked example

Hunting disk and memory pressure:

```
# Where did the disk go?
df -h /
df -i /
du -sh /var/* 2>/dev/null | sort -rh | head

# Deleted but still held open:
lsof | grep -i deleted | head

# Memory reality check:
free -h
vmstat 1 5
dmesg | grep -i 'oom' | tail
```

- df -i catches inode exhaustion: millions of tiny files.

- sort -rh: human-numeric reverse sort for the biggest-first view.

- dmesg reveals OOM-killer victims when processes die mysteriously.


## Common mistakes

- rm on a full disk without checking what is big: deleting the wrong thing.
  Fix: du first, understand, then delete - and keep backups of anything unsure.

- Killing processes for 'high memory' that was just cache.
  Fix: Read 'available'; cache is the kernel working as designed.


## Quick checks

Q: df says full but du shows less - where is the space?
A: Usually deleted-but-open files: the directory entry is gone but a process holds the handle, so blocks stay allocated. lsof | grep deleted finds them; restart the holder to reclaim.


Q: Is high 'used' memory in free -h a problem?
A: Only if 'available' is low. The kernel fills spare RAM with cache deliberately and reclaims it on demand. Worry when available shrinks and swapping starts.


## Mental model

df is the fuel gauge, du is opening the trunk to see which suitcase is heavy, inodes are the number of pockets (run out of pockets with the trunk half empty), and deleted-but-open files are suitcases you threw away while someone is still holding the handle.
