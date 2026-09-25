---
skill_id: sys_git_workflows
name: Git workflows
description: Team patterns: feature branches, trunk-based, and choosing what fits.
risk: info
permissions: []
requires_confirmation: false
tags: [git, vcs]
version: 1.0.0
---
# Git workflows

## Purpose

Team patterns: feature branches, trunk-based, and choosing what fits.

## Overview

Workflows are team agreements about branches. Feature-branch flow (GitHub flow): branch per change, open a pull request, review, merge to main, deploy. Simple, review-centric, fits most teams. Gitflow adds develop/release/hotfix branches - ceremony that pays off for versioned releases with parallel maintenance, overhead otherwise. Trunk-based: everyone commits to main (or very short branches), protected by CI and feature flags - fastest integration, demands discipline and great tests. Pull requests are the review unit: small, focused, with context (what/why, test evidence). Review etiquette: comment on code not people, distinguish blocking from nitpicking, approve when good enough - perfection is the enemy of merged. Protect main: require reviews, require green CI, no direct pushes. Keep main always releasable - broken main blocks everyone. Merge strategy per team: merge commits preserve PR context, squash keeps main linear and tidy, rebase-and-merge keeps linearity with per-commit history. Pick one, document it, stop debating it. Whatever the flow, the invariants hold: small changes, fast reviews, green main.

## Quick reference

- Feature-branch/PR flow: the default for most teams.

- Gitflow: for versioned releases with parallel maintenance lines.

- Trunk-based: fastest, needs great CI + feature flags.

- Protect main: reviews required, CI green, no direct pushes.

- PRs small and focused; approve when good enough.

- One merge strategy per team, documented. Main stays releasable.


## Worked example

A clean pull-request-sized change:

```
$ git switch -c feat/retry-with-backoff
# ... small focused change + tests ...
$ git push -u origin feat/retry-with-backoff
# open PR: title, what/why, test evidence
# after approval + green CI: squash-merge, delete branch
$ git switch main && git pull --ff-only
```

- One branch per reviewable change; push early for visibility.

- The PR description carries context CI cannot: why this approach.

- Sync main after merge so the next branch starts fresh.


## Common mistakes

- Mega-PRs touching everything: unreviewable, unmergeable.
  Fix: Split by concern; stack branches if they depend on each other.

- Direct pushes to main 'just this once': broken main blocks all.
  Fix: Protect main mechanically; no exceptions, not even for leads.


## Quick checks

Q: Which workflow should my team pick?
A: Default to feature-branch + PRs. Add Gitflow ceremony only for parallel version maintenance. Go trunk-based when CI is fast, tests are strong, and you can feature-flag - it integrates fastest.


Q: How do I get faster PR reviews?
A: Make PRs small (< ~400 lines), describe the why, show test evidence, and review others promptly - review latency is reciprocal.


## Mental model

Workflows are kitchen systems: feature-branch is tickets per dish with the head chef tasting (review) before it goes out; trunk-based is everyone seasoning the same pot continuously, trusting the recipe tests. Both work; chaos is everyone cooking without a system.
