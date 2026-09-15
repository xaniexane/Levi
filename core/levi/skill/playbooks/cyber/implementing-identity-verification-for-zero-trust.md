---
skill_id: cyber_implementing_identity_verification_for_zero_trust
name: Implementing Identity Verification for Zero Trust
description: Design identity proofing and authenticator binding (IAL/AAL) that satisfies zero trust's "never trust, always verify" requirement at enrollment and at every access decision.
risk: info
permissions: []
requires_confirmation: false
tags: [zero-trust, identity, authentication]
version: 1.0.0
---
## Purpose

Make identity the primary control plane for zero trust by ensuring the person behind a credential was rigorously verified at enrollment and re-verified continuously. This playbook maps NIST SP 800-63 identity assurance levels (IAL1–3) and authenticator assurance levels (AAL1–3) to practical enrollment, authentication, and step-up flows so that "verify explicitly" is engineered, not aspirational.

## When to use

- Designing the identity pillar of a zero-trust architecture (per NIST SP 800-207).
- Onboarding employees, contractors, or customers where account takeover would have high impact.
- Replacing weak enrollment (email-only signup, self-asserted identity) with proofed identity.
- Selecting authenticators for phishing-resistant MFA rollouts (FIDO2, PIV, smart cards).
- Responding to audit findings about inadequate identity proofing for privileged or financial access.

## Prerequisites

- Risk assessment classifying users and transactions by impact, to justify the target IAL/AAL per population.
- Legal/privacy review for collecting identity evidence (government IDs, biometrics) — requirements vary sharply by jurisdiction.
- An identity provider (IdP) that supports the chosen authenticators and can signal assurance level to relying parties (e.g., via SAML AuthnContext or OIDC `acr` claims).
- Documented enrollment channels (in-person, remote supervised, remote unsupervised) and which assurance level each can achieve.
- Fraud and help-desk procedures for exception handling — some legitimate users will always fail automated verification.

## Procedure

1. **Set target assurance levels.** Map each user population and resource tier to IAL/AAL: e.g., standard workforce IAL2/AAL2, privileged administrators IAL2/AAL3 (phishing-resistant), customer self-service IAL1/AAL1-2 depending on transaction risk. Write the matrix down and get risk-owner sign-off.
2. **Implement identity proofing for enrollment.** For IAL2: collect government-issued photo ID, validate it against issuing sources or authoritative databases, verify the document is genuine (security features, liveness-checked selfie match), and confirm address. For remote unsupervised enrollment, require liveness detection that resists presentation attacks — a static selfie is not verification.
3. **Bind authenticators at the right strength.** Enroll phishing-resistant authenticators (FIDO2 security keys, platform authenticators, PIV cards) for AAL3 populations; TOTP or push-based MFA meets AAL2 but document its phishing exposure. Bind each authenticator to the proofed identity record at enrollment, not as an afterthought.
4. **Signal assurance to relying parties.** Configure the IdP to emit `acr`/`amr` claims (OIDC) or AuthnContext (SAML) reflecting the achieved AAL, and have applications enforce step-up: a session authenticated at AAL1 cannot reach AAL3-gated resources without re-authentication.
5. **Verify continuously, not just at login.** Feed device posture, behavior analytics, and threat signals into the access decision. Trigger step-up verification on anomalies (impossible travel, new device, Tor exit, privilege escalation attempt) even mid-session, per zero-trust continuous evaluation.
6. **Handle recovery and exceptions securely.** Account recovery must meet the same IAL as enrollment — a help-desk password reset that bypasses proofing downgrades the whole system to the weakest link. Define supervised recovery workflows and log them as high-risk events.
7. **Re-verify on a schedule and on trigger.** Re-proof identities when documents expire, after long dormancy, or when fraud signals appear. De-provision authenticators promptly on role change or termination.
8. **Measure and audit.** Track proofing failure rates, help-desk recovery volumes, step-up challenge rates, and MFA bypass incidents. Audit authenticator inventories quarterly for AAL3 populations.

## Expected outputs

- Documented IAL/AAL matrix per user population and resource tier, approved by risk owners.
- Enrollment workflows achieving the target IAL, with exception-handling procedures.
- IdP configuration emitting assurance claims and applications enforcing step-up policies.
- Continuous-verification signal integrations (device posture, UEBA, threat intel).
- Metrics dashboard and quarterly assurance audit reports.

## Pitfalls

- **Weakest-link recovery.** Attackers target the help desk, not the cryptography. If recovery is easier than enrollment, your IAL is fiction.
- **Confusing MFA with identity verification.** MFA proves possession of an authenticator; it says nothing about whether the enrolled person is who they claim. Both are needed.
- **Privacy overreach.** Collecting biometrics or ID documents without a retention and minimization policy creates legal liability that outlives the security benefit.
- **One-size-fits-all AAL3.** Mandating hardware keys for every user on day one stalls adoption; phase by risk, starting with privileged and high-impact populations.
- **Ignoring the signal plumbing.** Step-up policies are useless if applications ignore `acr` claims. Verify enforcement end-to-end, not just IdP configuration.

## References

- NIST SP 800-63-4, "Digital Identity Guidelines" (covers 800-63A proofing, 800-63B authentication, 800-63C federation) — https://csrc.nist.gov/publications/detail/sp/800-63/4/final
- NIST SP 800-207, "Zero Trust Architecture" — https://csrc.nist.gov/publications/detail/sp/800-207/final
- CISA Zero Trust Maturity Model — https://www.cisa.gov/zero-trust-maturity-model
- MITRE ATT&CK T1556 (Subvert Trust Controls) — https://attack.mitre.org/techniques/T1556/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
