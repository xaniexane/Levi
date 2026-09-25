---
skill_id: sys_os_filesystems_inodes
name: OS Filesystems and Inodes
description: How files really live on disk: inodes, directories, links, and mounts.
risk: info
permissions: []
requires_confirmation: false
tags: [os, storage]
version: 1.0.0
---
# OS Filesystems and Inodes

## Purpose

How files really live on disk: inodes, directories, links, and mounts.

## Overview

A Unix filesystem separates names from data. The inode holds metadata - type, permissions, owner, timestamps, size, and pointers to data blocks - but NOT the filename. Directories are tables mapping names to inode numbers; the same inode can appear under multiple names (hard links), which is why files have a link count and survive until the last name is unlinked. Symbolic links are separate tiny files holding a path string - they break when the target moves, unlike hard links. ls -i shows inode numbers; df -i shows inode exhaustion (the 'disk full with free space' mystery). Journaling filesystems (ext4, xfs, APFS) log metadata changes first for crash consistency; copy-on-write filesystems (btrfs, ZFS) add snapshots and checksums. Mounts graft filesystems onto the tree (mount /dev/sdb1 /data); /etc/fstab makes them persistent. Permissions live in the inode, so moving a file within a filesystem keeps them, while copying creates anew. Defragmentation matters for spinning disks, negligibly for SSDs. Operational habits: monitor inode usage alongside bytes, keep backups filesystem-agnostic (tar/rsync), and remember deleting an open file frees the name but not the blocks until the last handle closes.

## Quick reference

- Inode = metadata + block pointers. Filename lives in the directory, not the inode.

- Hard links: multiple names, one inode. Symlinks: path strings, can break.

- df -i: inode usage - the 'full disk with free space' answer.

- Journaling (ext4/xfs): crash consistency. CoW (btrfs/ZFS): snapshots, checksums.

- mount grafts filesystems onto the tree; /etc/fstab persists them.

- Deleting an open file frees the name, not the blocks, until handles close.


## Worked example

Inodes, links, and mounts in practice:

```
# Inode numbers and link counts:
ls -li file.txt
ln file.txt hardlink.txt     # same inode, link count 2
ln -s /etc/hostname soft.txt # symlink: a path string
ls -li

# Inode pressure:
df -i / | tail -1

# What's mounted where:
findmnt
mount | grep ' /data '
```

- ls -li: first column is the inode number; hardlink shares it.

- Symlinks show their own inode pointing at a path, not data.

- findmnt draws the mount tree readably.


## Common mistakes

- rm on a symlinked directory's contents via trailing slash surprises.
  Fix: Know whether your tool follows the link; test with ls first.

- Filling inodes with millions of tiny files, then blaming bytes.
  Fix: Monitor df -i; archive small files (tar) to collapse inode usage.


## Quick checks

Q: Why does deleting a file not always free space?
A: Two reasons: hard links (other names still reference the inode) and open file handles (the kernel keeps blocks until the last handle closes). lsof | grep deleted diagnoses the second.


Q: Hard link vs symlink - when each?
A: Hard links for space-efficient same-filesystem aliases that must survive renames (backups). Symlinks for cross-filesystem references, directory links, and version pointers (current -> v2.4).


## Mental model

Inodes are library catalog cards (metadata + shelf location); directories are the card catalog drawers mapping titles to card numbers. Hard links are two catalog entries for the same card; symlinks are 'see also' notes that go stale when the book moves.
