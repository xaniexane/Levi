---
skill_id: cyber_analyzing_ransomware_payment_wallets
name: Analyzing Ransomware Payment Wallets
description: Trace ransomware payments on-chain: clustering and exchange touchpoints.
risk: low
permissions: [network.read]
requires_confirmation: false
tags: [ransomware, blockchain]
version: 1.0.0
---
# Analyzing Ransomware Payment Wallets

See also: analyzing-ransomware-leak-site-intelligence.md, analyzing-ransomware-network-indicators.md

## Purpose

Trace cryptocurrency wallets named in ransomware extortion notes, leak-site payment pages, or
incident evidence to build a defensible picture of ransom flow: which addresses received victim
funds, how funds moved afterward, and what patterns link wallets across victims. This supports
victim-scoped damage assessment, ransom decision-making context, and law-enforcement referral.

This playbook deliberately stops at tracing and analysis. It does not facilitate payment,
negotiation strategy, or interaction with attacker infrastructure — those are separate decisions
owned by the victim organization and its counsel.

## When to use

- An extortion note or leak-site page names one or more payment addresses tied to an active
  incident.
- Post-incident review needs a money-trail timeline to understand attacker operational tempo.
- Threat-intel enrichment requires confirming whether a wallet seen in your case matches known
  ransomware affiliate clusters.
- You are preparing a referral package and need wallet-level evidence summaries.
- Leadership asks whether a ransom demand is consistent with the actor's observed historical amounts
  and wallet behavior.

## Prerequisites

