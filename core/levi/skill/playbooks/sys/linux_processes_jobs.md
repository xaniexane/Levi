---
skill_id: sys_linux_processes_jobs
name: Linux Processes and Jobs
description: PIDs, signals, job control, and keeping processes where you want them.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, os]
version: 1.0.0
---
# Linux Processes and Jobs

## Purpose

PIDs, signals, job control, and keeping processes where you want them.

## Overview

A process is a running program with a PID, a parent (PPID), a state, and resource usage. ps aux lists them; top/htop watches live; pgrep finds by name. Signals are the control channel: TERM (15) asks politely to exit, KILL (9) forces it without cleanup, HUP (1) historically 'hang up' - daemons often reload config on it, INT (2) is Ctrl-C. kill sends signals (despite the name); kill -9 is the last resort because the target cannot flush buffers or release locks - always try TERM first. Job control manages the shell's own processes: cmd & backgrounds, Ctrl-Z suspends, bg/fg resume, jobs lists them. A background job dies with the shell unless protected: nohup or disown detaches it, tmux/screen keeps a whole session alive across logouts. nice/renice adjust CPU priority (higher nice = less CPU). Zombie processes (Z state) are dead children whose parent has not reaped their exit status - harmless unless they accumulate, in which case fix the parent. OOM killer sacrifices processes when memory exhausts; check dmesg when something dies mysteriously. For services, prefer systemd units over bare nohup - they restart, log, and order correctly.

## Quick reference

- ps aux / pgrep: list/find. top/htop: live view.

- Signals: TERM(15) polite, KILL(9) force, HUP(1) reload, INT(2) Ctrl-C.

- kill -9 is last resort: no cleanup runs. Try TERM first.

- &, Ctrl-Z, bg, fg, jobs: shell job control.

- nohup/disown/tmux: survive shell exit. systemd: for real services.

- Zombies: unreaped children; fix the parent, not the zombie.


## Worked example

Inspecting, signaling, and detaching:

```
# Find and politely stop:
pgrep -af 'myapp'
kill 1234            # SIGTERM first
sleep 2; kill -9 1234  # SIGKILL only if it ignored TERM

# Run detached, surviving logout:
nohup ./worker --queue jobs > worker.log 2>&1 &
disown

# Or keep a session:
# tmux new -s work   (detach with Ctrl-b d, reattach: tmux attach -t work)
```

- pgrep -af shows full command lines for identification.

- TERM before KILL: lets the process flush and release locks.

- nohup + redirect + & + disown: the classic detach recipe.


## Common mistakes

- kill -9 as the first resort, corrupting half-written state.
  Fix: TERM, wait, verify, then KILL only if needed.

- Starting a 'permanent' service with & and losing it on logout.
  Fix: Use systemd for services; tmux/nohup for interactive leftovers.


## Quick checks

Q: kill -9 didn't work - is the process immortal?
A: It is likely in uninterruptible sleep (D state), stuck in a kernel I/O wait - KILL cannot touch those until the I/O resolves. Check the STAT column; D-state usually means sick storage, not a stuck program.


Q: nohup vs tmux vs systemd - which for my service?
A: nohup: quick one-off. tmux: interactive session you reattach to. systemd: anything that must survive reboots, restart on failure, and log properly - i.e., every real service.


## Mental model

Signals are notes slipped to a running program: TERM says 'please finish up and close', KILL is the fire alarm that evacuates with no packing. Job control is juggling: & tosses a ball to keep spinning behind you, fg brings it back to your hands.
