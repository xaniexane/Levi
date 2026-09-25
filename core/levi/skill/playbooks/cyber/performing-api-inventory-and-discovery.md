---
skill_id: cyber_performing_api_inventory_and_discovery
name: Performing API Inventory and Discovery
description: Discover and catalog all APIs, including shadow and zombie endpoints, for governance.
risk: info
permissions: []
requires_confirmation: false
tags: [api-security, asset-management, governance]
version: 1.0.0
---

## Purpose
This playbook builds and maintains a complete API inventory: discovering known, shadow, and zombie APIs across the estate so every endpoint can be governed, tested, and monitored. You cannot secure APIs you do not know exist.

## When to use
- API sprawl with no central catalog; teams ship endpoints independently.
- Preparing for API security testing or a compliance assessment.
- After incidents involving undocumented or forgotten endpoints.

## Prerequisites
- Discovery tooling: API gateway logs, WAF/CDN logs, code repository scanning, and optionally an API discovery product.
- Authority to require API registration as part of the development lifecycle.
- Data classification to prioritize which APIs matter most.

## Procedure
1. **Discover from traffic.** Analyze gateway, WAF, and CDN logs for API-shaped traffic; extract hosts, paths, methods, and versions actually receiving requests.
2. **Discover from code and specs.** Scan repositories for OpenAPI specs, route definitions, and SDK references; reconcile against the traffic-derived list.
3. **Discover from the edge.** Review DNS records, certificate transparency logs, and cloud asset inventories for API hostnames nobody claimed.
4. **Classify every API.** Record owner, data sensitivity, authentication method, version status, and production vs. deprecated; flag shadow (unregistered) and zombie (deprecated but still live) APIs.
5. **Establish registration as a gate.** Make API registration (spec + owner + classification) a required step in the deployment pipeline; block unregistered production deployments.
6. **Continuously reconcile.** Run discovery on a schedule and alert on new unregistered endpoints; treat a new shadow API like a new internet-facing asset.
7. **Drive remediation.** Deprecate and decommission zombie APIs on a timeline; bring shadow APIs under auth, logging, and testing standards or shut them down.

8. **Version the inventory.** Track API versions and deprecation dates; v1 endpoints left running "temporarily" are the classic zombie API.
9. **Feed testing and monitoring.** Every cataloged API gets baseline security testing and production monitoring; inventory without follow-through is shelfware.

## Expected outputs
- Living API catalog with ownership, classification, and lifecycle state.
- Discovery-to-registration reconciliation process with alerting.
- Zombie/shadow API remediation backlog with decommission dates.
- Example: traffic analysis discovers an undocumented v1 endpoint still serving customer data two years after deprecation; it is either brought under auth and monitoring or decommissioned within 30 days.

## Pitfalls
- A one-time inventory exercise that is stale within a quarter.
- Cataloging without enforcement: registration must gate deployment.
- Focusing only on REST while GraphQL, gRPC, and websocket APIs go undiscovered.

- Counting only documented APIs while partner and internal-service APIs go undiscovered; extend discovery to east-west traffic.
- Registration processes so heavy that teams bypass them; make the secure path the easy path or shadow APIs multiply.

## References
- OWASP API Security Top 10 (owasp.org/API-Security) — API1:2023 Broken Object Level Authorization and inventory guidance.
- NIST SP 800-204 (microservices/API security series).
- Gartner/CSA API security guidance — lifecycle governance models.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
