---
skill_id: red_dll_hijacking_test
name: DLL Hijacking Test
description: Test DLL search-order hijacking in a lab to validate application directory permissions and monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, dll-hijacking, lab]
version: 1.0.0
team: red
tests_blue: cyber_core_dll_hijacking
---
# DLL Hijacking Test

## Purpose

Applications that load DLLs from writable directories can be hijacked: place a malicious
DLL earlier in the search order and it executes with the application's privileges. This
lab test identifies hijackable applications and validates directory-permission
hardening.

## When to use

- During persistence/privesc phases, lab-first.
- To validate that application directories are not user-writable.
- To test EDR detection of sideloaded DLL loads.

## Prerequisites

- Lab authorization; identify candidate applications with writable install directories.
- Inert DLLs only (canary MessageBox or file write).

## Procedure

1. Enumerate applications with missing DLLs (procmon-style missing-DLL profiling) or
   writable application directories.
2. Check directory permissions: is the application folder writable by the test user?
3. Place an inert hijack DLL in the search-order position and launch the application;
   verify the canary executed.
4. Record EDR telemetry: was the sideloaded DLL load flagged (image-load events)?
5. Test the phantom-DLL variant (DLL named for a non-existent import) vs. search-order
   variant.
6. Remediate in the report: directory ACL fixes per application; re-test to confirm.

## Expected outputs

- Hijackable-application list with permission evidence.
- EDR image-load detection matrix.
- Remediation verification (re-test after ACL fixes).

## Pitfalls

- Real malicious DLLs — inert canaries only.
- Hijacking system applications without authorization for the blast radius.
- Forgetting that installers/updates reset directory permissions — note in the report.

## References

- MITRE ATT&CK: Hijack Execution Flow — DLL Search Order Hijacking (T1574.001).

## Blue-team control under test

This playbook validates their application-directory ACLs and EDR image-load monitoring
are under test — writable app directories are a hardening finding on their own. Paired
blue-team counterpart:
`cyber_core_dll_hijacking`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
