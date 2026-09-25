---
skill_id: sys_git_init_clone
name: Git init and clone
description: Starting repositories and copying them: the first two commands.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git init and clone

## Purpose

Starting repositories and copying them: the first two commands.

## Overview

git init creates a repository in the current directory (a .git folder holding all history); git init -b main sets the initial branch name explicitly instead of inheriting the template default. git clone URL copies a remote repository locally with full history and sets up origin as the default remote. Clone depth (--depth 1) makes shallow copies for CI where history is unneeded. After init, set identity once per machine: git config --global user.name/email - commits without identity are misattributed. The three areas to internalize early: working tree (your files), staging area/index (what goes into the next commit), and HEAD (the current commit). git status shows all three at a glance - run it constantly until it becomes reflex. A .gitignore file lists patterns git should never track (build output, venvs, secrets); add it before the first commit, because ignoring a file already tracked requires untracking it first. Never commit secrets: once pushed, a secret is compromised - rotate it, do not just delete the file.

## Quick reference

- git init (-b main): new repo here. git clone URL: copy with history.

- Set identity: git config --global user.name / user.email.

- Three areas: working tree, staging index, HEAD. git status shows all.

- .gitignore before the first commit; tracked files need untracking to ignore.

- Never commit secrets: pushed = compromised. Rotate, don't just delete.


## Worked example

First day with a new repository:

```
$ mkdir notes && cd notes
$ git init -b main
$ git config user.email 'ada@example.com'
$ printf '*.log\n.venv/\n.env\n' > .gitignore
$ echo '# notes' > README.md
$ git add .gitignore README.md
$ git commit -m 'Initial commit'
$ git status
```

- -b main names the first branch explicitly.

- .gitignore lists the untrackables before anything is committed.

- git add stages; git commit snapshots the stage.


## Common mistakes

- Committing .env or keys, then 'fixing' by deleting the file.
  Fix: History keeps it. Rotate the secret and purge history properly.

- No .gitignore until after build artifacts are tracked.
  Fix: Write .gitignore first; untracking later is messier.


## Quick checks

Q: I committed a secret - how do I fix it?
A: Rotate the secret immediately: it is compromised the moment it was pushed. Then purge it from history (git filter-repo or BFG) and force-push, knowing clones may still hold it. Prevention (.gitignore, pre-commit hooks) beats cleanup.


Q: init vs clone - when each?
A: init when the project starts on your machine. clone when it already exists elsewhere (a teammate's repo, GitHub) and you want a local copy.


## Mental model

git init is staking a claim: this directory is now a project with a memory. clone is photocopying someone else's claimed land, fences and all, with a note saying where the original is (origin). The staging area is the loading dock: boxes sit there until you sign the manifest (commit).
