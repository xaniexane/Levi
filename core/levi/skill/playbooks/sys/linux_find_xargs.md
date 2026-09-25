---
skill_id: sys_linux_find_xargs
name: Linux find and xargs
description: Finding files by criteria and acting on them safely at scale.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux find and xargs

## Purpose

Finding files by criteria and acting on them safely at scale.

## Overview

find searches directory trees by criteria instead of names alone: -name '*.log' (basename glob), -iname (case-insensitive), -type f/d/l, -size +100M, -mtime -7 (modified in the last 7 days), -newer ref, -user, -perm, -empty. Tests combine with -a/-o/! and group with escaped parentheses. Actions: -print (default), -delete, -exec cmd {} + (batched, preferred) or -exec cmd {} \; (one process per file, slow). The + form batches like xargs. xargs builds command lines from stdin: echo files | xargs rm. Its power is batching and parallelism (-P 4 runs 4 workers), its footgun is whitespace: default splitting breaks on spaces and quotes. The safe pattern is find ... -print0 | xargs -0 cmd, using null delimiters that filenames cannot contain. -I{} enables placeholder placement for commands needing the name mid-argument; -n1 forces one argument per invocation when batching is wrong. Modern alternative: fd and rg are faster, more ergonomic find/grep replacements worth installing. Defensive rule: preview with -print before adding -delete or piping to rm - a find typo with -delete is unrecoverable.

## Quick reference

- find tests: -name/-iname, -type, -size, -mtime, -user, -perm, -empty.

- -exec cmd {} +: batched action (preferred). -delete: remove matches.

- xargs: stdin -> arguments. -P N: parallel workers.

- Safe pattern: find ... -print0 | xargs -0 cmd (null-delimited).

- Preview with -print before -delete or piping to rm.

- fd/rg: faster modern alternatives to find/grep.


## Worked example

Safe bulk operations with null delimiters:

```
# Preview first:
find . -name '*.tmp' -mtime +30 -print

# Then act, null-delimited so weird names are safe:
find . -name '*.tmp' -mtime +30 -print0 | xargs -0 rm -v

# Parallel compression of logs, 4 workers:
find /var/log -name '*.log' -print0 | xargs -0 -P 4 gzip

# Batched chmod via -exec + (no xargs needed):
find . -type f -name '*.sh' -exec chmod +x {} +
```

- -mtime +30: modified more than 30 days ago.

- -print0/-0: null delimiters survive spaces, quotes, and newlines in names.

- -P 4: four parallel gzip workers; -exec {} + batches internally.


## Common mistakes

- find / -delete with a typo'd -name: unrecoverable mass deletion.
  Fix: Always -print first, eyeball it, then add the destructive action.

- Piping newline-separated names into xargs with spaces in names.
  Fix: Null-delimit: -print0 | xargs -0, every time.


## Quick checks

Q: Why did xargs choke on my filenames?
A: Default xargs splits on whitespace and honors quotes - filenames with spaces break into pieces. Use -0 with find -print0, or -d'\n' for newline-delimited input you control.


Q: -exec {} \; vs {} + vs xargs - which?
A: {} + batches into few invocations and needs no pipe - simplest. xargs adds -P parallelism and -I{} placement. \; is one process per file: slowest, rarely right.


## Mental model

find is a detective with a description (name, size, age of file); xargs is the work crew that acts on whoever the detective rounds up. Null delimiters are handcuffs that cannot slip - without them, suspects with tricky names (spaces) escape mid-transfer.
