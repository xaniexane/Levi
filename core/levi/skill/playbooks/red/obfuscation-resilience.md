---
skill_id: red_obfuscation_resilience
name: Obfuscation Resilience Test
description: Test obfuscated payloads against static detection to validate layered detection.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, obfuscation]
version: 1.0.0
team: red
tests_blue: cyber_deobfuscating_powershell_obfuscated_malware
---
# Obfuscation Resilience Test

## Purpose

Obfuscation defeats signature and static analysis; behavior must catch what static
misses. This test runs progressively obfuscated canary payloads to prove the detection
stack's layers — static, AMSI, behavioral — each get their score.

## When to use

- During defense-evasion phases.
- To validate that behavioral detection covers what static analysis misses.
- To tune allow/block thresholds on obfuscation heuristics.

## Prerequisites

- Authorization for the test hosts; canary payloads only.
- Layered telemetry: static scan logs, AMSI, EDR behavioral alerts.

## Procedure

1. Build a canary payload in cleartext; verify each detection layer fires (baseline).
2. Apply progressive obfuscation: encoding, string splitting, dynamic invocation, packing —
   re-test each layer per stage.
3. Record per stage and per layer: blocked, alerted, or silent.
4. Identify the obfuscation stage where static/AMSI goes silent and confirm behavioral
   coverage takes over (or document the gap).
5. Clean all payload artifacts from test hosts.
6. Deliver the layered-detection scorecard with tuning recommendations.

## Expected outputs

- Obfuscation-stage × detection-layer matrix.
- Static-to-behavioral handoff analysis.
- Tuning recommendations per layer.

## Pitfalls

- Real malicious payloads 'for realism' — canaries only.
- Packing that the EDR quarantines the test tooling over — coordinate with the SOC.
- Concluding 'obfuscation wins' when behavioral caught it — score each layer honestly.

## References

- MITRE ATT&CK: Obfuscated Files or Information (T1027).

## Blue-team control under test

This playbook validates their detection layering is under test — the stage where every
layer goes silent defines the obfuscation ceiling they must raise. Paired blue-team
counterpart: `cyber_deobfuscating_powershell_obfuscated_malware`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
