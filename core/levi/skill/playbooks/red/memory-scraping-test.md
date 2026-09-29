---
skill_id: red_memory_scraping_test
name: Memory Scraping Test
description: Test memory-scraping techniques to validate EDR memory protection.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, memory, pos]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_memory_dumps_with_volatility
---
# Memory Scraping Test

## Purpose

Memory scraping reads secrets straight from process memory — PANs, keys, tokens. This
test scrapes canary secrets from test processes and validates whether EDR memory-
protection and read-monitoring catch it.

## When to use

- During collection phases.
- To validate EDR protections on sensitive processes.
- When the threat model includes POS-style or secret-harvesting malware.

## Prerequisites

- Authorization for memory-read operations on test processes.
- Canary secrets in test process memory only.

## Procedure

1. Plant canary secrets (fake PANs, tokens) in test process memory.
2. Scrape process memory with authorized tooling; verify canary recovery.
3. Record EDR telemetry: process-memory-read events, alerts.
4. Test protected processes: does PPL or EDR self-protection block the scrape?
5. Verify no real process memory was read beyond the test processes.
6. Deliver the memory-protection assessment.

## Expected outputs

- Memory-scrape success/detection per process type.
- Protected-process effectiveness results.
- Scope-compliance verification.

## Pitfalls

- Scraping real processes (browsers, password managers) without approval — test
  processes only.
- Recovered canary secrets handled per the credential ROE anyway — build the habit.

## References

- MITRE ATT&CK: Credential material from memory; POS-malware literature.

## Blue-team control under test

This playbook validates their EDR memory protections are under test — unalerted scraping
of sensitive processes is a memory-monitoring gap. Paired blue-team counterpart:
`cyber_analyzing_memory_dumps_with_volatility`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
