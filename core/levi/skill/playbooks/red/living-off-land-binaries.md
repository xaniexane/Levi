---
skill_id: red_living_off_land_binaries
name: Living-Off-the-Land Binaries (LOLBins)
description: Test LOLBin abuse paths (certutil, mshta, rundll32, etc.) to validate application-control and EDR behavioral rules.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, lolbins, application-control]
version: 1.0.0
team: red
tests_blue: cyber_core_lolbins_abuse
---
# Living-Off-the-Land Binaries (LOLBins)

## Purpose

Attackers live off the land — using signed Microsoft binaries for malicious purposes.
This playbook tests a representative LOLBin set against application-control
(AppLocker/WDAC) and EDR behavioral rules, measuring which dual-use executions are
caught and which sail through.

## When to use

- During execution phases where application allowlisting is claimed.
- To build the EDR behavioral-rule test matrix.
- When the threat model emphasizes fileless/living-off-the-land attacks.

## Prerequisites

- Authorization for LOLBin execution; payloads inert (canary writes, calculator-style
  proofs).
- List of LOLBins in the corporate baseline to test systematically.

## Procedure

1. Select a representative LOLBin set: certutil (download), mshta (HTA exec), rundll32 (DLL
   exec), regsvr32, msiexec, wmic, powershell — inert arguments only.
2. Execute each with a canary payload and record: blocked, alerted, or silent — per binary,
   per argument pattern.
3. Test application-control policies: does AppLocker/WDAC block the abusive invocation
   while allowing legitimate use?
4. Check EDR behavioral detections: which LOLBin executions triggered behavior rules vs.
   signature-only?
5. Vary the invocation (renamed binary, alternate paths) where authorized, to test rule
   robustness.
6. Deliver the LOLBin matrix with recommended allowlist refinements and EDR rule additions.

## Expected outputs

- Per-LOLBin block/alert/silent matrix.
- Application-control bypass findings with rule-fix recommendations.
- EDR behavioral-rule coverage assessment.

## Pitfalls

- Real malicious payloads via LOLBins 'for realism' — canary payloads prove the same
  execution.
- Testing LOLBins that are legitimately used by IT without distinguishing — note dual-
  use explicitly.
- Forgetting 32-bit vs. 64-bit binary paths (SysWOW64) in the matrix.

## References

- MITRE ATT&CK: Signed Binary Proxy Execution (T1218); LOLBAS project (public).

## Blue-team control under test

This playbook validates their application-control and EDR behavioral layers face the
dual-use problem directly — silent LOLBin execution is a behavior-detection gap. Paired
blue-team counterpart: `cyber_core_lolbins_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
