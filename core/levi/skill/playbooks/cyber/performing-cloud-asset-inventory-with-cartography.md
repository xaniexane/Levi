---
skill_id: cyber_performing_cloud_asset_inventory_with_cartography
name: Cloud Asset Inventory with Cartography
description: Build and maintain a graph-based cloud asset inventory using Cartography for security analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, asset-management, aws]
version: 1.0.0
---

## Purpose

You cannot secure what you cannot see. Cloud estates sprawl: accounts, VPCs, instances, buckets, identities, and the relationships between them change daily. Cartography consolidates cloud provider APIs into a Neo4j graph so you can query "which internet-facing instances have a path to this sensitive bucket" instead of clicking through consoles. This playbook covers deploying Cartography with read-only credentials, running syncs, writing security-relevant queries, and operationalizing the graph for continuous visibility.

## When to use

- Standing cloud security posture management where native CSPM tools are insufficient or unavailable.
- Answering blast-radius questions during incident response ("what can this compromised role reach?").
- Auditing cross-account trust relationships and public exposure at scale.
- Feeding an asset graph into threat modeling, attack-path analysis, or compliance evidence.
- Consolidating multi-account or multi-cloud inventory into one queryable model.

## Prerequisites

- A Neo4j instance (self-hosted or managed) sized for your estate; Cartography writes nodes and relationships per sync.
- Read-only IAM credentials (or roles) in each in-scope account with the permissions Cartography's intel modules require; scope them to the APIs you actually sync.
- Network path from the Cartography runner to the Neo4j bolt port and to cloud APIs.
- Python environment with the cartography package installed, plus the provider SDKs for each cloud in scope.
- Defined sync scope: which accounts, subscriptions, or projects to include, and which to exclude (e.g., sandbox accounts).

## Procedure

1. **Stand up Neo4j and secure it.** Deploy Neo4j, change default credentials, enable TLS on the bolt listener, and restrict network access to the Cartography runner and approved analysts. The graph will contain your full cloud topology — treat it as sensitive.
2. **Create least-privilege sync credentials.** Provision a dedicated IAM role/user per account with read-only access to the resource types you will sync. Document the policy; avoid reusing broad admin credentials for inventory collection.
3. **Configure the Cartography job.** Define the sync scope (accounts, regions) and select intel modules relevant to your questions: EC2, S3, IAM, VPC, RDS, Lambda, and equivalents for GCP/Azure. Start narrow and expand — a failed 40-module sync teaches less than a working 6-module one.
4. **Run the initial sync and validate.** Execute the sync, then sanity-check counts against provider consoles: number of accounts, instances, buckets, and roles. Investigate large discrepancies before trusting the graph; API pagination and permission gaps are the usual causes.
5. **Write security-relevant queries.** Build a library of Cypher queries for your recurring questions: internet-exposed instances, S3 buckets with public ACLs or policies, IAM roles with cross-account trust, security groups open to 0.0.0.0/0, instances with IMDSv1, and users with stale access keys. Version-control the queries.
6. **Schedule and monitor syncs.** Run syncs on a schedule matching your change rate (hourly to daily for dynamic estates). Alert on sync failures and on drift: new public exposures or new cross-account trusts appearing between runs are findings, not noise.
7. **Use the graph in incident response.** When an identity or instance is suspected compromised, query its relationships: attached policies, assumable roles, reachable subnets, and data stores. Export the subgraph as evidence and as the containment scoping input.
8. **Maintain the pipeline.** Review module updates with each Cartography release, rotate sync credentials on your standard schedule, prune out-of-scope accounts, and periodically re-validate a sample of graph data against live APIs.

## Expected outputs

- A populated Neo4j graph of cloud assets and relationships, refreshed on schedule.
- A version-controlled Cypher query library covering exposure, privilege, and blast-radius questions.
- Documented sync scope, credentials, and schedule, plus run/failure alerting.
- Incident-response runbooks that use graph queries for scoping and containment.
- Drift reports highlighting new exposures or trust relationships between syncs.

## Pitfalls

- Over-scoping the first sync: too many modules and accounts at once produces failures that are hard to attribute; grow incrementally.
- Read-only in name only: verify the sync policy cannot mutate anything, and never reuse the sync role for remediation automation.
- Stale graphs: a sync that silently stopped three weeks ago is worse than no graph, because analysts trust it. Monitor freshness explicitly.
- Storing the graph without access controls — it is a complete map of your attack surface; protect it accordingly.
- Querying without understanding the data model: Cartography's node/relationship names differ per provider; validate each query against known-good resources first.

## References

- Cartography project documentation (Lyft/cartography on GitHub)
- Neo4j Cypher manual for graph query syntax
- AWS IAM documentation on read-only and least-privilege policy design
- CIS Benchmarks for AWS, GCP, and Azure (for the checks your queries encode)
- NIST SP 800-53 control family CM-8 (system component inventory)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
