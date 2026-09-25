---
skill_id: cyber_generating_and_analyzing_sboms
name: Generating and Analyzing SBOMs
description: Generate software bills of materials for your software inventory and analyze them for vulnerable components and supply-chain risk.
risk: info
permissions: []
requires_confirmation: false
tags: [supply-chain, vulnerability-management, sdlc]
version: 1.0.0
---
## Purpose

A software bill of materials (SBOM) lists every component in a piece of
software — the inventory you need when the next Log4Shell drops and the
question is "where are we exposed?" This playbook covers generating SBOMs
in standard formats (SPDX, CycloneDX), analyzing them for known
vulnerabilities, and using them for procurement and incident response.

## When to use

- Building the software-component inventory required by supply-chain
  security programs and (for US federal suppliers) EO 14028 expectations.
- Responding to a widely exploited library vulnerability: SBOMs answer
  "are we affected" in minutes instead of days.
- Procurement and vendor risk: requesting and evaluating supplier SBOMs.
- CI/CD integration: generating an SBOM per build as a release artifact.

## Prerequisites

- Tooling for SBOM generation (e.g. Syft, or language-ecosystem tools)
  and for vulnerability matching against component data.
- An inventory of in-scope software: first-party builds, container
  images, and procured applications.
- Access to vulnerability data sources (OSV, NVD, vendor advisories)
  for analysis.
- Defined SBOM format policy: SPDX and CycloneDX are the two standard
  formats — pick based on ecosystem and consumer needs.

## Procedure

1. **Choose the format and tooling.** Standardize on CycloneDX or SPDX
   (both are NTIA-recognized). Select generators that cover your
   artifact types: container images, language package manifests,
   binaries, and firmware where applicable.
2. **Generate SBOMs per build.** Integrate generation into CI/CD so
   every release produces a signed SBOM artifact alongside the binary.
   Include transitive dependencies — direct-only SBOMs miss the
   components attackers actually target.
3. **Collect supplier SBOMs.** Request SBOMs from vendors for procured
   software; validate that they are machine-readable, complete, and
   current rather than marketing documents.
4. **Analyze for known vulnerabilities.** Match component name+version
   against vulnerability databases (OSV, NVD). Triage results by
   reachability and exploitability, not raw CVE counts — an unreachable
   vulnerable function is lower priority than a reachable one.
5. **Enrich with VEX.** Where analysis shows a CVE does not affect your
   deployment (component not reachable, mitigated by configuration),
   record a VEX (Vulnerability Exploitability eXchange) statement so
   future scans do not re-raise the same false positive.
6. **Use SBOMs in incident response.** When a component vulnerability
   goes critical, query the SBOM inventory for affected products and
   versions first — this compresses scoping from days to minutes. Feed
   results directly into patch prioritization.
7. **Monitor for drift.** Re-generate and diff SBOMs on dependency
   updates; alert on newly introduced components with known critical
   CVEs or from unexpected suppliers/registries (typosquatting,
   dependency-confusion signals).
8. **Govern the program.** Define SBOM retention, signing, distribution
   (who may receive them — SBOMs aid attackers too), and review cadence.
   Measure coverage: percentage of in-scope software with current SBOMs.

## Expected outputs

- SBOMs in the standard format for in-scope software, generated per
  build and signed.
- A vulnerability-analysis report per SBOM with triaged, reachability-
  aware findings.
- VEX statements for non-affected CVEs.
- An incident-response query capability: component → affected products.
- Program metrics: SBOM coverage, mean time to answer "are we affected".

## Pitfalls

- SBOMs enumerate components, not exploitability — raw CVE counts
  without reachability analysis create noise and burnout.
- Incomplete SBOMs (direct deps only, stale versions) give false
  confidence — validate completeness and freshness.
- SBOMs are sensitive: they tell an attacker exactly which vulnerable
  versions you run — control distribution.
- Vulnerability databases lag and conflict — correlate OSV, NVD, and
  vendor advisories rather than trusting one source.
- Supplier SBOMs vary wildly in quality — validate before relying on
  them in procurement decisions.

## References

- NTIA: "The Minimum Elements for a Software Bill of Materials"
- CycloneDX and SPDX specification documentation
- CISA: SBOM-related guidance and VEX documentation
- NIST SP 800-161: Cybersecurity Supply Chain Risk Management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
