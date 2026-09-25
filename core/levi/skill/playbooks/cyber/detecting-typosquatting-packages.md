---
skill_id: cyber_detecting_typosquatting_packages
name: Detecting Typosquatting Packages
description: Detect typosquatting attacks against software packages generally.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, typosquatting, detection]
version: 1.0.0
---
## Purpose

Typosquatting — publishing malicious packages with names one keystroke from legitimate ones — preys on developer typos and dependency confusion. This playbook covers typosquat detection as a general practice: name-similarity monitoring, package-metadata analysis, and the install-time gates that catch typosquats across ecosystems.

## When to use

- You need a typosquat-detection practice spanning package ecosystems.
- A typosquat incident occurred and you need broader coverage.
- Developers install packages ad hoc and you need guardrails.
- Evaluating supply-chain security tooling.

## Prerequisites

- Inventory of critical dependencies per ecosystem (npm, PyPI, NuGet, Maven, crates, Go).
- Package-registry metadata access (publish dates, maintainer history, download counts).
- A similarity-comparison method: edit-distance tooling or a monitoring service/feed.
- Install-time controls: internal proxy/registry, dependency scanning in CI.

## Procedure

1. Define your protected namespace. List the packages your organization depends on most critically — by download volume in your builds and by privilege (build tools, auth libraries, crypto). Typosquat monitoring is most valuable for these high-impact names; monitoring every transitive dependency for typos is infeasible, so prioritize deliberately.
2. Monitor for lookalike registrations. Regularly compare new package registrations against your protected list using edit distance (typos, transpositions, omissions), homoglyph/visual similarity, and common affix tricks (extra dashes, 'js'/'py' suffixes, pluralization). Subscribe to typosquat/malicious-package feeds for your ecosystems rather than building all comparisons in-house.
3. Analyze suspicious candidates before acting. For each lookalike: check publish date and maintainer history (new account, no history), compare code/functionality to the legitimate package (typosquats often contain unrelated malicious payloads or are empty), inspect install scripts and network behavior, and check download counts relative to age (suspicious spikes suggest active targeting).
4. Gate at install time. Configure package managers and proxies to: warn or block installs of packages matching typosquat patterns, require approval for newly published packages in protected namespaces, and alert when a developer installs a package whose name is within edit-distance 1-2 of a protected dependency. The install prompt is the last cheap intervention point.
5. Respond to confirmed typosquats. Report the package to the registry for takedown, search all repos/builds for the typosquat name (SBOM/lockfile search), determine if it executed (install scripts run at install time — check build logs and hosts), rotate secrets exposed to affected build environments, and notify developers with the correct package name. Track takedown to completion — re-registration under variants is common.
6. Reduce the typo surface: standardize on lockfiles and `ci`-style installs, maintain an internal allowlist for critical dependencies, educate developers on verifying package names (especially copy-pasted from the web), and claim defensive registrations of obvious typo variants for your own published packages.

## Expected outputs

- Protected-namespace list: critical dependencies prioritized for typosquat monitoring.
- Lookalike-detection process: similarity methods, feed subscriptions, review cadence.
- Install-time gates: proxy warnings/blocks, new-package approval for protected names.
- Typosquat incident runbook: takedown, exposure search, secret rotation, developer notification.

## Pitfalls

- Edit-distance-only matching misses homoglyph and affix tricks — layer multiple similarity methods.
- Monitoring every transitive dependency is infeasible — prioritize by impact and exposure.
- Blocking installs without an allowlist path drives developers to bypass the proxy.
- Typosquats get re-registered under new variants after takedown — monitor continuously, not once.
- Empty/placeholder typosquats are sometimes benign (defensive registrations) — analyze before alarming.

## References

- NIST SP 800-218 (SSDF) — dependency management; MITRE ATT&CK T1195.002 (Supply Chain Compromise) — https://attack.mitre.org/techniques/T1195/002/; OpenSSF guidance on package security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
