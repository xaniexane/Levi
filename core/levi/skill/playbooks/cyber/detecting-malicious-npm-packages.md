---
skill_id: cyber_detecting_malicious_npm_packages
name: Detecting Malicious npm Packages
description: Detect malicious npm packages — typosquats, compromised maintainers, dependency-confusion — before and after install.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, npm, detection]
version: 1.0.0
---
## Purpose

Modern applications inherit the risk of every package they install, and npm's scale makes it a prime target for typosquatting, account-takeover, and dependency-confusion attacks. This playbook covers both preventive gates (keeping bad packages out) and detective controls (finding the ones that got in), from the developer workstation to the CI pipeline to production.

## When to use

- A threat feed reports malicious npm packages and you need to check exposure.
- Your organization wants guardrails on open-source package consumption.
- Incident response suspects a compromised dependency in a build.
- A developer reports a suspicious package name or unexpected install behavior.

## Prerequisites

- Inventory of Node.js projects and their lockfiles (package-lock.json) across repos.
- A Software Bill of Materials (SBOM) or dependency-scanning tool in CI (npm audit, Socket, Snyk, or equivalent).
- Access to npm registry metadata and an internal proxy/registry (e.g., Artifactory, Nexus) if used.
- Defined policy: who may publish, version-pinning rules, and an approved-package process.

## Procedure

1. Gate at install time. Enforce lockfiles and `npm ci` in CI (never `npm install` with floating ranges), pin versions, and require integrity hashes. Route installs through an internal registry proxy that can block or quarantine newly published or flagged packages, and alert on installs of packages younger than a policy threshold (e.g., published within 24-72 hours).
2. Scan continuously, not just at build. Run dependency scanning on every PR and on a schedule against all repos — new disclosures arrive daily, and a package that was clean at build time may be flagged later. Track both direct and transitive dependencies; malicious code usually hides transitively.
3. Hunt for the classic malicious-package indicators: typosquat or brand-adjacent names, packages with install scripts (preinstall/postinstall) that exfiltrate data or download payloads, sudden ownership/maintainer changes, version bumps with no changelog, and packages that phone home to unexpected domains at install time (monitor CI egress).
4. Check for dependency confusion. Ensure internal package names cannot be claimed on the public registry (or are claimed defensively), configure scoped registries explicitly per scope, and alert on public-registry resolutions of internal package names in CI logs.
5. Respond to a confirmed malicious package as a supply-chain incident. Identify every repo, build, and deployed artifact containing it (SBOM makes this fast), rotate any secrets that passed through affected build environments, rebuild from clean lockfiles, and check production telemetry for the package's known malicious behaviors (C2 domains, exfil artifacts).
6. Harden the consumption pipeline: require 2FA on developer npm accounts, restrict who can publish under your scopes, sign and verify artifacts where possible, and maintain an allowlist for high-risk categories (install scripts, native bindings).

## Expected outputs

- CI gates: lockfile enforcement, integrity verification, new-package quarantine, scheduled rescans.
- Exposure report capability: given a package name+version, list affected repos/builds/artifacts within minutes.
- Dependency-confusion protections: scoped registry config, internal-name monitoring.
- Incident runbook for malicious-package confirmation: containment, secret rotation, rebuild, production hunting.

## Pitfalls

- npm audit alone is insufficient — it covers known CVEs, not malicious packages; use a malicious-package feed too.
- Transitive dependencies are where attackers hide; scanning only direct dependencies misses most risk.
- Blocking all install scripts breaks legitimate packages — allowlist by package, don't ban globally without review.
- Developers bypassing the proxy with public-registry installs defeats every gate — enforce via network policy and CI checks.
- A compromised maintainer account can push a malicious patch version of a trusted package — monitor for anomalous publishes of your critical dependencies.

## References

- npm documentation: package-lock.json and npm ci; OpenSSF guidance on securing software supply chains; MITRE ATT&CK T1195.002 (Supply Chain Compromise: Compromise Software Supply Chain) — https://attack.mitre.org/techniques/T1195/002/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
