---
skill_id: cyber_testing_websocket_api_security
name: Testing WebSocket API Security
description: Authorized WebSocket security testing: handshake authentication, origin validation, and message-level flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [api, websocket, testing]
version: 1.0.0
---
## Purpose
WebSockets bypass many HTTP-layer assumptions: long-lived connections, custom subprotocols, and message-level authorization. This playbook covers authorized testing of your own WebSocket APIs: handshake security, origin validation, authentication, and per-message authorization flaws.

## When to use
- Security assessment of real-time features (chat, trading, collaboration, gaming).
- After adding WebSocket endpoints or changing the handshake flow.
- Validating a reported WebSocket hijacking or auth bypass.
- Designing WebSocket security standards.

## Prerequisites
- Written authorization and test accounts with distinct privileges.
- WebSocket endpoint inventory: paths, subprotocols, and message schemas.
- Tooling for raw WebSocket interaction (proxy with WS support or scripting).
- Understanding of the intended authentication and authorization model.

## Procedure
1. Map the handshake: how authentication is passed (headers, cookies, tickets, tokens in URL).
2. Test origin validation: connect with attacker origins and missing origins; check for cross-site hijacking.
3. Test authentication: unauthenticated handshakes, expired tokens, and token-in-URL leakage via logs.
4. Test per-message authorization: subscribe to other users' channels, send actions as another user.
5. Test input handling in messages: injection into broadcast content, oversized frames, and rapid message floods.
6. Test session behavior: does logout or password change terminate open sockets?
7. Verify CSRF-style protections where cookies authenticate the handshake.
8. Confirm fixes: strict origin allowlist, short-lived handshake tickets, per-message authz, and rate limits.
9. Test reconnection and resume flows for session fixation or replay issues.
10. Pin the expected subprotocol; negotiation downgrades can weaken security.
11. Verify that horizontal scaling (multiple servers) does not break per-connection authorization.

## Expected outputs
- WebSocket test matrix: handshake, origin, auth, and message-level results.
- Findings with hijacking or cross-user impact evidence.
- Hardened handshake design and retest results.
- Reconnection/resume flow test results.
- Subprotocol negotiation assessment.
- Multi-server authorization consistency check.

## Pitfalls
- Tokens in WebSocket URLs leak into logs and proxies; use headers or tickets instead.
- Authorizing the handshake but not each message is the classic WebSocket BOLA.
- WAFs often do not inspect WebSocket frames; do not rely on them here.
- Long-lived sockets outlive revocation; implement server-side session checks or heartbeats.
- Subprotocol negotiation can downgrade security; pin the expected subprotocol.
- Sticky-session assumptions break authorization when scaling; test across servers.
- Idle-connection timeouts that are too generous waste resources and extend attack windows.
- Message ordering assumptions break under reconnect storms; design handlers idempotently.

## References
- OWASP Web Security Testing Guide: WebSocket testing.
- OWASP Cheat Sheet: WebSocket security.
- PortSwigger Web Security Academy: WebSocket vulnerabilities.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
