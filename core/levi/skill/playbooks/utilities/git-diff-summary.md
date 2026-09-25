---
skill_id: utility.git_diff_summary
name: Git Diff Summary
description: Summarize a git diff into files changed, line counts, and what kind of change each is.
risk: info
permissions: []
requires_confirmation: false
tags: [git, diff, review]
version: 1.0.0
---

# Git Diff Summary

Git Diff Summary parses git diff output into a readable overview: which files changed, how many lines were added and removed per file, and renames detected. Read-only; the working tree is untouched.

## When to use

- Reviewing a change before committing or pushing.
- Getting the shape of a large diff without reading every line.
- Sanity-checking that a commit contains only what you meant.

## Steps

1. Run git diff --stat and --numstat against the right target (worktree, staged, or a commit range).
2. Summarize per file: additions, deletions, and whether it looks like a rename.
3. Flag binary files (reported, not analyzed) and unusually large diffs.
4. Display the summary table; the full diff remains one command away.

## Honest limits

- Read-only analysis of diff output; nothing is staged, committed, or reset.
- It summarizes the shape of change, not its correctness - review still needs eyes.
- Binary files are noted by presence, not content.

Original work authored for LEVI - utilities pack.
