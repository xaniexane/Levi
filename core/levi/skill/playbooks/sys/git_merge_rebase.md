---
skill_id: sys_git_merge_rebase
name: Git merge vs rebase
description: Two ways to combine history: when to merge, when to rebase, and the golden rule.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git merge vs rebase

## Purpose

Two ways to combine history: when to merge, when to rebase, and the golden rule.

## Overview

merge joins two histories with a merge commit: it preserves the true chronology, including the fact that work happened in parallel. rebase replays your commits onto a new base, producing a linear history that reads like the work happened sequentially. Rule: rebase private branches to keep them clean and current; merge to integrate, especially into shared branches where history must stay honest. Never rebase commits others have based work on - it rewrites their history out from under them (the golden rule). git pull is fetch + merge by default; git pull --rebase replays your local commits onto the fetched tip, avoiding noisy merge commits on routine syncs. Conflicts are normal: git status shows both sides, edit the markers, git add the resolved files, then git rebase --continue or git commit. Abort cleanly with --abort when the rebase goes sideways. Interactive rebase (-i) rewrites private history deliberately: squash fixups, reword messages, reorder - the tool for turning 'wip' piles into a reviewable series before merging.

## Quick reference

- merge: joins histories, preserves truth. rebase: replays linearly, reads clean.

- Rebase private branches; merge into shared ones. Never rebase public history.

- git pull --rebase: replay local commits on sync, skip noise merges.

- Conflicts: edit markers, git add, --continue. --abort bails out cleanly.

- rebase -i: squash/reword/reorder private history before review.


## Worked example

Rebasing a feature branch onto fresh main:

```
$ git switch feat/login-timeout
$ git fetch origin
$ git rebase origin/main
# ... resolve any conflicts, git add, git rebase --continue ...
$ git push --force-with-lease   # private branch: safe rewrite
$ git switch main
$ git merge --no-ff feat/login-timeout
```

- fetch + rebase: replay your work onto the latest main.

- --force-with-lease refuses if someone else pushed: safer than --force.

- --no-ff keeps a merge commit marking the feature boundary.


## Common mistakes

- Rebasing main or any shared branch: rewrites everyone's history.
  Fix: The golden rule: rebase private, merge public.

- git push --force on shared branches after a rebase.
  Fix: --force-with-lease at most, and only on your own private branches.


## Quick checks

Q: Merge or rebase for my feature branch?
A: Rebase while it is private to keep it current and linear; merge (often --no-ff) when landing it so the integration point stays visible. Teams standardize one flow - follow the repo's convention.


Q: Rebase hit conflicts in every commit - what now?
A: git rebase --abort to bail safely, then consider merge instead for this branch. Per-commit conflicts mean the branch diverged a lot; merging once may be kinder than replaying.


## Mental model

merge is weaving two ropes into one with a visible knot (the merge commit); rebase is untying your rope and re-tying it onto the end of the other so it looks like one continuous strand. Re-tying someone else's rope while they hold it is why rebasing public history is forbidden.
