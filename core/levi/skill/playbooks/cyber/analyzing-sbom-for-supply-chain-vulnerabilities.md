# Analyzing SBOMs for Supply Chain Vulnerabilities

See also: analyzing-supply-chain-malware-artifacts.md

## Purpose

Take a Software Bill of Materials (SBOM) for a product, image, or application and turn it into an
actionable vulnerability picture: which components carry known CVEs, which are end-of-life or
abandoned, which violate organizational policy, and where the SBOM itself is incomplete or
untrustworthy. The goal is prioritized remediation, not a raw vulnerability dump.

A secondary purpose is SBOM quality assessment. A vendor SBOM that omits transitive dependencies or
lists phantom components is itself a supply-chain risk signal, and this playbook treats the
document's trustworthiness as a first-class finding.

## When to use

- A vendor delivers an SBOM with a new product or update and you must validate it before deployment.
- You own software built from third-party dependencies and need continuous supply-chain risk
  monitoring.
- A new high-severity CVE drops and you need to know within the hour which systems are exposed.
- Procurement or compliance (e.g., executive-order-style SBOM mandates) requires a documented
  component-risk review.
- Evaluating a vendor's security maturity during selection: SBOM quality correlates with engineering
  discipline.

## Prerequisites

- Written authorization from the asset owner or security leadership to scan the SBOM and associated
  artifacts; include scope boundaries (which products, which environments) and data-handling rules
  for vendor-supplied documents.
- The SBOM itself in a machine-readable format (SPDX JSON/XML or CycloneDX JSON/XML). If you only
  have a PDF, convert and validate it first — manual review of prose SBOMs is error-prone.
- An inventory of where the SBOM applies: build version, deployment targets, and contact for the
  build/release team.
- Chain-of-custody notes: who supplied the SBOM, when, and the hash of the file you analyzed, so
  findings can be traced back to the exact document version.
- Access to the build artifacts or deployed image if you plan the independent completeness check —
  coordinate with engineering so the comparison uses the same build.

## Procedure

1. Validate the SBOM structurally. Run it through a format validator (e.g., the SPDX or CycloneDX
   validation tooling) and confirm: every component has a name, version, and a package identifier
   (PURL or CPE where available); the document declares its own version and the software version it
   describes; and dependency relationships are present rather than a flat component list.
2. Measure completeness against ground truth. Compare the SBOM's component list with an
   independently generated one (e.g., generate your own with Syft from the same image or build
   tree). Flag components present in reality but missing from the vendor SBOM, and vice versa.
   Record the delta explicitly — a vendor SBOM that omits half the transitive dependencies is itself
   a finding.
3. Scan components against vulnerability data. Feed the SBOM into a scanner (Grype,
   Dependency-Track, or OSV-Scanner) configured with current CVE feeds. Capture the full result set
   with CVE IDs, CVSS scores, and the fixed versions, preserving the scanner version and feed
   timestamps for reproducibility.
4. Enrich with exploitability context. For each high/critical CVE, check: known-exploited catalogs
   (e.g., CISA KEV), whether the vulnerable code path is actually reachable in your deployment, and
   whether VEX (Vulnerability Exploitability eXchange) statements exist from the vendor. A critical
   CVE in an unused optional module is not the same risk as one in the request path.
5. Identify stale and abandoned components. Flag components with no upstream release in the last 24
   months, archived repositories, or known end-of-life announcements. Abandoned components are
   future CVEs with no one to fix them.
6. Apply policy checks. Compare the component list against organizational rules: license
   allowlists/denylists, prohibited countries of origin if policy requires it,
   minimum-maintainer-activity thresholds, and banned packages. Document each violation with the
   policy clause it breaches.
