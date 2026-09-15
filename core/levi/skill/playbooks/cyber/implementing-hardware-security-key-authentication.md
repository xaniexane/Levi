---
skill_id: cyber_implementing_hardware_security_key_authentication
name: Hardware Security Key Authentication
description: Roll out phishing-resistant authentication with FIDO2 security keys across the organization.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication]
version: 1.0.0
---
## Purpose
Passwords get phished, SMS codes get intercepted, push notifications get fatigue-approved — but
FIDO2 security keys (YubiKey and equivalents) are phishing-resistant by design: the credential is
bound to the origin, so a fake login page can't use it. This playbook rolls out hardware security
keys org-wide: procurement, enrollment, recovery, and the policy enforcement that makes "MFA"
actually mean something.

## When to use
- Eliminating phishing as an account-takeover vector (the highest-ROI identity investment).
- After credential-phishing incidents, MFA-fatigue attacks, or SIM-swap concerns.
- Meeting phishing-resistant MFA requirements (EO 14028, OMB M-22-09, cyber-insurance, PCI DSS 4.0).
- Protecting privileged users first, then the general population.
- As the authentication foundation of zero trust (AAL3 where needed).

## Prerequisites
- Key procurement: FIDO2-certified keys (USB-C/NFC/Lightning per device mix), two per user (primary
  + backup — non-negotiable).
- IdP/application support inventory: which systems support FIDO2/WebAuthn vs. need alternatives.
- Enrollment infrastructure: in-person or verified-remote enrollment with identity proofing.
- Recovery and helpdesk procedures written before rollout (lost keys will happen on day two).
- Executive sponsorship: this changes daily login for everyone — leadership must go first.

## Procedure
1. **Start with privileged users and executives.** Enroll IT admins, super-admins, executives, and
   finance first — the most targeted and most impactful. Require security keys for all privileged
   access (no fallback to weaker MFA for admins). Their adoption sets the cultural tone and protects
   the highest-risk accounts immediately.
2. **Procure and distribute properly.** Two keys per user (one primary, one backup stored safely — a
   single key is a lockout waiting to happen). Choose form factors matching the device fleet (USB-C,
   NFC for mobile). Distribute via verified channels (in-person, manager handoff, or shipped with
   identity verification) — keys are trust anchors; the supply chain matters.
3. **Enroll with identity proofing.** Enrollment binds the key to the identity: verify the person
   (in-person or strong remote proofing), register both keys, and confirm successful authentication
   before closing the enrollment. Document the enrollment event — it's the trust root of everything
   after.
4. **Enforce phishing-resistant MFA in policy.** Configure IdPs and apps: require FIDO2 (not "any
   MFA") for target populations; disable or restrict weaker methods (SMS off, push with
   number-matching only as fallback during transition, then off). "MFA enforced" with SMS allowed is
   not phishing-resistant — the policy must name the method.
5. **Build the lost/broken-key workflow.** Self-service + helpdesk: user reports lost key → identity
   re-verified → lost key revoked → backup key promoted → replacement issued. Target: restore access
   within hours without weakening verification. Test the workflow before rollout — the first lost
   key shouldn't be a process discovery exercise.
6. **Handle the edge cases.** Shared workstations (per-user keys, no shared keys), travelers (backup
   key travels separately from primary), mobile-only users (NFC/platform authenticators), and
   service accounts (keys don't fit — use workload identity instead). Each gets a documented path,
   not an ad-hoc exception.
7. **Plan for platform authenticators.** Where appropriate, supplement with platform authenticators
   (Windows Hello, Touch ID, Android) as phishing-resistant options — same WebAuthn standard, no
   extra hardware. Define which authenticator types are allowed per assurance level; keep hardware
   keys mandatory for privileged tiers.
8. **Monitor authentication telemetry.** Track: FIDO2 usage rate vs. weaker methods, enrollment
   completion, lost-key events, and authentication failures (possible attacks or usability issues).
   Alert on: sudden fallback to weaker MFA, mass enrollment anomalies, and admin MFA-policy changes.
9. **Roll out in waves with support.** After privileged users: departments in waves, with
   floor-walker support during each wave's first week, clear instructions (with pictures), and a
   feedback channel. Measure enrollment and login-success rates per wave; fix UX issues before the
   next wave.
10. **Mature to passwordless.** Once keys are universal, move toward passwordless (FIDO2 as primary,
    password removed or de-emphasized) for the best UX and security combination. Report:
    phishing-resistant MFA coverage percent, account-takeover incidents before/after, and helpdesk
    load — the metrics that justify the program.

## Expected outputs
- Security keys procured (two per user) and enrolled for privileged users first, then org-wide in
  waves.
- IdP/app policies requiring FIDO2 (weaker methods disabled or restricted) with enforcement
  verified.
- Lost-key recovery workflow tested; edge cases (shared stations, travelers, mobile) documented.
- Authentication telemetry: usage rates, enrollment, anomalies, policy-change alerting.
- A passwordless roadmap with coverage and incident-reduction metrics.

## Pitfalls
- One key per user: loss means lockout or weak recovery. Two keys, always.
- "MFA enforced" allowing SMS: the policy must require phishing-resistant methods specifically, or
  attackers just use the weakest allowed.
- No recovery workflow: the first lost keys create chaos and pressure for weak fallbacks. Build
  recovery before rollout.
- Skipping executives: if leadership won't use keys, nobody will. Executives enroll first — visibly.
- Treating keys as the whole identity program: lifecycle (joiner/mover/leaver), conditional access,
  and session management still matter. Keys are the authentication layer, not the entire program.

## References
- FIDO Alliance: FIDO2 / WebAuthn specifications and deployment guidance
- NIST SP 800-63B (authenticator assurance levels — AAL3)
- CISA guidance on phishing-resistant MFA
- Vendor documentation for the chosen keys and IdP WebAuthn configuration
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
