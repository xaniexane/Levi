---
skill_id: sys_git_tags_releases
name: Git tags and releases
description: Marking points in history: lightweight vs annotated tags and release hygiene.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git tags and releases

## Purpose

Marking points in history: lightweight vs annotated tags and release hygiene.

## Overview

Tags are fixed pointers to commits, usually marking releases: v1.2.0. Lightweight tags are bare pointers; annotated tags (-a) are full objects with a message, tagger, and date - and can be GPG-signed (-s). Always prefer annotated (signed when provenance matters): they carry who, when, and why. git push --follow-tags pushes commits plus their tags; plain push does not push tags, and --tags pushes all (including teammates' experiments - avoid). Semantic versioning (MAJOR.MINOR.PATCH) communicates change impact: breaking, feature, fix. Tag from the release commit on main after CI passes, not from a feature branch. Releases pair tags with notes: generate changelogs from commit messages (which is why message discipline pays). Never move a published tag - downstream builds pin them, and moving one is a supply-chain integrity violation; cut a new version instead. Delete a bad unpublished tag with git tag -d plus push --delete. Verify signatures with git tag -v when consuming others' releases.

## Quick reference

- Annotated tags (-a): message, tagger, date - always prefer over lightweight.

- Sign release tags (-s) when provenance matters; verify with tag -v.

- push --follow-tags: push commits + their tags. Avoid bare --tags.

- Semver: MAJOR.MINOR.PATCH = breaking.feature.fix.

- Tag the release commit on main after CI passes.

- Never move a published tag; cut a new version instead.


## Worked example

Cutting a signed release tag:

```
$ git switch main && git pull --ff-only
$ git log --oneline -3          # confirm CI-green release commit
$ git tag -s v2.4.0 -m 'Release 2.4.0: faster sync, new CLI'
$ git tag -v v2.4.0            # verify the signature
$ git push --follow-tags
```

- Tag the main-branch release commit, after CI passes.

- -s signs the tag: provenance for downstream consumers.

- --follow-tags pushes the tag with its commits, nothing extra.


## Common mistakes

- Moving a published tag to 'fix' a release.
  Fix: Downstream pins break silently. Cut v2.4.1 instead.

- git push --tags pushing everyone's experimental tags.
  Fix: Use --follow-tags to push only your release tags.


## Quick checks

Q: Lightweight vs annotated - does it really matter?
A: For personal bookmarks, lightweight is fine. For anything shared - especially releases - annotated carries the metadata (who/when/why) and supports signing. Shared tags should always be annotated.


Q: I tagged the wrong commit and pushed - fix?
A: If it just happened and nobody consumed it: delete locally and remotely, re-tag correctly, and tell everyone. If it is published and pinned downstream: leave it, cut a new version. Moving published tags breaks trust.


## Mental model

Tags are brass plaques bolted to a milestone: annotated tags are engraved (who, when, why), lightweight are blank plates. Moving a published plaque is rewriting history at the monument - visitors with old maps (pinned builds) get lost.
