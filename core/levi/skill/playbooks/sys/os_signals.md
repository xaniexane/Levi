---
skill_id: sys_os_signals
name: OS Signals
description: The kernel's notification system: what signals mean and how programs handle them.
risk: info
permissions: []
requires_confirmation: false
tags: [os, linux]
version: 1.0.0
---
# OS Signals

## Purpose

The kernel's notification system: what signals mean and how programs handle them.

## Overview

Signals are asynchronous notifications from the kernel (or another process) to a process: a number with a conventional meaning and a default action (terminate, core dump, stop, continue, ignore). The essentials: HUP (1) - terminal hung up; daemons reload config. INT (2) - Ctrl-C interrupt. QUIT (3) - quit with core dump. KILL (9) - forced terminate, cannot be caught. TERM (15) - polite termination request, the default kill. STOP (19)/CONT (18) - suspend/resume, uncatchable like KILL. USR1/USR2 (10/12) - application-defined. CHILD (17) - a child changed state; parents reap via wait(). Programs install handlers for catchable signals (signal.signal in Python) to flush state and exit cleanly on TERM/INT - but handlers run asynchronously, so they must be tiny and reentrant: set a flag, return; do real work in the main loop. KILL and STOP cannot be caught, blocked, or ignored - the kernel guarantees a way to stop anything (except D-state sleep). Masks (sigprocmask) defer delivery around critical sections. kill -l lists all signals; kill -SIGNAL pid sends one. Design rule: TERM means 'shut down gracefully now', and services should honor it within seconds - orchestrators escalate to KILL after a grace period.

## Quick reference

- Signals: async kernel notifications; number + meaning + default action.

- TERM(15) polite, KILL(9) forced+uncatchable, INT(2) Ctrl-C, HUP(1) reload.

- STOP(19)/CONT(18): suspend/resume, uncatchable.

- Handlers must be tiny: set a flag, do work in the main loop.

- CHILD(17): child state change - parents must reap with wait().

- Services: honor TERM within seconds; orchestrators escalate to KILL.


## Worked example

Graceful shutdown on SIGTERM in Python:

```
import signal, time

shutdown = False

def handle_term(signum, frame):
    global shutdown
    shutdown = True          # handler only sets the flag

signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGINT, handle_term)

print('worker running; send SIGTERM to stop')
while not shutdown:
    time.sleep(0.5)          # real work happens here
print('flushing state and exiting cleanly')
```

- The handler sets a flag; the loop does the graceful teardown.

- Catching both TERM and INT covers kill and Ctrl-C uniformly.

- No I/O or locks in the handler: async-signal safety.


## Common mistakes

- Doing real work (I/O, locks) inside a signal handler.
  Fix: Set a flag; let the main loop do the work. Handlers are async.

- kill -9 as routine restarts: state corruption, unflushed buffers.
  Fix: TERM, wait for clean exit, KILL only the stubborn.


## Quick checks

Q: Why can't anything catch SIGKILL?
A: By design: the kernel needs an unstoppable last resort. If programs could block KILL, a wedged process could never be terminated. D-state (uninterruptible I/O sleep) is the one exception - even KILL waits there.


Q: My daemon ignores TERM and gets KILLed after 30s - fix?
A: Install a TERM handler that stops accepting work, finishes in-flight tasks, flushes state, and exits - well within the orchestrator's grace period. Log the shutdown path.


## Mental model

Signals are taps on the shoulder from the kernel: TERM is 'excuse me, time to leave' (you pack up), INT is someone yanking your sleeve (Ctrl-C), KILL is security escorting you out mid-sentence. A good program packs its bag when asked instead of waiting for security.
