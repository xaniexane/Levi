---
skill_id: sys_os_file_descriptors
name: OS File Descriptors
description: The universal I/O handle: fds, the standard trio, and descriptor hygiene.
risk: info
permissions: []
requires_confirmation: false
tags: [os, linux]
version: 1.0.0
---
# OS File Descriptors

## Purpose

The universal I/O handle: fds, the standard trio, and descriptor hygiene.

## Overview

A file descriptor is a small integer handle a process uses to talk to an open file, socket, or pipe - the kernel translates it to the real object. Every process starts with 0 (stdin), 1 (stdout), 2 (stderr). open/socket/pipe return the lowest free fd; close releases it. This uniformity is the Unix superpower: the same read/write works on files, terminals, sockets, and pipes, which is why redirection and pipelines compose. dup2(old, new) remaps descriptors - the mechanism behind shell redirection (2>&1) and capturing child output. Each fd has flags (O_NONBLOCK for non-blocking I/O, FD_CLOEXEC to close on exec) and points to an open file description holding the offset - which is why two fds from separate opens have independent offsets, while dup'd fds share one. Limits: ulimit -n caps fds per process (servers raise it); leaking fds (sockets never closed) eventually hits 'too many open files'. /proc/<pid>/fd lists a process's descriptors; /dev/stdin etc. are symlinks to them. Hygiene: close what you open (with blocks in Python), set CLOEXEC on descriptors children should not inherit, and monitor fd counts on long-lived services.

## Quick reference

- fd: small int handle -> kernel object. 0/1/2 = stdin/stdout/stderr.

- Same read/write for files, sockets, pipes: the Unix uniformity win.

- dup2 remaps fds: the engine behind 2>&1 and output capture.

- Separate opens = separate offsets; dup'd fds share one offset.

- ulimit -n caps fds; leaks cause 'too many open files'.

- /proc/<pid>/fd lists descriptors. Close what you open; CLOEXEC the rest.


## Worked example

Inspecting and managing descriptors:

```
# What does this process have open?
ls -l /proc/$$/fd

# Raise the fd limit for a server (also set in systemd LimitNOFILE=)
ulimit -n 65536

# Python: with blocks close reliably
with open('in.txt', encoding='utf-8') as f:
    data = f.read()
print('fd', f.fileno(), 'closed:', f.closed)

# Sockets are fds too: leaked ones exhaust the table
import socket
s = socket.create_connection(('example.com', 80), timeout=5)
print('socket fd:', s.fileno())
s.close()
```

- /proc/$$/fd: the shell's own descriptor table, live.

- with blocks close the fd on every exit path - no leaks.

- Every unclosed socket consumes an fd; servers must track them.


## Common mistakes

- Leaking fds on error paths: open without with/try-finally.
  Fix: Always use context managers; audit long-lived services' fd counts.

- Forgetting CLOEXEC: children inherit listening sockets.
  Fix: Set FD_CLOEXEC (Python does by default since 3.4) or close in the child.


## Quick checks

Q: 'Too many open files' - how do I find the leak?
A: ls /proc/<pid>/fd | wc -l for the count; ls -l /proc/<pid>/fd to see what they are (sockets show as socket:[...]). Then find the code path that opens without closing - usually a missing with/close on an error path.


Q: Why do separate opens of one file have independent offsets?
A: The offset lives in the open file description, not the inode. Each open() creates a fresh description; dup() shares one. That is why two readers do not disturb each other's position, but a dup'd pair do.


## Mental model

File descriptors are coat-check tickets: small numbers the attendant (kernel) maps to your actual coat (file/socket). Tickets 0-2 are pre-printed for everyone. dup2 copies a ticket; losing tickets (leaks) fills the check room until no one gets served.
