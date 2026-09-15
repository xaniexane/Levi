---
skill_id: cyber_implementing_taxii_server_with_opentaxii
name: Implementing a TAXII Server with OpenTAXII
description: Deploy an OpenTAXII server to publish and share STIX threat intelligence.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intelligence, taxii, sharing]
version: 1.0.0
---
## Purpose
This playbook covers standing up an OpenTAXII server so your organization can publish STIX collections to trusted partners and consume shared collections, with proper authentication, access control, and auditability.

## When to use
- You produce threat intelligence (from incidents, hunts, or research) that partners or an ISAC should consume.
- Sharing currently happens over email or portals and needs a machine-readable, standards-based channel.
- You must enforce who can read or write each collection.

## Prerequisites
- A host or container platform for the server with TLS termination and a service account model.
- STIX 2.1 content to publish (indicators, reports, sightings) with TLP markings assigned.
- List of consumer organizations and their authentication method (API keys, mutual TLS, or basic auth over TLS).

## Procedure
1. **Install and configure OpenTAXII.** Deploy the server, define collections (e.g., one per sharing community or sensitivity level), and set retention and pagination defaults.
2. **Harden the service.** Terminate TLS with a valid certificate, disable weak ciphers, place the server behind authentication, and restrict management endpoints to administrators.
3. **Define access control.** Create accounts per consumer; grant read access only to the collections they are entitled to, and write access only to trusted producers.
4. **Publish content.** Push STIX bundles to the appropriate collections with correct TLP labels, external references, and confidence values; validate with a STIX validator before publishing.
5. **Document the consumer contract.** Publish the discovery endpoint, collection IDs, polling guidance, and the meaning of your confidence/TLP conventions so consumers can ingest correctly.
6. **Audit and monitor.** Log all reads and writes; alert on anomalous access (new IPs, bulk downloads, failed auth bursts) and review sharing agreements periodically.
7. **Test end-to-end.** Have a trusted partner poll a collection and confirm objects parse, markings are respected, and updates propagate.

## Expected outputs
- Operational OpenTAXII server with documented collections and access matrix.
- Consumer onboarding guide and published STIX bundles.
- Audit logs of sharing activity and a review cadence for access.

## Pitfalls
- Publishing indicators without TLP or confidence, leaving consumers unable to act safely.
- Overly broad collection access that leaks sensitive context to the wrong audience.
- Letting the server fall behind on STIX/TAXII library updates, breaking compatibility.

## References
- OASIS TAXII 2.1 specification (docs.oasis-open.org/cti/taxii/v2.1).
- OpenTAXII project documentation (github.com/eclecticiq/OpenTAXII — project docs).
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
