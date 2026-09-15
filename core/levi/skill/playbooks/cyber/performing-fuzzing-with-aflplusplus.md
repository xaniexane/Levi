---
skill_id: cyber_performing_fuzzing_with_aflplusplus
name: Fuzzing with AFLplusplus
description: Discover memory-safety flaws in binaries with coverage-guided fuzzing.
risk: low
permissions: []
requires_confirmation: false
tags: [fuzzing, testing, vulnerabilities]
version: 1.0.0
---
# Fuzzing with AFLplusplus

## Purpose

Fuzzing finds the crashes that manual review misses. AFLplusplus is a
coverage-guided fuzzer that mutates inputs to maximize code coverage in a
target binary, surfacing memory-corruption bugs before attackers do. This
playbook runs a productive fuzzing campaign and turns crashes into
actionable, fixed vulnerabilities.

## When to use

- Security-testing parsers, protocol handlers, and file-format code
  your organization ships.
- Triaging a suspected memory-safety bug to find the full crash surface.
- Validating that a patch actually closes the vulnerable code paths.
- Pre-release hardening of C/C++ components.

## Prerequisites

- Source or a buildable target: compile with AFL instrumentation
  (`afl-clang-fast`) and AddressSanitizer for maximum signal.
- A corpus of valid seed inputs for the target's input format; fuzzing
  from an empty corpus wastes cycles on format parsing.
- Compute capacity: fuzzing is CPU-hungry — dedicate cores or machines,
  never a shared production host.

## Procedure

1. Build the harness: instrument with `afl-clang-fast`, link ASan/UBSan,
   and create a minimal driver that feeds one input file per run and
   exits cleanly.
2. Assemble the seed corpus: collect valid sample inputs covering the
   target's features; minimize with `afl-cmin` so the fuzzer starts
   from a compact, diverse set.
3. Launch the campaign: `afl-fuzz -i seeds -o out -- ./target @@` and
   let it run for a meaningful window (days for new targets, not
   minutes).
4. Monitor the status screen: track execs/sec, coverage edges, and
   stability — low stability means nondeterminism that will hide bugs.
5. Triage crashes as they appear: deduplicate with `afl-tmin` and
   stack-hash grouping; confirm each unique crash under ASan to get the
   exact fault (heap overflow, UAF, stack smash).
6. Convert crashes to proof-of-concept: minimize the input, identify
   the vulnerable function, and assess exploitability (controllable
   write? PC control?) to set severity.
7. File and fix: report with the minimized PoC, ASan trace, and affected
   versions; verify the fix by re-running the crashing corpus against
   the patched build.
8. Keep the corpus: add the minimized crash inputs to a regression
   corpus run in CI so the bug class never returns silently.

## Expected outputs

- Unique, deduplicated crashes with ASan traces and minimized PoCs.
- Severity assessments and filed vulnerability reports.
- Verified patches confirmed by re-fuzzing the crash corpus.
- A regression corpus integrated into CI.

## Pitfalls

- Fuzzing uninstrumented binaries: you get coverage noise and miss the
  sanitizer's precise fault reports.
- Stopping at the first crash: the same code usually holds a family of
  bugs — keep the campaign running.
- Treating hangs as low priority: algorithmic-complexity hangs are
  denial-of-service bugs.
- Fuzzing without a stability check: flaky harnesses produce flaky
  "findings."

## References

- AFLplusplus documentation (github.com/AFLplusplus/AFLplusplus)
- NIST SP 800-95 guidance on secure software testing practices
- Google OSS-Fuzz documentation on continuous fuzzing
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
