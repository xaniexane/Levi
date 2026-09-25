---
skill_id: sys_linux_bash_basics
name: Linux Bash Basics
description: The shell fundamentals: commands, quoting, globbing, and history.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux Bash Basics

## Purpose

The shell fundamentals: commands, quoting, globbing, and history.

## Overview

Bash reads a line, expands it, and executes the result. Expansion order matters: brace expansion, tilde, variables, command substitution, globbing, then quote removal. Quoting controls expansion: double quotes allow $variable and $(command) expansion, single quotes allow none - when in doubt, single-quote literals. Globbing patterns (*, ?, [abc]) match filenames; unmatched globs pass through literally by default, a classic surprise. Variables assign with no spaces (x=1, not x = 1) and expand with $x or ${x}; export marks them for child processes. Command substitution $(...) captures output; prefer it over backticks. History (up-arrow, Ctrl-R reverse search, !! last command, !$ last argument) speeds interactive work; HISTCONTROL=ignoredups keeps it clean. Exit statuses drive scripting: 0 means success, anything else failure - test with $? or directly in if. set -euo pipefail makes scripts fail fast on errors, unset variables, and pipeline failures; it is the sane starting template for any non-trivial script. Read man pages with man cmd, and prefer --help for quick reminders.

## Quick reference

- Single quotes: no expansion. Double quotes: $var and $(cmd) expand.

- No spaces around = in assignments. export shares variables with children.

- $(...): command substitution, preferred over backticks.

- Globs (*, ?, [..]) match filenames; unmatched patterns pass through literally.

- Exit status: 0 = success. Test via if cmd or $?.

- set -euo pipefail: fail-fast template for scripts.

- Ctrl-R: reverse history search. !!: last command. !$: last argument.


## Worked example

Quoting, substitution, and a fail-fast script header:

```
#!/usr/bin/env bash
set -euo pipefail

name='ada'
echo "hello $name"      # expands
echo 'hello $name'        # literal

today=$(date +%F)
echo "today is $today"

if grep -q ERROR app.log; then
    echo 'errors found' >&2
    exit 1
fi
```

- set -euo pipefail: exit on error, unset var, or failed pipe stage.

- Single quotes keep $name literal; double quotes expand it.

- grep -q with if uses the exit status directly - no $?.


## Common mistakes

- Unquoted variables: rm -rf $dir with empty dir becomes rm -rf.
  Fix: Quote expansions: "$dir". (Or use arrays for lists.)

- Backticks and $() confusion in nested substitution.
  Fix: $() nests cleanly; backticks do not - always prefer $().


## Quick checks

Q: Why did my variable assignment fail with 'command not found'?
A: Spaces around =: `x = 1` runs `x` as a command. Assignments need `x=1` with no spaces. Use ${x} form when the name abuts other text.


Q: What does set -euo pipefail actually buy me?
A: -e exits on the first failing command, -u errors on unset variables instead of silently emptying, and -o pipefail makes pipelines fail if any stage fails - without it, only the last stage's status counts.


## Mental model

Bash is a sous-chef that preps your line before cooking: it chops (expands variables), measures (globs filenames), and only then fires the pan (runs the command). Quoting is telling the sous-chef 'hands off this ingredient - use it exactly as written'.
