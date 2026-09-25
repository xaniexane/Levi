---
skill_id: sys_linux_environment_variables
name: Linux Environment Variables
description: Configuration via the environment: reading, setting, and scoping correctly.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux Environment Variables

## Purpose

Configuration via the environment: reading, setting, and scoping correctly.

## Overview

Environment variables are process-scoped key/value strings inherited by children. export VAR=value marks a shell variable for export to children; without export it stays shell-local. Login shells read /etc/profile and ~/.profile (or ~/.bash_profile); interactive non-login shells read ~/.bashrc - put PATH tweaks and aliases in bashrc, one-time session setup in profile. PATH is the command search list, colon-separated, searched left to right; '.' in PATH is a security risk (a trojan ls in a writable dir). Inspect with printenv or echo $VAR; env VAR=val cmd sets a variable for one command without polluting the shell. Twelve-factor apps take config from the environment: no secrets in code or repos, different values per deploy. But env has limits: values are strings, visible in /proc/<pid>/environ to the same user and inherited by every child (leak surface), and shells happily export typos. Validate at startup (fail fast on missing/invalid), prefer explicit config files for complex structure, and never log env wholesale in production - it contains the secrets.

## Quick reference

- export VAR=value: share with children. Without export: shell-local.

- ~/.bashrc: interactive shells. ~/.profile: login shells. Know which runs.

- PATH searched left to right; never put '.' in PATH.

- env VAR=val cmd: one-command override without polluting the shell.

- Config from env: no secrets in code. Validate at startup, fail fast.

- Env values are strings, visible via /proc, inherited by children - handle carefully.


## Worked example

Reading, scoping, and validating config:

```
# ~/.bashrc: interactive tweaks
export PATH="$HOME/.local/bin:$PATH"
export EDITOR=vim

# One-command override:
env DEBUG=1 ./run_tests.sh

# Python: fail fast on bad config
import os
def get_config():
    try:
        port = int(os.environ.get('APP_PORT', '8080'))
    except ValueError:
        raise SystemExit('APP_PORT must be an integer')
    return port
```

- Prepending to PATH keeps your tools first without dropping system dirs.

- env VAR=val scopes the variable to that single command.

- Fail fast on invalid config: crash at startup, not at 3 AM.


## Common mistakes

- Secrets committed in .env files pushed to git.
  Fix: gitignore .env; inject secrets at deploy time from a manager.

- export in a script expecting the parent shell to see it.
  Fix: Children cannot change the parent's environment - source the file instead.


## Quick checks

Q: I set a variable but my script cannot see it - why?
A: You set a shell variable without export, or set it in a file the target shell never reads (bashrc vs profile confusion). export it, and verify with printenv in the same context the script runs.


Q: Are environment variables safe for secrets?
A: Safer than code, not safe absolutely: visible in /proc to same-user processes, inherited by children, easy to leak via logs or error pages. Prefer a secrets manager for high-value secrets; env for the rest.


## Mental model

Environment variables are the air a process breathes: inherited from its parent, invisible but everywhere, and every child breathes the same air. export opens the window; without it the room stays sealed. Secrets in the air can be smelled by anyone in the building - ventilate carefully.
