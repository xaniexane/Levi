---
skill_id: cyber_implementing_fuzz_testing_in_cicd_with_aflplusplus
name: Fuzz Testing in CI/CD with AFL++
description: Integrate AFL++ coverage-guided fuzzing into CI/CD to find memory-safety bugs before release.
risk: low
permissions: []
requires_confirmation: false
tags: [testing, devsecops]
version: 1.0.0
---
## Purpose
Memory-safety bugs (overflows, use-after-free, parsing flaws) hide in code paths unit tests never
reach. Coverage-guided fuzzing (AFL++) bombards parsers and protocol handlers with mutated inputs,
using coverage feedback to explore deeper — finding crashes humans miss. This playbook integrates
AFL++ into CI/CD: harness writing, corpus management, crash triage, and regression — the
memory-safety net for C/C++ (and harness-able) code.

## When to use
- Securing C/C++ codebases, parsers, protocol handlers, media codecs, and deserialization logic.
- After incidents involving memory-corruption vulnerabilities (buffer overflows, RCE via file
  parsing).
- Meeting secure-SDLC expectations for high-assurance or exposed native code.
- Before releases of libraries, daemons, or firmware components.
- As the depth layer beneath SAST (which finds patterns; fuzzing finds actual crashes).

## Prerequisites
- Target code identified: parsers, network handlers, file-format processors — the attack surface,
  not the whole codebase.
- Build system capable of instrumented builds (afl-clang-fast / afl-clang-lto) in CI.
- Fuzzing infrastructure: CI runners with sufficient CPU (fuzzing is compute-hungry) or dedicated
  fuzzing hosts.
- Sanitizers available: ASan/UBSan builds for precise crash diagnosis.
- Developer ownership: someone must triage crashes — fuzzing without triage is just electricity.

## Procedure
1. **Select and prioritize targets.** Rank by: attack exposure (untrusted input handlers first),
   code criticality, and historical bug density. Start with 1-3 harnesses on the highest-risk
   parsers — prove value before expanding. Document the target list and rationale.
2. **Write focused harnesses.** Each harness feeds fuzzer input to one API/entry point (e.g.,
   LLVMFuzzerTestOneInput calling the parser). Keep harnesses fast (microseconds per run — slow
   harnesses waste the fuzzing budget), deterministic, and free of network/disk dependencies. Good
   harnesses are the highest-leverage fuzzing work.
3. **Build the seed corpus.** Collect valid sample inputs (test files, protocol captures, regression
   corpora) per target. A good corpus gives the fuzzer valid starting points to mutate — coverage
   from valid inputs beats random bytes. Minimize the corpus (afl-cmin) to keep it fast.
4. **Integrate short fuzzing runs into CI.** Add a CI stage: build instrumented + sanitizer
   binaries, run AFL++ for a bounded time (10-30 min per target on PRs; longer nightly), and fail
   the build on new unique crashes. Short runs catch regressions; they're not exhaustive — set that
   expectation.
5. **Run long campaigns outside CI.** Nightly/weekly multi-hour (or continuous, on dedicated hosts)
   campaigns with the full corpus explore deeper. Sync interesting new corpus entries back to the
   shared corpus. Long campaigns find the bugs short runs miss — budget the compute.
6. **Build with sanitizers for diagnosis.** Fuzz ASan+UBSan instrumented builds: crashes come with
   precise reports (heap-buffer-overflow at file:line, use-after-free stacks). Deduplicate crashes
   by stack hash — one bug can produce thousands of crashing inputs; triage unique stacks, not
   inputs.
7. **Triage crashes like vulnerabilities.** For each unique crash: reproduce, assess exploitability
   (write vs. read, control of values — use the sanitizer report and manual analysis), file with
   severity, and assign to the code owner. Fuzzer-found crashes are real bugs until proven otherwise
   — "probably not exploitable" needs evidence.
8. **Add regression tests.** For every fixed crash, add the crashing input to the regression
   corpus/tests so the bug can never silently return. The corpus is institutional memory of past
   failures — it grows with every bug.
9. **Measure fuzzing effectiveness.** Track: coverage over time per target (is the fuzzer still
   finding new code?), unique crashes found and fixed, time-to-fix, and corpus size. Stagnant
   coverage means the harness or corpus needs work — fuzzing isn't "set and forget."
10. **Expand and maintain.** Add harnesses for new parsers/handlers as code evolves (require fuzz
    harnesses for new untrusted-input code in the secure-SDLC policy). Keep AFL++ and toolchains
    updated; periodically refresh the corpus with new valid samples. Review target priorities
    annually.

## Expected outputs
- AFL++ harnesses for priority targets with seed corpora, integrated into CI (bounded runs, fail on
  new crashes).
- Long-running campaigns on dedicated capacity with corpus sync.
- Sanitizer-instrumented builds producing deduplicated, triaged crash reports.
- Crash-to-fix workflow with regression inputs added per bug.
- Coverage and fix metrics with expanding target coverage.

## Pitfalls
- Fuzzing without harnesses: pointing AFL++ at main() rarely works. Harness writing is the
  essential, skilled work — budget for it.
- Slow harnesses: milliseconds-per-run harnesses burn the time budget on nothing. Optimize harness
  speed relentlessly.
- No triage ownership: crashes pile up, developers ignore the fuzzer, the program dies. Every target
  needs an owner.
- Treating CI runs as exhaustive: bounded CI fuzzing catches regressions; deep bugs need long
  campaigns. Both, with honest expectations.
- Ignoring the corpus: stale or tiny corpora cap effectiveness. Curate and grow it — it's the
  fuzzer's starting intelligence.

## References
- AFL++ documentation (build modes, corpus management, CI integration)
- Google OSS-Fuzz documentation (harness-writing guidance, applicable beyond OSS-Fuzz)
- NIST SP 800-53 SI-10 (information input validation — fuzzing as validation testing)
- "Fuzzing" research literature (coverage-guided methodology background)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
