---
skill_id: sys_git_reset_revert
name: Git reset and revert
description: Undoing changes: the safe way (revert) and the sharp way (reset).
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git reset and revert

## Purpose

Undoing changes: the safe way (revert) and the sharp way (reset).

## Overview

Two tools, opposite safety profiles. git revert creates a NEW commit that undoes an old one - history stays honest and shared branches stay safe. It is the default undo for anything pushed. git reset moves the branch pointer backward, with three flavors: --soft keeps changes staged, --mixed (default) unstages them into the working tree, --hard discards everything - working tree included. --hard is the chainsaw: uncommitted work vanishes permanently, so verify status first and prefer it only on private branches. Reset rewrites history: fine privately, forbidden once pushed and shared. Related rescues: git checkout -- file / git restore file discards working-tree changes to one file; git restore --staged un-stages. The reflog (git reflog) records every HEAD movement for ~90 days - the safety net under every rewrite: find the lost commit's hash and reset --hard back to it. Decision tree: pushed/shared? revert. Private and unpushed? reset freely. Uncommitted mess? restore the file. Lost something? reflog first, panic never.

## Quick reference

- revert: new commit undoing an old one - safe for shared history.

- reset --soft/--mixed/--hard: staged / unstaged / discarded. --hard destroys.

- reset rewrites history: private branches only.

- restore file / restore --staged: discard worktree change / unstage.

- reflog: every HEAD move for ~90 days - the undo for undos.

- Decision: shared -> revert. Private -> reset. Uncommitted -> restore.


## Worked example

Undoing at each level:

```
# Undo a pushed commit safely:
$ git revert 9f3a2c1

# Private branch: drop the last two commits, keep the work unstaged:
$ git reset --mixed HEAD~2

# Discard one file's uncommitted changes:
$ git restore -- app.py

# Rescued from the reflog:
$ git reflog
$ git reset --hard 3b9aa10
```

- revert is a normal commit: pushable, reviewable, safe.

- --mixed HEAD~2: pointer back two, changes survive in the worktree.

- reflog finds commits orphaned by resets and rebases.


## Common mistakes

- reset --hard on the wrong branch: work destroyed.
  Fix: git status first, every time; --hard is forever.

- Reverting instead of fixing forward when the revert conflicts badly.
  Fix: If the revert is messier than a follow-up fix, do the fix.


## Quick checks

Q: I reset --hard and lost work - is it gone?
A: Probably not: git reflog lists recent HEAD positions including the pre-reset one. Copy the hash and reset --hard back to it. Act before the ~90-day expiry and before gc prunes.


Q: revert vs reset - one-line rule?
A: Shared or pushed history: revert (adds a commit). Private, unpushed history: reset (moves the pointer). When unsure, revert - it is always safe.


## Mental model

revert is publishing a correction in the newspaper: the original article stays, the correction is new and dated. reset is ripping pages out of your private diary. The reflog is the diary's recycle bin - ripped pages sit there for 90 days before the bin is emptied.
