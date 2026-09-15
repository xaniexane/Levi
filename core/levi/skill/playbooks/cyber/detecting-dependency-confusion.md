---
skill_id: cyber_detecting_dependency_confusion
name: Detecting Dependency Confusion
description: Detect dependency-confusion attacks on package managers with namespace monitoring and pipeline verification.
risk: info
permissions: []
requires_confirmation: false
tags: [supply-chain, detection, devsecops]
version: 1.0.0
---
## Purpose

Detect dependency confusion — attackers publishing malicious packages with the same names as your private packages on public registries, so your builds pull the attacker's code. This supply-chain attack is silent, high-impact, and fully preventable with the right pipeline controls.

## When to use

- Securing build pipelines that mix private and public package registries (npm, PyPI, Maven, NuGet, RubyGems).
- Auditing dependency resolution order in CI/CD.
- Investigating a suspected supply-chain compromise via package manager.
- Validating artifact-repository (Artifactory, Nexus) configuration.

## Prerequisites

- Inventory of private package names across all ecosystems in use.
- Control over package-manager and CI configuration (registries, scopes, resolution order).
- An artifact repository manager (preferred) or strict registry configuration.
- SBOM generation for builds to detect unexpected package sources.

## Procedure

1. **Inventory private package names.** List every internal package name in every ecosystem (npm, PyPI, etc.). These names are the attack surface — any of them that doesn't exist on the public registry is claimable by an attacker. This inventory is the foundation of all detection.
2. **Claim or reserve the names.** For each private package name, check whether it exists on the public registry. Where it doesn't, publish a placeholder (or reserve the name per the registry's mechanism) so attackers can't claim it. This is the single most effective preventive control — do it before anything else.
3. **Enforce scoped and private-first resolution.** Configure package managers to resolve private scopes/namespaces only from the private registry: npm scopes (`@company`), pip `--index-url` with private-first, Maven repository ordering with private repos first, NuGet source mapping. Never let the resolver fall through to public registries for private names.
4. **Detect confusion attempts in the pipeline.** Alert on: packages resolved from unexpected registries (log and verify the registry source of every resolved package), version anomalies (a private package suddenly resolving to a much higher public version — the attacker's version), and new packages appearing in lockfiles that weren't explicitly added. SBOM comparison between builds catches the substitution.
5. **Monitor public registries for your names.** Set up monitoring (manual or automated) for new public packages matching your private names or typosquats of them. If an attacker claims a name you missed, early detection limits the exposure window. Treat any such publication as a security incident, not a coincidence.
6. **Audit historical builds.** Retroactively check: have any past builds resolved private names from public registries? Examine CI logs and lockfiles for registry sources. If confusion already happened, scope it like a supply-chain incident — which builds, which deployments, what did the malicious package do?
7. **Lock the pipeline.** Require lockfiles committed and verified in CI, verify package hashes/signatures on install, use the artifact repository as the single source of truth (proxying public registries with caching), and alert on any direct-to-public-registry resolution in CI. The pipeline should be unable to be confused, not just monitored for confusion.

## Expected outputs

- A complete private-package-name inventory with public-registry claims/reservations.
- Scoped, private-first resolver configuration across all ecosystems and CI.
- Pipeline detections for unexpected registries, version anomalies, and lockfile changes; locked-down artifact flow.

## Pitfalls

- Unclaimed private names on public registries — the attack is one `npm publish` away.
- Resolver fall-through to public registries — the default configuration in most ecosystems.
- No lockfiles or unverified lockfiles — builds resolve floating versions from anywhere.
- Monitoring without claiming — detection is good; prevention by reservation is better.
- Forgetting the less-common ecosystems — attackers check RubyGems and NuGet too.

## References

- The original dependency-confusion research (published disclosure) for attack mechanics
- OWASP Software Supply Chain guidance
- NIST SP 800-161 (Cybersecurity Supply Chain Risk Management)
- Package-manager documentation on scopes, registries, and resolution order (npm, pip, Maven)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
