# Assessing Vector and Embedding Weaknesses

## Purpose

Provide a repeatable methodology for evaluating the security posture of embedding models
and vector databases that back retrieval-augmented generation (RAG) systems, semantic
search, and LLM memory. The goal is to find weaknesses — unsecured endpoints, poisoned or
exfiltrated corpora, access-control gaps, and metadata leakage — before an adversary does.

## When to use

- Before deploying or auditing a RAG pipeline, semantic search service, or vector-backed
  assistant.
- During vendor review of an embedding service or managed vector database.
- After an incident involving prompt injection via retrieved documents or suspected
  retrieval-data poisoning.
- As part of an AI-security assessment scoped to model-serving and retrieval infrastructure.
- When data classification changes and you must confirm restricted documents are not
  retrievable by unauthorized principals.

## Prerequisites

- Written authorization covering the target system (the assessment touches live retrieval
  traffic and stored embeddings).
- A defined scope: which vector collections, embedding endpoints, and data sources are in
  bounds.
- Read access to collection configuration, namespace/index schemas, and the application code
  that queries vectors.
- A test collection or namespace you are permitted to write to (never inject test documents
  into production indexes).
- Inventory of the stack: embedding model name/version, vector DB product/version, the
  chunking and ingestion pipeline, and metadata fields.
- Two test identities — one privileged, one low-privilege — to verify document-level access
  enforcement.

## Procedure

1. **Map the retrieval pipeline.**
   - Document every stage: source documents → ingestion/chunking → embedding model →
     vector store → retrieval filter → prompt construction.
   - Record which service owns each stage and where trust boundaries sit (ingestion
     workers vs. query API vs. model host).

2. **Inventory access controls on the vector store.**
   - Check who can read, write, and delete vectors per collection/namespace.
   - Verify authentication on management and query ports: Milvus gRPC/REST, Weaviate,
     Qdrant `:6333`/`:6334`, Pinecone API keys, pgvector via database roles.

3. **Test for unauthenticated access.**
   - From a network position equivalent to an untrusted client, attempt anonymous requests:
     - `curl -s http://<host>:6333/collections` (Qdrant — a `200` listing collections
       confirms exposure)
     - `curl -s http://<host>:8080/v1/schema` (Weaviate)
     - Milvus gRPC `:19530` / REST `:9091`
   - An open read path exposes the full document corpus to similarity queries.

4. **Audit metadata fields for sensitive data.**
   - Query the collection schema and sample payloads for fields such as `source_url`,
     `owner`, `classification`, `customer_id`, or raw PII.
   - Confirm retrieval filters actually exclude restricted documents for low-privilege
     callers — test it, don't trust the filter code alone.

5. **Test document-level authorization as two principals.**
   - Run the same representative queries as the privileged and the low-privilege identity.
   - Any restricted document returned to the low-privilege caller is a confirmed failure;
     record query, document ID, and the filter that should have blocked it.

6. **Evaluate ingestion integrity.**
   - Review who or what can add documents: user uploads, scraped web content,
     third-party feeds, scheduled sync jobs.
   - Any low-trust source flowing into ingestion without review or signing makes the
     corpus poisonable — record it as a finding with the affected collections.

7. **Test corpus poisoning in the sandbox namespace.**
   - With authorization, insert a test document containing a canary string
     (e.g., `CANARY-<random-hex>`), run representative queries, and confirm whether it is
     retrieved and cited by the LLM. Delete the canary and verify removal afterward.

8. **Assess embedding inversion exposure.**
   - Published research shows embeddings can partially reconstruct source text — treat
     readable vectors as sensitive.
   - Check TLS in transit, encryption at rest, and whether raw vectors leave the trust
     boundary (logs, backups, analytics exports).

9. **Review query logging and retention.**
   - Confirm queries and retrieved document IDs are logged with a retention window that
     supports incident response, and that logs are tamper-evident without storing raw
     user PII unnecessarily.

10. **Check rate limiting and abuse controls.**
    - Confirm per-key or per-tenant rate limits on embedding and query endpoints to blunt
      corpus-extraction attacks that sweep the index with many similarity queries.
    - Test with a burst of authorized requests and observe the `429` behavior.

11. **Verify model and pipeline provenance.**
    - Record embedding model name, version, and source; flag unpinned, unreviewed, or
      locally patched models.
    - Check a silent model swap can't change retrieval behavior undetected (hash model
      artifacts or pin digests in deployment manifests).

12. **Produce findings with severity.**
    - For each confirmed weakness record the affected collection/endpoint, evidence
      (command output, query transcript), and impact (corpus theft, poisoning, privilege
      bypass).
    - Recommend concrete remediation: enforce authentication, per-tenant namespaces,
      ingestion allowlists with content review, metadata redaction, query-layer ACL checks.

## Key tools & commands

- `curl` / `httpie` — probe vector DB REST endpoints for anonymous access.
- `qdrant-client`, `pymilvus`, `weaviate-client` — official Python clients for schema
  inspection and authorized test queries; prefer read-only roles.
- `psql` — inspect pgvector collections: `\d <table>` for schema, `SELECT` on metadata
  columns, `\z` for table privileges.
- `nmap -sV -p 6333,6334,8080,19530,9091 <host>` — which vector-store ports are reachable
  from untrusted segments.
- `trufflehog` / `gitleaks` — scan ingestion repos and configs for hardcoded vector-DB API
  keys.
- Application source review — the only reliable way to confirm retrieval filters and prompt
  construction; no scanner replaces reading the query code.

## Expected outputs

- Retrieval pipeline diagram with trust boundaries marked.
- Collection inventory: name, access controls, metadata fields, ingestion sources, owner.
- Authorization test matrix: query × principal → documents returned, failures highlighted.
- Findings list with evidence, severity, remediation (unauthenticated endpoints, over-broad
  metadata, poisonable ingestion, missing rate limits, ACL bypass).
- Canary test report: whether planted documents were retrieved and cited, cleanup confirmed.
- Remediation roadmap ordered by risk (exposure first, hardening second).

## Pitfalls

- Testing poisoning against a production index — always use a sandbox collection and clean
  up canaries.
- Confusing "vectors are not readable text" with safety: embeddings are reversible enough
  to matter, and metadata often contains the sensitive parts outright.
- Overlooking ingestion: the vector DB may be locked down while a scheduled scraper writes
  attacker-influenced documents straight in.
- Assuming the application enforces document-level ACLs — verify in code *and* with test
  queries as two different principals.
- Forgetting backups and analytics exports: vectors copied to a data lake inherit none of
  the query-layer access controls.

## References

- MITRE ATLAS: `AML.T0020` (Poison Training Data), `AML.T0034` (Exfiltrate ML Model / data
  via AI queries).
- OWASP Top 10 for LLM Applications: LLM02 (Data and Model Poisoning), LLM05 (Improper
  Output Handling), LLM06 (Excessive Agency).
- NIST AI 600-1, *Artificial Intelligence Risk Management Framework: Generative AI
  Profile*.
- Qdrant docs (authentication, TLS, RBAC); Milvus docs (RBAC); Weaviate docs
  (authorization configuration).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
