---
skill_id: sys_linux_pipes_redirection
name: Linux Pipes and Redirection
description: Composing commands: pipes, redirection, and the standard streams.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux Pipes and Redirection

## Purpose

Composing commands: pipes, redirection, and the standard streams.

## Overview

Every process starts with three streams: stdin (0) for input, stdout (1) for output, stderr (2) for errors. Redirection repoints them: > truncates a file and writes stdout, >> appends, < feeds a file to stdin, 2> captures errors, 2>&1 merges stderr into stdout, &> grabs both. The pipe | connects stdout of one command to stdin of the next, building pipelines where each stage transforms a stream - the core Unix philosophy of small composable tools. Order matters: cmd >file 2>&1 merges correctly, while 2>&1 >file sends stderr to the old stdout (the terminal). xargs converts stdin lines into command arguments for tools that do not read stdin. tee splits a stream to both a file and onward. Process substitution <(cmd) presents a command's output as a filename for tools that demand file arguments (diff <(a) <(b)). Heredocs (<<EOF) feed multi-line literal input. Defensive habits: never > a file you are reading in the same pipeline (the truncation happens first, emptying it), quote redirections' filenames, and remember pipes create subprocesses - variables set inside a pipeline stage do not survive it in bash without lastpipe/shopt.

## Quick reference

- > truncates, >> appends, < feeds stdin, 2> captures stderr.

- 2>&1 merges stderr into stdout; order matters: cmd >f 2>&1.

- | pipes stdout to the next stdin: the composable core of Unix.

- tee: split stream to file + onward. xargs: stdin lines -> arguments.

- <(cmd): process substitution - output presented as a filename.

- Never > a file you are reading in the same command: truncation first.


## Worked example

Pipeline patterns and safe redirection:

```
# Top 5 error lines, counted:
grep ERROR app.log | cut -d' ' -f1 | sort | uniq -c | sort -rn | head -5

# Merge stderr into stdout, log everything, still see it:
./build.sh > build.log 2>&1

# Compare outputs of two commands without temp files:
diff <(sort a.txt) <(sort b.txt)

# Feed a list of files to a tool as arguments:
find . -name '*.tmp' -print0 | xargs -0 rm
```

- Each pipe stage transforms the stream; sort|uniq -c|sort -rn ranks.

- >file 2>&1 order: stdout to file first, then stderr merged into it.

- -print0 | xargs -0 handles filenames with spaces and newlines safely.


## Common mistakes

- cat file | grep x > file: truncation empties the input first.
  Fix: Write to a temp file, then move it over, or use sponge.

- Forgetting 2>&1 and wondering where the errors went.
  Fix: Errors live on stderr; merge or redirect it explicitly.


## Quick checks

Q: Why is my log file empty after `cmd 2>&1 >file`?
A: Redirections apply left to right: 2>&1 first duplicates stderr to the current stdout (terminal), then >file moves only stdout. Use cmd >file 2>&1 to merge into the file.


Q: Variables set inside a pipeline disappear - why?
A: Pipeline stages run in subshells; their variable assignments die with the subshell. Restructure with process substitution or shopt -s lastpipe.


## Mental model

Streams are three conveyor belts leaving every program: finished goods (stdout), scrap reports (stderr), and an intake belt (stdin). Pipes bolt the goods belt of one machine to the intake of the next; redirection parks a belt's end at a loading dock (a file).
