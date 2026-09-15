---
skill_id: cyber_implementing_bgp_security_with_rpki
name: BGP Security with RPKI
description: Secure BGP routing with RPKI origin validation, prefix filtering, and hijack monitoring.
risk: low
permissions: []
requires_confirmation: false
tags: [network, bgp]
version: 1.0.0
---
## Purpose
BGP trusts by default: anyone can announce anyone's prefixes, enabling hijacks that redirect traffic
through attacker infrastructure (for interception, DDoS, or impersonation). Resource Public Key
Infrastructure (RPKI) adds cryptographic authorization — Route Origin Authorizations (ROAs) stating
which AS may originate which prefixes — so routers can reject invalid announcements. This playbook
implements RPKI origin validation plus the complementary BGP hygiene that makes hijacks hard and
visible.

## When to use
- Operating your own ASNs and IP space (ISP, hosting provider, large enterprise, cloud customer with
  BYOIP).
- After route-leak or hijack incidents affecting your prefixes or your providers.
- Meeting contractual or regulatory expectations for routing security (e.g., telecom, finance).
- As part of a network-security hardening program alongside DDoS mitigation.
- When your prefixes are high-value targets (financial services, government, major SaaS).

## Prerequisites
- Authority over your IP resources: RIR (ARIN/RIPE/APNIC/LACNIC/AFRINIC) account access to create
  ROAs.
- BGP-speaking routers supporting RPKI/RTR (most modern platforms do — verify OS versions).
- An RPKI validator deployment (Routinator, rpki-client, OctoRPKI) or a managed RPKI service.
- Upstream/transit provider coordination: confirm they honor RPKI or at least your prefix filters.
- Monitoring for BGP announcements of your space (BGPStream, RIPE RIS, or commercial route
  monitoring).

## Procedure
1. **Inventory your address space and ASNs.** List every prefix you originate, from every ASN,
   including anycast and BYOIP in clouds. Reconcile against RIR records — stale or undocumented
   announcements are your first cleanup target.
2. **Create ROAs for all originated prefixes.** In your RIR's portal, publish Route Origin
   Authorizations binding each prefix to its authorized origin AS, with correct maxLength (as
   specific as your actual announcements — overly loose maxLength enables sub-prefix hijacks).
   Include ROAs for all more-specifics you announce.
3. **Deploy RPKI validators.** Run redundant validators (two instances minimum, different networks)
   syncing the RPKI repository and serving validated data to routers over RTR. Monitor validator
   health: stale data is worse than no data if routers trust it.
4. **Enable origin validation on routers.** Configure BGP origin validation (RFC 6483) with a reject
   or de-preference policy for RPKI-invalid routes. Start in log/de-preference mode to catch ROA
   errors (yours and others'), then move to reject-invalid after a burn-in period.
5. **Fix your own ROA errors first.** Monitor for your prefixes showing as invalid (usually
   maxLength or ASN mistakes). An invalid ROA gets your traffic dropped by validating networks
   worldwide — treat ROA correctness as production-critical config.
6. **Implement prefix filtering with peers and customers.** Apply prefix-lists: accept from
   customers only their registered prefixes, from peers only expected ranges; filter bogons, overly
   specific prefixes (beyond /24 IPv4, /48 IPv6 typically), and your own prefixes arriving from
   unexpected directions.
7. **Deploy BGP monitoring and alerting.** Alert on: your prefixes announced by unauthorized ASNs,
   unexpected more-specifics of your space, origin changes, and RPKI validation state flips to
   invalid. Route alerts to network operations with an incident runbook.
8. **Write the hijack response runbook.** Steps: confirm via multiple vantage points (not a single
   monitor), contact the offending AS's NOC and your upstreams, announce more-specifics of your own
   prefixes to win back traffic, engage your RIR if resources are abused, and consider legal/abuse
   channels for persistent hijacks. Time matters — rehearse.
9. **Coordinate with upstreams and peers.** Confirm your transit providers perform RPKI validation
   and prefix filtering; request their filtering policies in writing. A provider that accepts
   invalid routes undermines your local validation for inbound traffic.
10. **Maintain continuously.** Review ROAs quarterly and on every network change (new prefixes, ASN
    changes, decommissioned space — remove stale ROAs). Track RPKI adoption metrics: percent of your
    prefixes covered by valid ROAs, invalid-route reject counts, and hijack-alert MTTR.

## Expected outputs
- ROAs published for 100% of originated prefixes with correct maxLength.
- Redundant RPKI validators serving routers; origin validation enforcing reject-invalid.
- Prefix filters on customer, peer, and upstream sessions; bogon filtering.
- BGP monitoring with hijack alerting and a rehearsed response runbook.
- Quarterly ROA review cadence and adoption metrics.

## Pitfalls
- Loose maxLength on ROAs: authorizes sub-prefix hijacks up to the maxLength. Set it to the most
  specific prefix you actually announce.
- Skipping the burn-in: going straight to reject-invalid with ROA errors will blackhole your own
  traffic at validating networks. Log first, then enforce.
- Single validator: validator outage or stale cache blinds all routers. Run redundant validators and
  monitor their freshness.
- Forgetting IPv6: hijackers use whichever family you neglected. Cover v6 prefixes, filters, and
  monitoring equally.
- No hijack runbook: discovering a hijack without a plan wastes the critical first hour.
  More-specific announcements and upstream contacts must be pre-staged.

## References
- RFC 6480-6493 series (RPKI architecture and origin validation), RFC 6811 (BGP origin validation)
- NIST SP 800-189 (resilient interdomain traffic exchange / BGP security)
- MANRS (Mutually Agreed Norms for Routing Security) actions for network operators
- RIPE NCC RPKI documentation and best practices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