7. Verify signatures and provenance where available. If components carry SLSA provenance or Sigstore
   signatures, verify them (`cosign verify` against the vendor's published identity); if the SBOM is
   signed, verify that too. Unsigned provenance is a data-quality note, not a vulnerability, but
   record it.
8. Check transitive and build-time dependencies separately. Direct dependencies get the attention;
   transitive ones carry the surprises. Also distinguish runtime components from build-only tooling
   — a CVE in a build plugin has a different blast radius than one in a shipped library, and
   conflating them inflates the report.
9. Prioritize and assign. Rank findings by (exploitability × exposure × blast radius), not CVSS
   alone. For each: affected component/version, deployed locations, recommended action (upgrade,
   patch, replace, accept with compensating control), and owner. Set dates.
10. Wire the SBOM into the build gate. For software you build: fail or warn the CI pipeline on new
    critical CVEs or policy violations at SBOM-generation time, so the next release cannot silently
    regress. Record the gate thresholds alongside the report.
11. Track vendor remediation SLAs. For vendor-supplied SBOMs, log each finding against the vendor
    ticket, the contractual or committed fix timeline, and the compensating control in place while
    you wait. Escalate misses through procurement, not just engineering.
12. Deliver and file. Produce the report for the asset owner and security leadership, store the
    SBOM, the scan outputs, feed versions, and the report under the case/asset record with hashes,
    and schedule the next review (or hand the SBOM to the continuous-monitoring pipeline).

## Key tools & commands

- Syft (Anchore) for independent SBOM generation: `syft packages <image-or-dir> -o cyclonedx-json >
  baseline.cdx.json`.
- Grype for CVE matching against an SBOM: `grype sbom:vendor-sbom.json -o json >
  grype-results.json`. Pair with `grype db check` / `grype db update` to know your feed freshness.
- OSV-Scanner as an alternative matcher: `osv-scanner --sbom=vendor-sbom.json --format json`.
- Dependency-Track for continuous monitoring: upload the SBOM to a project and let it correlate
  against NVD/GitHub advisories on a schedule.
- Cosign (Sigstore) for signature verification: `cosign verify --key vendor.pub artifact` and
  `cosign verify-blob` for signed SBOM documents.
- `jq` for SBOM surgery, e.g. listing components missing a PURL: `jq '.components[] | select(.purl
  == null) | .name' sbom.json`.
- SPDX and CycloneDX online/schema validators for the structural check in step 1.

## Expected outputs

- A validation report: SBOM format, schema compliance, identifier coverage (name/version/PURL/CPE),
  relationship completeness.
- A completeness delta: independently generated SBOM vs. vendor SBOM, with missing/extra components
  listed.
- A vulnerability result set with CVE IDs, CVSS, fixed versions, scanner version, and feed
  timestamps.
- An exploitability-enriched, prioritized remediation list with owners and dates.
- Policy-violation findings mapped to specific policy clauses.
- Provenance/signature verification results.
- CI gate thresholds (for owned builds) and vendor SLA tracking (for vendor SBOMs).
- The full evidence bundle (SBOM, scans, report) hashed and filed under the asset record.

## Pitfalls

- Treating CVSS as risk: a 9.8 in an unreachable test dependency will drown out a reachable 7.5.
  Always apply reachability and exposure.
- Trusting the vendor SBOM without the completeness check — the most dangerous component is the one
  nobody listed.
- Stale feeds: a Grype or Dependency-Track database weeks out of date will miss the CVE that matters
  this week. Record feed dates in every report.
- Confusing SBOM formats: SPDX and CycloneDX have different required fields; a "valid JSON" file can
  still be a semantically broken SBOM.
- Acting on scanner output without verifying the fixed version actually resolves the finding in your
  deployment configuration.
- Counting build-time-only CVEs as shipped risk: separate the build graph from the runtime graph
  before prioritizing.
- VEX statements taken at face value: a vendor "not affected" claim deserves a spot check against
  your actual deployment configuration.

## References

- NTIA "The Minimum Elements for a Software Bill of Materials (SBOM)" — the baseline for SBOM
  completeness.
- SPDX specification and CycloneDX specification — authoritative field definitions for the
  structural check.
- CISA Known Exploited Vulnerabilities (KEV) catalog — exploitability context.
- SLSA (Supply-chain Levels for Software Artifacts) framework — provenance verification concepts.
- OWASP Software Component Verification Standard (SCVS) — component-assurance criteria.
- Sigstore/Cosign documentation — signature verification workflows.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
