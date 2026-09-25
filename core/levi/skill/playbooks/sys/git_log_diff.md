---
skill_id: sys_git_log_diff
name: Git log and diff
description: Reading history: log formats, diff scopes, and blame.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git log and diff

## Purpose

Reading history: log formats, diff scopes, and blame.

## Overview

git log lists commits; --oneline compresses to one line each, --graph --all --decorate draws the branch topology, -p shows patches, --stat summarizes files, --since/--until filter by date, --grep searches messages, -S 'text' finds commits that added/removed a string (pickaxe - the code archaeologist's best friend). Limit with -n. git diff with no args: unstaged working-tree changes; --cached: staged; HEAD: everything since the commit; commitA..commitB: the range; --stat for the summary view. git show <commit> displays one commit fully. git blame -L 10,20 file attributes lines to their commits - use it to understand, never to shame; the person may have had good reasons. Diff output reads: ---/+++ headers, @@ hunks, - removed, + added. Word-diff (--word-diff) helps prose. Habits: log before you merge (know what is landing), diff --cached before every commit (know what you are signing), and blame to find the commit message that explains the weird line - good messages pay compound interest here.

## Quick reference

- log --oneline --graph --all --decorate: the topology view.

- -S 'text' (pickaxe): find commits that added/removed a string.

- diff: unstaged. --cached: staged. HEAD: all since commit. A..B: range.

- show <commit>: one commit fully. blame -L: attribute lines to commits.

- Read diffs: ---/+++ headers, @@ hunks, -/+ lines.

- log before merging; diff --cached before committing.


## Worked example

Archaeology: who changed what and when:

```
$ git log --oneline --graph --all --decorate -12
$ git log -S 'MAX_RETRIES' --oneline -- app.py
$ git diff --stat main...feat/login-timeout
$ git show 9f3a2c1 --stat
$ git blame -L 40,55 app.py
```

- -S pickaxe: which commits touched the string MAX_RETRIES.

- main...feat (three dots): changes unique to the feature branch.

- blame -L narrows attribution to the suspicious lines.


## Common mistakes

- Reading raw git log on a busy repo: an unreadable wall.
  Fix: --oneline --graph --decorate -n keeps it navigable.

- Using blame to assign fault in reviews.
  Fix: Blame explains; the commit message is the context. Ask, don't accuse.


## Quick checks

Q: Two dots vs three dots in diff/log ranges?
A: A..B: commits reachable from B but not A (B's unique history). A...B (symmetric): commits unique to either side since their merge base - what a merge would bring in. For 'what does my branch add', use three dots.


Q: blame points at me for a line I barely touched - fair?
A: blame shows the last commit touching the line, which may be a reformat or move. Follow with log -L or show to see the real change; whitespace-only commits mislead.


## Mental model

log is the library catalog, diff is laying two manuscript drafts side by side with changes highlighted, pickaxe (-S) is asking the librarian 'which edition first contained this sentence', and blame is the margin note saying who penciled each line - for understanding, not for detention slips.
