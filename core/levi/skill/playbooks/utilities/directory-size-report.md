---
skill_id: utility.directory_size_report
name: Directory Size Report
description: Walk a directory tree and display what's consuming the space, largest first.
risk: info
permissions: []
requires_confirmation: false
tags: [files, disk, report]
version: 1.0.0
---

# Directory Size Report

Directory Size Report walks a directory tree, totals file sizes per directory, and displays the breakdown sorted largest-first so the space hogs are obvious. Read-only.

## When to use

- Finding what is eating disk space.
- Auditing a project folder before archiving.
- Comparing the weight of two directory trees.

## Steps

1. Walk the tree with os.scandir, summing file sizes per directory.
2. Handle permission-denied directories gracefully: note them, do not crash.
3. Display the top entries sorted by size with human-readable units.
4. Offer a depth limit so the report stays readable on huge trees.

## Honest limits

- Standard library only.
- Sizes are logical file sizes, not disk blocks - sparse files may differ.
- Read-only: it measures, it never cleans.

Original work authored for LEVI - utilities pack.
