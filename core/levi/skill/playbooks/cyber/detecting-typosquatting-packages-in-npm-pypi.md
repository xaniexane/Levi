---
skill_id: cyber_detecting_typosquatting_packages_in_npm_pypi
name: Detecting Typosquatting Packages in npm and PyPI
description: npm/PyPI-specific typosquat detection: ecosystem tooling, metadata, and response.
risk: low
permissions: []
requires_confirmation: false
tags: [npm, pypi, typosquatting]
version: 1.0.0
---
## Purpose

This playbook specializes typosquat detection for the two highest-risk ecosystems — npm and PyPI — covering their specific registry metadata, the attack patterns seen in each, and ecosystem-native tooling and takedown processes. Pair with the general typosquatting playbook for cross-ecosystem strategy.

## When to use

- Your stack is Node.js and/or Python and you need ecosystem-specific coverage.
- A malicious npm/PyPI package was reported — check your exposure.
- Developers use pip/npm directly and you need practical guardrails.
- Building ecosystem-specific supply-chain detections.

## Prerequisites

- npm and PyPI registry metadata access (registry APIs, RSS/sequence feeds of new packages).
- Inventory of your Python/JS dependencies with lockfiles (package-lock.json, requirements/poetry.lock).
- Malicious-package feeds covering npm/PyPI (Socket, Phylum, Snyk, or community feeds).
- Internal proxy/registry (Artifactory, Nexus, or npm/PyPI proxy) for install-time gating.

## Procedure

1. Monitor npm and PyPI new-package streams. Both registries publish new-package feeds — consume them (or a curated malicious-package feed) and compare against your protected dependency list with npm/PyPI-aware similarity: npm scoped-package tricks (@scope/name confusion), PyPI normalization quirks (dashes/underscores/case treated equivalently — attackers exploit this), and cross-ecosystem name collisions.
2. Apply ecosystem-specific metadata checks. npm: inspect package.json for install scripts (preinstall/postinstall), bundled dependencies hiding payloads, and maintainer-change history. PyPI: inspect setup.py for code execution at install time (PyPI's highest-risk vector — setup.py runs arbitrary code on install), check for compiled extensions masking payloads, and verify project URLs and descriptions against the legitimate project. Install-time code execution is the key risk in both — prioritize packages with install hooks.
3. Hunt your existing footprint. Search all lockfiles and build histories for: packages matching typosquat patterns of your dependencies, packages installed from outside your proxy, and packages with install scripts that were never reviewed. Check CI logs for installs of suspicious names — pip and npm both log resolved package versions, which reveals what actually installed versus what was intended.
4. Gate installs per ecosystem. npm: enforce lockfiles + `npm ci`, configure scoped registries, block/warn on install-script packages not allowlisted. pip: require hashes (`--require-hashes`) for critical environments, use a proxy with quarantine for new packages, prefer wheels from trusted indexes, and alert on `--extra-index-url` usage pointing outside approved indexes. Make the secure path the easy path.
5. Respond per ecosystem. For a confirmed malicious npm/PyPI package: report via the registry's abuse process (npm support, PyPI security), search all environments (dev machines too — developers install locally), check for install-script execution (assume code ran at install time), rotate exposed secrets, and pin or remove the dependency. Document the typosquat pattern to improve your monitoring.
6. Claim defensive ground: register obvious typo variants of your own published packages, monitor for new lookalikes of your top 50 dependencies on a schedule, and include typosquat checks in dependency-review for new packages.

## Expected outputs

- npm/PyPI new-package monitoring with ecosystem-aware similarity checks.
- Metadata-analysis checklist: install scripts, setup.py, maintainer history, normalization tricks.
- Lockfile/build-history hunt procedure for typosquat exposure.
- Install-time gates per ecosystem and takedown/reporting runbook.

## Pitfalls

- PyPI's name normalization (dash/underscore/case equivalence) creates typosquat variants invisible to naive string comparison — account for it.
- setup.py executes on install — a malicious PyPI package needs no further action to compromise the installer.
- npm scoped packages don't fully prevent dependency confusion — configure scopes explicitly.
- Developers installing with --extra-index-url or public registries bypass proxy gates — enforce via policy and CI checks.
- Feed-only monitoring misses targeted typosquats nobody reported — pair feeds with your own similarity monitoring.

## References

- npm documentation: install scripts, package-lock; PyPI documentation: package security, reporting malware; MITRE ATT&CK T1195.002 — https://attack.mitre.org/techniques/T1195/002/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
