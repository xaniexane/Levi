---
skill_id: cyber_implementing_supply_chain_security_with_in_toto
name: Implementing Supply-Chain Security with in-toto
description: Use in-toto layouts and link metadata to verify each step of the software supply chain.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, in-toto, build-integrity]
version: 1.0.0
---
## Purpose
This playbook shows how to apply the in-toto framework to a build pipeline: defining the expected steps (layout), collecting signed evidence for each step (link metadata), and verifying the final product against the layout before release.

## When to use
- You need evidence that every build step ran on the expected system, in order, by the expected actor.
- Customers or auditors ask for verifiable build provenance beyond "trust our CI".
- Complementing SLSA or Sigstore adoption with step-level verification.

## Prerequisites
- A documented build pipeline with discrete, ordered steps (fetch, build, test, package, sign).
- Key material or OIDC identities for each functionary (the humans or systems performing steps).
- A verification point: release gate, admission controller, or customer-side verifier.

## Procedure
1. **Model the pipeline as a layout.** Write the in-toto layout: ordered steps, which functionaries may perform each, expected materials and products per step, and inspections to run at verify time.
2. **Instrument each step.** Wrap build steps so they emit link metadata: what went in (materials with hashes), what came out (products with hashes), the command run, and the environment.
3. **Sign link metadata.** Have each functionary sign its link files with its key or OIDC-bound identity; store signatures alongside the metadata.
4. **Verify before release.** At the release gate, run verification: layout signature valid, every required step has valid link metadata from an authorized functionary, artifact hashes match across steps, inspections pass.
5. **Bind verification to deployment.** Reject artifacts that fail verification; surface the failing step and functionary so remediation is targeted.
6. **Rotate and revoke deliberately.** Update the layout when the pipeline changes, and maintain a revocation path for compromised functionary keys.
7. **Archive evidence.** Retain layouts and link metadata with the release for audit and incident response.

8. **Handle pipeline exceptions.** Define how hotfixes and emergency builds produce valid link metadata; an undocumented bypass becomes the attacker's favorite path.
9. **Integrate with artifact signing.** Combine in-toto verification with Sigstore signing so each verified step's output is also tamper-evident in storage.

## Expected outputs
- Signed in-toto layout matching the real pipeline, under version control.
- Per-release link metadata bundle and a verification report.
- Release gate that blocks unverifiable artifacts.
- Example: a release where the layout requires signed link metadata from the build, test, and package steps; verification fails the release when the test step's metadata is missing, pointing exactly at the gap.

## Pitfalls
- A layout that does not match the actual pipeline fails verification on every legitimate build.
- Unsigned or loosely-scoped functionary keys let an attacker forge a step.
- Treating in-toto as a checkbox: the value is the verification gate, not the metadata collection.

- Layouts that pin exact tool versions and break every legitimate build when the toolchain updates; pin the properties that matter for security, not every byte.
- Verifying signatures but not checking that the signing identity matches the expected functionary for that step.

## References
- in-toto documentation (in-toto.io; in-toto.github.io/docs).
- SLSA framework (slsa.dev).
- NIST SP 800-204D, Strategies for the Integration of Software Supply Chain Security.
- CNCF Software Supply Chain Best Practices (github.com/cncf/tag-security — supply chain guidance).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
