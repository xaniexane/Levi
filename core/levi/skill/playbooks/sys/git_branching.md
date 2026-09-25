---
skill_id: sys_git_branching
name: Git branching
description: Branches as cheap pointers: creating, switching, and deleting with confidence.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git branching

## Purpose

Branches as cheap pointers: creating, switching, and deleting with confidence.

## Overview

A branch is a lightweight pointer to a commit - creating one costs almost nothing, which is why branching is the core workflow unit. git branch name creates, git switch name moves HEAD (checkout is the legacy spelling), git switch -c name creates and switches in one step. Branches isolate work: feature branches keep main releasable, and short lifespans keep merges painless. Merge a branch with git merge, then delete it (git branch -d) - merged branches are clutter, and -d refuses if unmerged as a safety net (-D forces). Track remote branches with --set-upstream-to or push -u once. Name branches for their purpose (feat/login-timeout, fix/oom-crash), not their author. Long-lived branches drift: rebase or merge main in regularly to keep conflicts small and fresh. Stale branches lie about what is done - prune merged ones and delete abandoned experiments deliberately. Detached HEAD (HEAD pointing at a commit, not a branch) is for inspection; commit there and the work floats - create a branch first if you will keep it.

## Quick reference

- Branch = cheap pointer to a commit. switch -c: create + switch.

- Short-lived feature branches keep main releasable and merges painless.

- Merge, then branch -d (safe delete; -D forces).

- Name for purpose: feat/..., fix/... - not for author.

- Rebase/merge main regularly into long branches to keep conflicts small.

- Detached HEAD is for looking; branch before keeping work.


## Worked example

Feature branch lifecycle:

```
$ git switch -c feat/login-timeout
# ... work, commit ...
$ git switch main
$ git merge feat/login-timeout
$ git branch -d feat/login-timeout
$ git branch --merged | grep -v '^\*' | head   # find merged clutter
$ git push origin --delete old-experiment       # drop remote too
```

- switch -c creates and checks out in one step.

- -d refuses unmerged branches: a safety net against losing work.

- Delete the remote branch too, or clutter accumulates server-side.


## Common mistakes

- Working on main directly for a multi-day feature.
  Fix: Branch per change; main stays releasable and reviewable.

- Committing in detached HEAD and losing track of the work.
  Fix: Create a branch the moment the work matters.


## Quick checks

Q: Why did my commits 'disappear' after switching branches?
A: They did not - they are on the other branch's pointer. git reflog and git branch --contains <sha> find them. Branches are just labels; switching moves the label you stand on.


Q: How long should a branch live?
A: Days, not weeks. The longer it lives, the more main drifts and the nastier the merge. Small branches, merged fast, deleted after.


## Mental model

Branches are sticky notes on a timeline: main marks the official history, feature notes mark experiments. Merging moves the official marker forward to include the experiment; deleting the note afterward keeps the board readable.