- Written authorization from the case owner (incident commander, legal counsel, or the victim
  organization's designated approver) to conduct blockchain analysis on the named addresses.
- A documented chain of custody: case ID, source of each address (note file name, leak-site URL
  snapshot, ransom negotiation transcript), collector identity, and collection timestamps. Hash
  (SHA-256) any copied note files or page snapshots.
- Work on copies of evidence, not originals. Screen snapshots of leak sites should be stored with
  capture tool, date, and timezone recorded.
- Confirm jurisdiction rules before sharing wallet intelligence with third parties; some regions
  restrict disseminating victim-identifying financial data.
- Do not move funds, generate transactions, or interact with attacker-controlled infrastructure
  (e.g., leak-site payment portals requiring "registration").
- Agree in writing whether the organization will consider payment at all; analysis proceeds the same
  either way, but the question will arise and should not be improvised mid-incident.

## Procedure

1. Build an address inventory. Extract every cryptocurrency address from the evidence set: extortion
   notes (typically Bitcoin, sometimes Monero or Ethereum), leak-site payment portals, and
   negotiation chat logs. Record for each: address string, coin type, the exact source file or URL,
   and the date it was observed. Normalize case and strip whitespace.
2. Snapshot the evidence. Save the raw note files and rendered pages (PDF or full-page screenshot),
   then compute SHA-256 hashes and log them in the case notes. This preserves provenance if the
   attacker edits the page later.
3. Query a public block explorer for each address. For Bitcoin, use an explorer's address endpoint
   (e.g., Blockchair or mempool.space) to pull: total received, total sent, current balance,
   first-seen and last-seen timestamps, and the full transaction list. Save the raw API responses as
   JSON with a retrieval timestamp.
4. Construct the first-hop transaction graph. For each inbound transaction, record the sending
   addresses, amounts, block heights, and timestamps. For each outbound transaction, record
   destination addresses, change outputs (if identifiable), amounts, and timestamps. Draw this as a
   directed graph with the wallet as the hub.
5. Apply the common-input ownership heuristic carefully. When a single transaction spends inputs
   from multiple addresses, those addresses are typically controlled by the same entity. Expand the
   cluster cautiously: one unconfirmed merge can contaminate the whole cluster. Flag merges as
   provisional until corroborated.
6. Identify downstream behavior patterns. Look for: consolidation into fewer addresses, peeling
   chains (successive small outputs peeled off a large balance), transfers to exchanges or known
   services, mixing-like patterns (many equal-value outputs), and long dormancy followed by sudden
   movement. Describe what you observe; do not assert laundering intent without corroborating
   evidence.
7. Check for exchange touchpoints. When funds move to a known exchange deposit address, record the
   exchange, the deposit transaction, and the timestamp — but recognize that on-chain data cannot
   show the off-chain account holder. Exchange attribution requires legal process, not blockchain
   analysis alone.
8. Cross-reference against known data. Compare your cluster against internal prior-case wallets,
   published ransomware wallet lists from law-enforcement advisories, and your threat-intel
   platform. Record exact matches, partial overlaps (shared transaction counterparties), and
   near-misses with the criteria you used.
9. Build the timeline. Align wallet activity with incident milestones: initial access date,
   encryption date, note delivery, and any known negotiation events. Note whether ransom deposits
   correlate with known victim disclosures in the timeframe — correlation only, never claim
   attribution to a specific victim without independent confirmation.
10. Assess demand consistency. Compare the demanded amount and the wallet's historical receipts
    against the actor's known pattern from prior cases and advisories. An out-of-pattern demand
    (wrong coin, unusual amount, reused victim address) can indicate an affiliate freelancing or a
    copycat.
11. Set up ongoing monitoring. Configure address-watch alerts (explorer notification features or a
    scheduled API poll) on the case wallets so new movements generate a case update. Define who
    receives the alert and the re-triage procedure when funds move months later.
12. Validate clusters before finalizing. Re-examine every heuristic merge: drop any merge resting on
    a single ambiguous transaction (possible CoinJoin or shared-service spend), and re-run the
    cluster expansion. The final cluster should survive a skeptical re-read.
13. Draft the intelligence product. Produce a wallet dossier: addresses with sources, cluster
    summary, first-hop graph, behavioral observations, exchange touchpoints, matches to known
    datasets, demand-consistency assessment, and the evidence hashes. State confidence levels
    (confirmed / probable / speculative) for every inference.
14. Hand off securely. Deliver the dossier to the case owner and, where authorized, the designated
    law-enforcement liaison. Retain the raw explorer responses and hashes in the case evidence store
    for the retention period defined by the investigation charter.

## Key tools & commands

- Public block explorers with JSON APIs: Blockchair (`curl
  "https://api.blockchair.com/bitcoin/dashboards/address/<addr>"`) and mempool.space (`curl
  "https://mempool.space/api/address/<addr>/txs"`). Both return transaction lists and balances;
  neither requires an account for basic queries.
- WalletExplorer.com — a public database of named wallet clusters useful for checking whether an
  address sits in a previously labeled cluster. Treat labels as leads, not ground truth.
- `curl` / `jq` for pulling and filtering explorer JSON, e.g. `curl -s
  "https://api.blockchair.com/bitcoin/dashboards/address/<addr>" | jq
  '.data."<addr>".transactions'`.
- Graph visualization: yEd, Gephi, or scripted network graphs, fed from the CSV you build in step 4.
- Open-source chain-graphing utilities (e.g., community GraphSense builds) for clustering
  experiments on your own data.
- `sha256sum` for hashing note files and page snapshots.
- Your threat-intel platform's wallet/IOC search to check for prior-case overlap.

## Expected outputs

- An address inventory CSV: address, coin, source evidence, first observed date.
- Raw explorer JSON responses with retrieval timestamps.
- A first-hop transaction graph (diagram or graph file) centered on each wallet.
- A cluster summary listing heuristically linked addresses with the heuristic and confidence noted.
- A behavior/timeline narrative aligned to incident milestones.
- Exchange touchpoint records with the legal-process caveat stated.
- A demand-consistency assessment against the actor's known pattern.
- A monitoring configuration for ongoing wallet movement alerts.
- A wallet dossier suitable for law-enforcement referral, with evidence hashes and confidence
  labels.

## Pitfalls

- Treating the common-input heuristic as proof: a single bad merge (e.g., a CoinJoin misread as
  single-owner) poisons the cluster. Require corroboration.
- Assuming an address is "the attacker's" permanently: ransomware affiliates rotate wallets, and
  some notes contain victim-specific deposit addresses that the operator never reuses.
- Interpreting exchange deposits as cash-out: funds may move through custodial wallets for other
  reasons, and on-chain data cannot show off-chain exchange activity.
- Monero wallets in notes are effectively untraceable on-chain; note the limitation rather than
  inventing a trail.
- Collecting data from a live leak-site payment portal beyond public reads can cross into
  unauthorized interaction — stick to passive observation and document it.
- Dusting and spam transactions: tiny unsolicited outputs to the wallet are noise (or
  deanonymization attempts), not ransom payments. Filter by amount relevance.
- Presenting a probable cluster as confirmed in a legal referral — confidence labels exist to
  prevent exactly this.

## References

- MITRE ATT&CK: T1486 (Data Encrypted for Impact); T1587.001 (Develop Capabilities: Malware) for
  ransomware tooling context.
- FBI Internet Crime Complaint Center (IC3) ransomware advisories — wallet-reporting guidance for
  victims.
- Blockchair API documentation and mempool.space API documentation for explorer query syntax.
- Meiklejohn et al., "A Fistful of Bitcoins: Characterizing Payments Among Men with No Names" — the
  academic basis of common-input ownership clustering.
- FATF guidance on virtual assets and VASPs — the legal-process context for exchange attribution.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
