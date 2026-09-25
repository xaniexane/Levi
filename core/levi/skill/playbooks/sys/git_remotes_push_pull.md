---
skill_id: sys_git_remotes_push_pull
name: Git remotes, push, and pull
description: Sharing work: remotes, pushing, pulling, and fetch-first habits.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git remotes, push, and pull

## Purpose

Sharing work: remotes, pushing, pulling, and fetch-first habits.

## Overview

A remote is a named URL for another copy of the repo; clone sets up origin automatically. git remote -v lists them; git remote add name url adds one (upstream for the source you forked from). git fetch downloads remote history without touching your work - the safe update; git pull is fetch + merge (or rebase with --rebase). Fetch first, inspect (git log origin/main..main), then integrate: surprises are cheaper to see than to untangle. git push sends your commits; -u sets the upstream so later pushes need no arguments. Pushes can be rejected (non-fast-forward): someone else pushed first - pull/rebase, then push again. --force-with-lease overwrites only if the remote is as you last saw it, the safe rewrite for private branches; bare --force risks clobbering others' work. Remote-tracking branches (origin/main) are read-only snapshots of the remote's state - you never commit to them directly. Prune stale ones with git fetch --prune. Protocol note: SSH remotes authenticate with keys (no password prompts in scripts); HTTPS uses credential helpers.

## Quick reference

- Remote = named URL. origin: default. upstream: the forked source.

- fetch: safe download, touches nothing. pull = fetch + merge/rebase.

- Fetch first, inspect, then integrate.

- push -u: set upstream once. Non-fast-forward reject: pull/rebase, retry.

- --force-with-lease: safe rewrite; bare --force risks clobbering others.

- git fetch --prune: drop stale remote-tracking branches.


## Worked example

The fetch-first collaboration loop:

```
$ git remote -v
origin  git@github.com:me/app.git (fetch)
$ git fetch origin
$ git log --oneline origin/main..main   # what do I have that they lack?
$ git log --oneline main..origin/main   # what did they add?
$ git rebase origin/main
$ git push
```

- remote -v shows fetch and push URLs.

- The .. ranges show each side's unique commits before integrating.

- Rebase-then-push keeps the shared history linear and honest.


## Common mistakes

- git pull with local uncommitted changes conflicting: messy merges.
  Fix: Commit or stash first; pull onto a clean tree.

- --force on shared branches, rewriting teammates' history.
  Fix: --force-with-lease on private branches only; shared history is append-only.


## Quick checks

Q: My push was rejected - what is the right move?
A: Someone pushed first. fetch, look at their commits, rebase or merge your work onto them, test, then push. Never --force a shared branch to 'win'.


Q: fetch vs pull - why have both?
A: fetch only downloads; your branches do not move until you integrate. pull combines download + integrate in one step - convenient, but it hides the inspection step where surprises are cheapest.


## Mental model

Remotes are pen pals with your repo: fetch reads their latest letter without touching your desk, pull reads it and rearranges your desk to match, push mails your pages. Reading before rearranging (fetch first) means you never shelve a letter that contradicts your draft unseen.
