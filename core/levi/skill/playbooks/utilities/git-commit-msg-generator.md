---
skill_id: utility.git_commit_msg_generator
name: Git Commit Message Generator
description: Draft a conventional commit message from your staged changes - it never commits.
risk: low
permissions: []
requires_confirmation: false
tags: [git, commit, messages]
version: 1.0.0
---

# Git Commit Message Generator

Git Commit Message Generator reads your staged diff, summarizes what changed, and proposes a conventional commit message (type: subject, with a body for larger changes). It only drafts - you run git commit yourself.

## When to use

- Writing consistent commit messages without staring at the diff.
- Enforcing a type: subject convention across a team.
- Summarizing a large staged change before committing.

## Steps

1. Confirm there are staged changes (git diff --cached --stat); nothing staged means nothing to describe.
2. Summarize the diff: files touched, lines added/removed, apparent intent.
3. Draft the message: a conventional type (feat, fix, docs, refactor, test, chore), an imperative subject under 72 chars, and a body if the change needs explaining.
4. Display the draft for your approval; do not commit.

## Honest limits

- Draft only - this skill never runs git commit; the commit remains your decision.
- It describes the diff, not your intent; correct the message when the why differs from the what.
- Unstaged changes are ignored - stage first, then draft.

Original work authored for LEVI - utilities pack.
