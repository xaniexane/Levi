---
skill_id: utility.log_error_extractor
name: Log Error Extractor
description: Stream a log file and write every error-like line to a findings file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [logs, errors, extract]
version: 1.0.0
---

# Log Error Extractor

Log Error Extractor streams through a log file - never loading it whole - matches lines against an error pattern (ERROR, Traceback, Exception, CRITICAL, FAILED), and writes the hits with line numbers to a new file.

## When to use

- Pulling failures out of a huge application log.
- Isolating tracebacks from a noisy test run.
- Building an incident timeline's raw material.

## Steps

1. Define or confirm the match pattern; start with ERROR|CRITICAL|Traceback|Exception|FAILED and tune it.
2. Stream the log line by line, recording matches with their line numbers.
3. Write matches to a new findings file; report total lines scanned and hits found.
4. Read the findings file - patterns in the hits often matter more than any single hit.

## Honest limits

- Pattern-based, not magic: an unusual error format needs its pattern added.
- The skill extracts; diagnosing the errors is separate work.
- Streaming keeps memory flat even on multi-gigabyte logs.

Original work authored for LEVI - utilities pack.
