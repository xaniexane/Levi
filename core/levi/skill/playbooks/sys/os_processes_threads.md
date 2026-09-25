---
skill_id: sys_os_processes_threads
name: OS Processes vs Threads
description: The execution model: address spaces, threads, and what the kernel schedules.
risk: info
permissions: []
requires_confirmation: false
tags: [os, concurrency]
version: 1.0.0
---
# OS Processes vs Threads

## Purpose

The execution model: address spaces, threads, and what the kernel schedules.

## Overview

A process is a program in execution: its own virtual address space, file descriptors, and at least one thread. Processes are isolated - one cannot touch another's memory - which makes them robust but expensive to create and communicate between (pipes, sockets, shared memory). A thread is a schedulable execution stream inside a process: threads share the address space, file descriptors, and most state, differing only in stack, registers, and thread-local storage. Sharing makes threads cheap and communication trivial - and data races possible, hence locks. The kernel schedules threads (on Linux, tasks), preempting them onto CPU cores; a process with N threads can truly run on N cores at once. Context switches between threads of one process are cheaper than between processes (no address-space switch). Fork creates a process by duplicating the parent (copy-on-write makes it cheap); exec replaces the process image - the classic fork/exec pair behind every command you run. Choose processes for isolation and true parallelism of CPU work; threads for shared-memory concurrency and I/O overlap. Green threads/coroutines (asyncio, goroutines) multiplex many logical tasks onto few kernel threads for massive I/O fan-out.

## Quick reference

- Process: own address space + resources. Isolated, heavier.

- Thread: execution stream sharing the process's memory. Cheap, needs sync.

- Kernel schedules threads; N threads can run on N cores.

- fork duplicates (copy-on-write); exec replaces the image.

- Processes: isolation + CPU parallelism. Threads: shared memory + I/O overlap.

- Coroutines: many logical tasks on few kernel threads for I/O fan-out.


## Worked example

Seeing processes and threads on Linux:

```
# Process tree:
ps -ef --forest | head -20

# Threads of a process (LWP = light-weight process = thread):
ps -T -p <pid> -o pid,lwp,nlwp,cmd

# Who is eating CPU right now, per thread:
top -H -p <pid>

# Python: threads share memory (see the GIL caveat)
import threading
print(threading.active_count(), 'threads in this process')
```

- ps -T exposes threads as LWPs under their process.

- top -H breaks CPU usage down per thread.

- Threads share the process: one address space, many stacks.


## Common mistakes

- Assuming threads parallelize CPU-bound work everywhere (GIL, or oversubscription).
  Fix: Match the tool to the bottleneck: I/O -> threads, CPU -> processes.

- Sharing mutable state across threads without synchronization.
  Fix: Locks, queues, or immutable handoff - pick one deliberately.


## Quick checks

Q: Why do threads need locks but processes (mostly) not?
A: Threads share memory: two threads can read-modify-write the same variable concurrently, interleaving into garbage. Processes have separate memories, so the sharing - and the race - does not exist by default.


Q: fork vs thread creation - what is actually cheaper and why?
A: Threads: allocate a stack and scheduler entry, sharing everything else. fork: duplicate page tables and process state (copy-on-write defers the memory copy). Threads win on setup; processes win on isolation.


## Mental model

A process is an office: private rooms (memory), its own phone lines (file descriptors). Threads are coworkers in one open-plan office sharing the whiteboard - fast collaboration, but two people erasing the same spot needs a rule (locks). fork is photocopying the whole office; hiring (thread) just adds a desk.
