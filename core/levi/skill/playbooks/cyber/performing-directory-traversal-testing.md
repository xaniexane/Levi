---
skill_id: cyber_performing_directory_traversal_testing
name: Directory Traversal Control Validation
description: Validate your applications against path traversal flaws and detect exploitation attempts.
risk: low
permissions: []
requires_confirmation: false
tags: [web, assessment, hardening]
version: 1.0.0
---

## Purpose

Path traversal lets crafted input (`../`, encoded variants, absolute paths) escape the intended directory and read — or write — files the application never meant to expose. It remains common in file-download, template, and archive-extraction features. This playbook is defensive: assess your own applications for traversal weaknesses safely, detect exploitation attempts in your logs, and fix the root cause with proper path handling. Testing is limited to applications you own or are authorized to assess.

## When to use

- Security review of features that read or write files based on user input (downloads, exports, avatars, templates).
- Validating a scanner or bounty report claiming path traversal.
- Auditing archive extraction (zip-slip class) in your codebase.
- Detecting traversal probing in WAF and application logs.
- Setting secure file-handling standards for development teams.

## Prerequisites

- Authorization covering the application and test environment.
- Inventory of file-handling endpoints: parameters that influence file paths, and the intended base directories.
- Test environment with canary files placed outside the web root to detect successful reads (never use real sensitive files as canaries).
- Access to WAF and application logs for detection work.
- Knowledge of the platform's path semantics (Windows vs. Linux separators, encoding handling).

## Procedure

1. **Inventory file-handling surface.** Enumerate endpoints accepting filenames, paths, template names, or archive uploads. For each, record the intended base directory and the code that joins user input to it. Features added quickly (export-to-CSV, "download report") are the usual suspects.
2. **Review path construction in code.** Check for: direct string concatenation of user input into paths, missing canonicalization, blocklists of `../` (bypassable via encoding, double-encoding, `....//`), and archive extraction without entry-name validation (zip-slip). Note the framework's path utilities — many have safe join functions nobody used.
3. **Validate safely in test.** Where authorized, submit traversal probes against test endpoints using canary filenames: `../` sequences, URL-encoded and double-encoded variants, absolute paths, and null-byte terminations (legacy stacks). Success is defined strictly as reading a canary file outside the base directory — never probe for real system files.
4. **Test archive handling separately.** Upload archives containing entries like `../../evil.txt` to your extraction code in test and verify entries are rejected or sanitized. Zip-slip is a distinct code path from URL-parameter traversal and needs its own test.
5. **Detect probing in production.** Alert on: `../` and encoded variants in request parameters and URLs, absolute-path patterns (`/etc/`, `C:\`) in web input, and repeated traversal probes from single sources (scanner or attacker reconnaissance). Correlate with application error logs showing file-not-found for suspicious paths.
6. **Fix at the root.** Apply in order: (a) avoid user-controlled paths entirely — map inputs to an allowlist of identifiers; (b) canonicalize the resolved path and verify it stays within the base directory (`startswith` on the resolved absolute path, not the raw input); (c) use framework safe-join utilities; (d) run the application with filesystem permissions that make escape low-impact even if logic fails.
7. **Verify and regression-test.** Re-run the traversal probes against the fixed build confirming rejection, and add automated tests asserting that malicious path inputs are neutralized. Include archive-extraction tests in the suite.

## Expected outputs

- Inventory of file-handling endpoints with traversal exposure ratings.
- Safe validation evidence from test (canary-based, no real sensitive files touched).
- Severity-rated findings with root-cause analysis per endpoint.
- Remediation: allowlist mapping, canonicalization checks, safe extraction, least-privilege file permissions.
- Production detection rules for traversal probing and CI regression tests.

## Pitfalls

- Blocklisting `../` instead of allowlisting/canonicalizing — encoding bypasses are endless.
- Checking the raw input rather than the canonicalized resolved path; normalization must happen before the boundary check.
- Forgetting archive extraction paths when fixing URL-parameter traversal — they are separate bugs.
- Probing production with traversal payloads, which can read real sensitive files or trigger incident response.
- Assuming the framework handles it; verify the safe function is actually called on every path.

## References

- OWASP Path Traversal guidance and testing guide
- CWE-22, "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')"
- CWE-29/178 context for improper validation variants
- Snyk/zip-slip vulnerability documentation for archive extraction patterns
- Framework docs for safe path joining (e.g., Python `pathlib`, Java `Path.normalize`)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
