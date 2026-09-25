---
skill_id: sys_git_stash
name: Git stash
description: Parking work in progress: stashing, popping, and partial stashes.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git stash

## Purpose

Parking work in progress: stashing, popping, and partial stashes.

## Overview

stash shelves uncommitted changes so you can switch contexts cleanly - pull updates, fix a hotfix, then restore. git stash push -m 'msg' shelves with a label (always label; the default 'WIP on branch' list becomes unreadable fast). git stash list shows the stack; git stash pop restores and drops the top entry, apply keeps it. Stashes are per-repository, not per-branch - pop onto the branch where the changes belong. git stash -u includes untracked files (default stashes tracked only); -p stashes interactively hunk-by-hunk for partial shelving. Conflicts on pop are normal: resolve like a merge, then drop the stash manually since pop aborts the drop on conflict. Stash is for short parking (hours, a day); anything longer deserves a real branch - stashes have no names that survive context switches and get forgotten. Never stash to 'hide' work from review; commit it on a branch instead. Recovery: dropped stashes are hard to find (reflog sometimes) - pop carefully and prefer apply until you are sure.

## Quick reference

- stash push -m 'msg': shelve with a label. list/pop/apply manage the stack.

- Stashes are per-repo, not per-branch: pop onto the right branch.

- -u includes untracked files. -p stashes hunks interactively.

- Conflicts on pop: resolve, then drop manually (pop aborts the drop).

- Short parking only; longer work belongs on a branch.

- Prefer apply until sure; dropped stashes are hard to recover.


## Worked example

Shelving work for a hotfix:

```
$ git stash push -m 'half-done timeout refactor' -u
$ git switch -c hotfix/crash
# ... fix, commit, merge ...
$ git switch feat/login-timeout
$ git stash pop
$ git stash list
```

- -m labels the stash; -u includes untracked files.

- Pop back onto the branch the work belongs to.

- list confirms the stack is empty afterward.


## Common mistakes

- A dozen unlabeled stashes nobody dares touch.
  Fix: Label every stash; convert old ones to branches or drop them.

- Stashing to hide unfinished work from a review.
  Fix: Commit it on a branch - hidden work is lost work.


## Quick checks

Q: stash pop says 'already exists' / conflicts - now what?
A: Your current tree changed the same lines. Resolve the conflicts like a merge, git add them, then git stash drop the (still present) entry - pop does not drop on conflict.


Q: Should I commit instead of stashing?
A: For anything living past today: yes, commit on a scratch branch. Stash is for quick context switches, not storage - labeled stacks rot.


## Mental model

stash is the coat check at a restaurant: hand over your bulky work-in-progress, get a ticket, handle the interruption hands-free, then reclaim it with the ticket. Lose the ticket (no label) and you are describing your coat to a skeptical attendant.
