---
skill_id: sys_python_subprocess
name: Python subprocess
description: Running external commands safely: run, pipes, timeouts, and shell-injection defense.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python subprocess

## Purpose

Running external commands safely: run, pipes, timeouts, and shell-injection defense.

## Overview

subprocess.run is the modern way to execute external programs. Pass the command as a list - ['ls', '-l', path] - and no shell interprets it, which eliminates shell injection: a malicious filename cannot smuggle extra commands. capture_output=True (or stdout=PIPE) grabs output; text=True decodes to str; check=True raises CalledProcessError on nonzero exit so failures cannot slip by silently; timeout= bounds hanging commands. The result object carries .returncode, .stdout, .stderr. For pipelines, chain processes by feeding one's stdout to the next's stdin, or use input= for short feeds. subprocess.Popen gives full control for long-running or interactive children, but always communicate() or wait() to reap them - unreaped children become zombies. shell=True is the escape hatch for real shell features (globbing, pipes in one string); when you must use it, never interpolate untrusted data - shlex.quote() each piece or, better, restructure to avoid the shell. Security posture: argument lists by default, absolute executable paths in security-sensitive code, timeouts on everything, and validate outputs before acting on them.

## Quick reference

- subprocess.run(['cmd', 'arg'], ...): list form avoids the shell.

- capture_output=True, text=True, check=True, timeout=N: the safe quartet.

- Result: .returncode, .stdout, .stderr. check=True raises on failure.

- Popen for long-running children; always communicate()/wait() to reap them.

- shell=True only when shell features are truly needed; shlex.quote() untrusted parts.

- Absolute executable paths + timeouts in security-sensitive code.


## Worked example

Safe command execution with timeout and checks:

```
import subprocess

def disk_free(path='/'):
    r = subprocess.run(
        ['df', '-h', path],
        capture_output=True, text=True,
        check=True, timeout=10,
    )
    return r.stdout

try:
    print(disk_free())
except subprocess.CalledProcessError as e:
    print('df failed:', e.returncode)
except subprocess.TimeoutExpired:
    print('df hung')
```

- List form: path cannot inject extra shell commands.

- check=True converts silent failure into an exception.

- timeout=10 bounds the worst case; TimeoutExpired is catchable.


## Common mistakes

- Interpolating user input into a shell=True string: classic injection.
  Fix: Use the list form; the shell never sees the arguments.

- Forgetting check=True and acting on garbage from a failed command.
  Fix: check=True or inspect returncode explicitly before trusting output.


## Quick checks

Q: When is shell=True actually justified?
A: When you genuinely need shell syntax - glob expansion, a pipeline expressed as one string, redirection operators. Even then, keep untrusted data out via shlex.quote, or build the pipeline from multiple Popen stages.


Q: My child process hangs forever - what did I miss?
A: Usually a missing timeout, or a PIPE buffer filling because you never read stdout/stderr. Use communicate() (which drains both) and always set a timeout.


## Mental model

subprocess.run with a list is handing the bouncer a guest list of exact names; shell=True is shouting instructions across a noisy room where anyone can interject. The guest list cannot be talked into admitting extra people; the shouted version can.
