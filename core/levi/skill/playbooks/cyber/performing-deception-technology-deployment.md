---
skill_id: cyber_performing_deception_technology_deployment
name: Deception Technology Deployment
description: Deploy honeypots, honeytokens, and decoy assets to detect intruders early and study their behavior.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, deception, monitoring]
version: 1.0.0
---

## Purpose

Deception flips the asymmetry: instead of finding the attacker's needle in your haystack, you plant needles that only an attacker would touch. Honeypots (decoy systems), honeytokens (fake credentials, documents, API keys), and canary assets generate high-fidelity alerts because legitimate users have no reason to interact with them. This playbook covers designing, deploying, and operating deception: placement strategy, realistic decoys, alerting, and the legal/operational guardrails that keep deception safe and useful.

## When to use

- Early-warning detection for lateral movement and insider threats.
- Environments where traditional detection has blind spots (OT networks, legacy segments).
- Studying attacker behavior safely during an active intrusion (what are they after?).
- Validating that your SOC actually investigates alerts (deception trips are controlled tests).
- High-value asset protection: placing tripwires around crown-jewel systems and data.

## Prerequisites

- Network segments where decoys can be placed without confusing legitimate users or automation (decoys in the middle of production workflows generate noise).
- Alerting pipeline: deception alerts must reach the SOC with context and priority, not vanish into a separate console.
- Legal review: entrapment is a law-enforcement concept, but liability for attacker actions launched from your honeypot is real — design decoys that cannot be weaponized.
- Realistic-but-fake content: decoy documents, credentials, and systems must be convincing yet clearly non-production to your own staff.
- Maintenance ownership: stale, obviously-fake decoys teach attackers to ignore them.

## Procedure

1. **Define what you want to learn.** Deception goals differ: detect lateral movement (decoy servers in server VLANs), catch credential theft (honeytokens in memory/registry), detect data theft (canary documents in file shares), or identify insider snooping (decoy HR/finance records). One goal per deployment keeps design coherent.
2. **Place decoys where attackers go.** Position honeypots along likely attack paths: a decoy admin workstation in the IT VLAN, a fake database server near real ones, honeytokens (fake AWS keys, database credentials) in places attackers harvest — CI configs, wikis, memory of jump hosts. Decoys nobody can reach detect nothing.
3. **Make decoys believable but sterile.** Populate with plausible data: recent timestamps, realistic file names, convincing service banners. Never use real credentials, real customer data, or routable paths to production — a convincing decoy built from real secrets is a real vulnerability.
4. **Harden the decoys themselves.** Honeypots must not become attack platforms: isolate them at the network layer (no outbound internet except logged sinkholes), keep them patched, and monitor them for compromise. A honeypot the attacker pivots from is a liability, not an asset.
5. **Tune alerting for fidelity.** Any interaction with a decoy is suspicious by design, so alert immediately — but include context: source IP, user, the exact decoy touched, and the action. Route deception alerts at high priority; their false-positive rate should be near zero, and any noise indicates a placement problem.
6. **Respond to trips as incidents.** A touched honeytoken means someone is harvesting credentials or moving laterally: initiate your incident process, preserve the decoy's logs, and use the interaction to learn the attacker's interests (which decoys, in what order) before containing.
7. **Rotate and refresh.** Change decoy credentials, documents, and host identities periodically. Attackers who map your deception will avoid it; freshness preserves the uncertainty that makes deception work.
8. **Measure effectiveness.** Track: time from deployment to first trip, trips per quarter, true-positive rate, and incidents where deception provided the earliest detection. Report these to justify the operational overhead.

## Expected outputs

- A deception design: goals, decoy types, placement map, and alerting flow.
- Deployed honeypots, honeytokens, and canary assets with documented (fake) content.
- High-priority alerting pipeline from deception platform to SOC.
- Response procedures for deception trips, integrated with incident response.
- Effectiveness metrics: detection latency, trip rates, true-positive rates.

## Pitfalls

- Decoys in production workflows that legitimate automation touches — every false trip erodes trust in the alerts.
- Using real data or credentials in decoys, converting a detection asset into an exposure.
- Honeypots with outbound internet access becoming attack infrastructure with your name on it.
- Deploying deception without SOC integration; alerts nobody reads are decoration.
- Static decoys: attackers fingerprint and avoid stale honeypots, so refresh is mandatory.

## References

- MITRE Engage (defensive deception and adversary engagement framework)
- NIST SP 800-160 Vol. 2 (cyber resiliency techniques, including deception)
- Honeynet Project documentation and honeypot deployment guidance
- SANS guidance on deception technology operations
- Vendor-agnostic canary-token concepts (tripwire credentials and documents)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
