---
skill_id: cyber_performing_second_order_sql_injection
name: Second-Order SQL Injection Testing and Defense
description: Find second-order SQL injection flaws during authorized application testing and harden data flows against them.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, sqli, testing]
version: 1.0.0
---

## Purpose
- This playbook covers authorized security testing to find second-order SQL injection plus defensive hardening; it does not cover exploiting applications without permission.
- Explain why second-order SQLi evades naive input filters: payloads are stored safely, then executed unsafely later.
- Give testers a method to trace data from input through storage to dangerous sink queries.
- Provide developers with the parameterized-query and validation patterns that eliminate the class.

## When to use
- During authorized web application penetration tests and secure code reviews.
- When auditing applications that store user input and reuse it in later queries.
- When building SAST or DAST coverage for injection flaws that single-request scanners miss.
- After incidents where stored data triggered unexpected query behavior.

## Prerequisites
- Written authorization for application security testing with defined scope and test accounts.
- A non-production test environment with representative data flows.
- Access to application source code or cooperation from developers for data-flow tracing.
- Database query logging enabled so sink queries can be observed during testing.

## Procedure
1. Confirm authorization and scope, and use only designated test accounts and environments.
2. Map data flows: identify where user input is stored (profiles, comments, file names) and where stored data is later used in queries.
3. Review source code for queries built with string concatenation that consume database-stored values.
4. Craft distinctive but harmless test payloads and submit them through input vectors.
5. Trigger the secondary use: the profile view, report generation, or batch job that reuses the stored data.
6. Observe database query logs for the payload executing as SQL syntax rather than data.
7. Confirm exploitability minimally: demonstrate query manipulation without extracting or modifying real data.
8. Document the full chain: input vector, storage location, sink query, and code references.
9. Recommend fixes: parameterized queries everywhere including for stored data, least-privilege DB accounts, and output encoding where queries cannot be parameterized.
10. Retest after fixes to confirm the stored payload is now treated purely as data.

## Expected outputs
- Test findings with the complete input-to-sink chain documented.
- Code-level remediation guidance for developers.
- Retest evidence confirming the fix.
- Data-flow diagrams marking every input-to-sink path reviewed.
- Secure coding checklist updates for the development team.

## Pitfalls
- Testing on production or with payloads that could corrupt real data; use isolated environments.
- Stopping at input validation; second-order flaws live at the sink, where stored data meets query construction.
- Assuming ORM usage means safety; raw query fragments in ORMs are still injectable.
- Fixing the reported sink while identical patterns remain in other modules.

## References
- OWASP Code Review Guide on data-flow analysis
- OWASP SQL Injection guidance, https://owasp.org/www-community/attacks/SQL_Injection
- OWASP Web Security Testing Guide on injection testing
- CWE-89 on SQL injection
- PortSwigger Web Security Academy materials on second-order SQL injection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
