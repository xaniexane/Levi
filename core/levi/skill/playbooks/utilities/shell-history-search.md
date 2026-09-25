---
skill_id: utility.shell_history_search
name: Shell History Search
description: Search your shell history for past commands matching a pattern - read-only.
risk: info
permissions: []
requires_confirmation: false
tags: [shell, history, search]
version: 1.0.0
---

# Shell History Search

Shell History Search looks through your shell's history file for commands matching a substring or regex and displays them with line numbers. It never executes anything it finds.

## When to use

- Recovering a long command you ran last week.
- Finding how you invoked a tool before.
- Auditing what ran on a machine recently.

## Steps

1. Locate the history file (HISTFILE env, ~/.bash_history for bash, ~/.zsh_history for zsh).
2. Search lines by substring or compiled regex; display matches with line numbers.
3. Never execute a match - display only; re-running is your call.
4. Note the history file's size and rotation so missing entries are explained.

## Honest limits

- Read-only: it searches, it never runs.
- History files are incomplete by nature (session buffering, HISTCONTROL) - absence of a command proves nothing.
- zsh history uses timestamped extended format; the skill handles both layouts.

Original work authored for LEVI - utilities pack.
