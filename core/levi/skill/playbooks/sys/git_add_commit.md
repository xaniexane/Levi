---
skill_id: sys_git_add_commit
name: Git add and commit
description: Building good commits: staging with intent and writing messages that help.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git add and commit

## Purpose

Building good commits: staging with intent and writing messages that help.

## Overview

git add moves changes into the staging area; git commit snapshots the stage into history. Stage with intent: git add -p walks hunks interactively so one commit holds one idea, even when the working tree has several. Review before committing: git diff shows unstaged changes, git diff --cached shows what is staged - the commit should contain exactly what the cached diff shows, nothing more. Commit messages: a short imperative summary line ('Fix login timeout'), a blank line, then the why - what and why, not how (the diff shows how). Small, focused commits beat giant ones: they review cleanly, revert safely, and bisect precisely. git commit --amend fixes the last commit (message or content) but rewrites history - fine on private branches, forbidden on shared ones. Empty commits (-m '') and 'wip' piles are technical debt; squash them before merging. Sign commits (-S) when provenance matters. The discipline: every commit should pass tests and stand alone as a logical unit - future you, bisecting at 2 AM, will be grateful.

## Quick reference

- git add -p: stage hunks interactively - one idea per commit.

- git diff: unstaged. git diff --cached: staged (what the commit holds).

- Message: imperative summary line, blank line, the why.

- Small focused commits: reviewable, revertable, bisectable.

- --amend rewrites history: private branches only.

- Sign (-S) when provenance matters.


## Worked example

Staging with intent and amending:

```
$ git status --short
 M app.py
 M tests.py
$ git add -p app.py        # stage only the login-timeout hunk
$ git diff --cached        # verify: exactly the intended change
$ git commit -m 'Fix login timeout under slow DNS'
$ git commit --amend -m 'Fix login timeout under slow DNS'
$ git log --oneline -3
```

- add -p stages hunk-by-hunk: mixed work splits into clean commits.

- diff --cached is the pre-commit review: read it every time.

- amend on a private branch only - never after pushing shared history.


## Common mistakes

- git commit -a -m 'stuff': giant mystery commits with no review.
  Fix: Stage deliberately, review the cached diff, write a real message.

- Amending pushed shared history, stranding teammates.
  Fix: Rewrite only private history; shared history gets new commits.


## Quick checks

Q: How small should a commit be?
A: One logical change: it should be reviewable in minutes, revertable without collateral, and leave tests passing. If the message needs 'and' twice, split it.


Q: I already pushed - can I still amend?
A: Only if nobody else has based work on it (then force-push and tell them). On shared branches, make a new commit instead - history rewrites strand collaborators.


## Mental model

Staging is packing a shipping box: add -p lets you pick items one by one instead of sweeping the whole room in. The commit message is the customs label - 'misc' gets your package opened and inspected by a grumpy future maintainer.
