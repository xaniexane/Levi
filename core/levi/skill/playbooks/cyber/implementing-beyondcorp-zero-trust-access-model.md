---
skill_id: cyber_implementing_beyondcorp_zero_trust_access_model
name: BeyondCorp-Style Zero Trust Access
description: Implement a BeyondCorp-style access model: identity- and device-aware proxies replacing network trust.
risk: info
permissions: []
requires_confirmation: false
tags: [zero-trust, access]
version: 1.0.0
---
## Purpose
BeyondCorp (Google's zero-trust model) proved that corporate networks don't need privileged
perimeters: every access decision is made per-request from identity, device state, and context,
enforced by an access proxy. This playbook implements that model: inventory services, deploy
identity-aware proxies, assess device trust, and migrate users off VPN — removing network location
as a trust signal.

## When to use
- Replacing VPN-centric remote access with zero-trust application access.
- After incidents where VPN credentials or flat-network access enabled lateral movement.
- Supporting BYOD or contractor access without extending the corporate network to untrusted devices.
- As the architectural target for a zero-trust program (pairs with the CISA ZTMM playbook for
  maturity tracking).
- When auditors or customers ask how you enforce least privilege for remote access.

## Prerequisites
- A strong identity provider (IdP) with MFA enforced — identity is the new perimeter, so IdP
  compromise is total compromise.
- Device inventory and management (MDM/EDR) to assess device trust signals.
- An access-proxy solution: Google's BeyondCorp Enterprise, or equivalents (Cloudflare Access,
  Zscaler Private Access, Pomerium, or IdP-native app proxies).
- Application inventory: which internal apps exist, who uses them, and their current access path.
- Executive sponsorship: this changes how everyone works daily; without it, exceptions will hollow
  out the model.

## Procedure
1. **Inventory applications and access paths.** Catalog internal applications: URL, auth method,
   user population, data sensitivity. Map how each is reached today (VPN, office network, public).
   This inventory drives the migration order.
2. **Establish identity as the primary control.** Enforce phishing-resistant MFA (security keys
   preferred) for all users at the IdP. Clean up stale accounts and enforce least-privilege group
   memberships — the proxy will trust IdP assertions completely.
3. **Define device trust tiers.** Tier 1: managed, encrypted, EDR-healthy corporate devices (full
   access). Tier 2: managed but non-compliant or personal devices with MDM (limited access). Tier 3:
   unknown devices (no access to sensitive apps). Emit these signals from your device management to
   the proxy.
4. **Deploy the access proxy.** Place the identity-aware proxy in front of applications
   (reverse-proxy or connector model). Configure per-app policies: required identity group + device
   tier + context (managed device, current OS). Start with low-risk apps to prove the pattern.
5. **Migrate applications in waves.** Wave 1: IT tools and low-sensitivity apps. Wave 2: general
   business apps. Wave 3: sensitive apps (finance, HR, production admin) with the strictest
   policies. Each wave: dual-run period, user communication, then cutover with rollback plan.
6. **Decommission network-based trust.** As apps migrate, remove their VPN-only access paths and
   internal-network exemptions. The goal: no application trusts "came from the office network."
   Track the count of apps still requiring VPN — drive it to zero.
7. **Log every access decision.** The proxy must log: identity, device signals, policy evaluated,
   decision, and timestamp — shipped to the SIEM. These logs are both the audit trail and the
   anomaly-detection feed (impossible travel, tier downgrade, off-hours sensitive access).
8. **Handle exceptions explicitly.** Legacy protocols that can't proxy (thick clients, some OT) get
   documented exceptions with compensating controls (jump hosts with MFA, time-limited firewall
   rules) and sunset plans. Exceptions are inventory items with owners, not permanent loopholes.
9. **Test the trust model adversarially.** Attempt: access from an unmanaged device with valid
   credentials (must fail for sensitive apps), a compromised-tier device (must fail or step up), and
   a valid user from an anomalous location (must trigger additional verification). Document results.
10. **Measure zero-trust maturity.** Track: percent of apps behind the proxy, percent of access
    without VPN, MFA coverage (phishing-resistant %), device-tier compliance, and policy-denial
    rates. Report progress against the CISA Zero Trust Maturity Model pillars.

## Expected outputs
- Application inventory with per-app proxy policies (identity + device + context).
- Deployed access proxy with phased migration waves and VPN decommissioning plan.
- Device trust tiers defined, signaled, and enforced.
- Comprehensive access-decision logging in the SIEM with anomaly detection.
- Maturity metrics tracked against zero-trust targets.

## Pitfalls
- Weak identity undermining everything: SMS-MFA or password-only IdP makes the proxy a gate with a
  cardboard lock. Phishing-resistant MFA first.
- Device signals nobody maintains: stale MDM data grants access to compromised devices. Device
  health must be fresh and enforced.
- Migrating apps without user communication: access changes that surprise users generate helpdesk
  floods and pressure for exemptions.
- Leaving VPN paths open "just in case": dual trust models mean the weaker one defines your
  security. Decommission aggressively.
- Treating the proxy as a VPN replacement only: the model also needs service-to-service
  authentication (workload identity) — user access is half the architecture.

## References
- Google BeyondCorp whitepapers (the original zero-trust implementation papers)
- NIST SP 800-207 (Zero Trust Architecture)
- CISA Zero Trust Maturity Model v2
- NIST SP 800-63 (digital identity guidelines, authenticator assurance levels)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
