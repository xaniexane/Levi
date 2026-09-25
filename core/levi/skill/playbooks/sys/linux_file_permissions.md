---
skill_id: sys_linux_file_permissions
name: Linux File Permissions
description: Ownership, mode bits, and the least-privilege habits that keep systems safe.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, security]
version: 1.0.0
---
# Linux File Permissions

## Purpose

Ownership, mode bits, and the least-privilege habits that keep systems safe.

## Overview

Every file has an owner, a group, and three permission triples: user, group, other - each rwx (read, write, execute). ls -l shows -rwxr-xr--: owner full, group read+execute, others read-only. Directories need x to enter/list and w to create/delete entries; r alone on a directory is nearly useless. chmod sets modes numerically (4=r,2=w,1=x: 755 = rwxr-xr-x, 644 = rw-r--r--) or symbolically (u+x, g-w, o=). chown user:group changes ownership (root only for arbitrary changes); chgrp changes group. Defaults come from umask, which masks bits off new files (022 gives 755 dirs / 644 files). Special bits: setuid (4) runs an executable as its owner - powerful and dangerous, audit these; setgid (2) on directories makes new files inherit the directory's group; the sticky bit (1) on /tmp lets users delete only their own files. Least-privilege habits: private keys 600, configs with secrets 600/640, never 777 anything (world-writable = anyone can replace it), web roots readable but not writable by the server user. sudo runs commands as root; configure it narrowly (specific commands, specific users) rather than ALL. When access is denied, check the full path: every parent directory needs x for traversal.

## Quick reference

- Triples: user/group/other, each rwx. ls -l shows them.

- Numeric: 4=r 2=w 1=x. 755 dirs/scripts, 644 files, 600 secrets.

- chmod u+x / o=: symbolic changes. chown user:group, chgrp group.

- umask 022: default giving 755/644.

- setuid: run as file owner (audit!). setgid on dirs: inherit group. sticky: /tmp semantics.

- Never 777. Private keys 600. Denied? Check x on every parent dir.


## Worked example

Sane permissions for a deploy:

```
# Inspect:
ls -l deploy.sh
namei -l /srv/app/config.env   # shows perms of every path component

# Fix up:
chmod 755 deploy.sh            # executable script
chmod 600 /srv/app/config.env  # secrets: owner read/write only
chmod 644 /srv/app/app.conf

# Find dangerous bits:
find /usr/local/bin -perm -4000 -ls   # setuid files: audit these
```

- namei -l reveals which parent directory blocks traversal.

- 600 on secrets: even group members cannot read.

- -perm -4000 finds setuid files - every one is a privilege decision.


## Common mistakes

- chmod 777 to 'fix' a permission error: world-writable everything.
  Fix: Diagnose the actual missing bit (often directory x) and grant minimally.

- Private key at 644: ssh refuses it, and it was world-readable.
  Fix: Keys 600, always; ssh enforces this for a reason.


## Quick checks

Q: I get 'Permission denied' but the file looks readable - why?
A: Check traversal: every parent directory needs the x bit. namei -l shows the whole chain. Also check ACLs (getfacl) and SELinux contexts if plain modes look fine.


Q: When is setuid legitimate vs a red flag?
A: Legitimate: narrow, audited tools like sudo/passwd that must briefly act as root. Red flag: setuid on scripts, world-writable setuid files, or any setuid binary you did not deliberately install.


## Mental model

Permissions are office key cards: owner (your office), group (your floor), other (the public). r lets them read the whiteboard, w lets them erase it, x lets them enter the room. setuid is a master-key badge that acts as the boss while worn - count who holds one.
