---
skill_id: sys_os_virtual_memory
name: OS Virtual Memory
description: How every process gets its own private address space on shared RAM.
risk: info
permissions: []
requires_confirmation: false
tags: [os, memory]
version: 1.0.0
---
# OS Virtual Memory

## Purpose

How every process gets its own private address space on shared RAM.

## Overview

Virtual memory gives each process the illusion of a large private address space; the MMU translates virtual addresses to physical RAM via page tables, in 4 KB pages typically. Translation is cached in the TLB; a miss walks the tables (fast, hardware-assisted). Pages not in RAM fault: the kernel loads them from disk (or allocates zeroed pages) transparently - this demand paging is why programs can exceed physical RAM, spilling to swap at a steep speed cost. Copy-on-write shares pages between processes (fork) until one writes, then copies - making fork cheap. Memory-mapped files (mmap) map file contents into the address space: reads/writes become memory accesses, the kernel handles I/O and caching - the mechanism behind fast file processing and shared libraries. Protection comes free: pages carry rwx bits, so code is executable-but-not-writable (W^X) and null dereferences fault instead of corrupting. Thrashing is the failure mode: working set exceeds RAM, every access faults, throughput collapses - the fix is less memory pressure, not more swap. Tools: /proc/<pid>/maps shows a process's mappings; free/vmstat show system pressure.

## Quick reference

- MMU + page tables translate virtual -> physical per process (4K pages).

- Demand paging: pages load on fault; programs may exceed RAM via swap.

- Copy-on-write: fork shares pages until write - cheap process creation.

- mmap: files as memory; the kernel handles I/O and caching.

- Page rwx bits: W^X code, faulting null derefs - protection is structural.

- Thrashing: working set > RAM collapses throughput; reduce pressure.


## Worked example

Inspecting a process's virtual memory:

```
# A process's mappings: addresses, perms, what backs them
cat /proc/self/maps | head -12

# System-wide pressure
vmstat 1 3
free -h

# Python: mmap a file instead of reading it
import mmap
with open('/etc/hostname', 'r+b') as f:
    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        print(m.readline())
```

- /proc/self/maps: text, heap, stacks, and mapped libraries per process.

- vmstat si/so columns reveal swap activity (thrashing signal).

- mmap lets the kernel page the file in on demand - no read() loop.


## Common mistakes

- Treating swap as 'extra RAM': it is emergency spillover, 1000x slower.
  Fix: Size RAM for the working set; fix leaks instead of adding swap.

- Ignoring OOM kills: 'the process just died'.
  Fix: dmesg + memory graphs first; the kernel tells you what it did.


## Quick checks

Q: If memory is virtual, what does 'out of memory' even mean?
A: The kernel refused to back more pages: RAM + swap exhausted, or a per-process limit (ulimit, cgroup) hit. The OOM killer then sacrifices processes to reclaim pages - check dmesg.


Q: Why is mmap faster than read() for some workloads?
A: No user/kernel buffer copies and no read syscalls per chunk - page faults pull data straight into the mapping, and the kernel's page cache is shared. Best for random access over large files.


## Mental model

Virtual memory is giving every tenant their own numbered parking garage (address space) while the building has one real lot (RAM): the valet (MMU) maps your spot number to a real space, double-parks rarely-used cars in the overflow lot (swap), and photocopies shared flyers instead of printing per tenant (copy-on-write).
