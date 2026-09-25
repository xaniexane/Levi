---
skill_id: web_http_version_history
name: HTTP Versions 1.0 to 3
description: What changed from HTTP/1.0 through HTTP/3: keep-alive, multiplexing, header compression, and QUIC.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Versions 1.0 to 3
## Purpose
Give historical context for the protocol's evolution so version-specific behaviors, like head-of-line blocking, make sense when you meet them.
## Key ideas
- HTTP/1.0 opened a new TCP connection per request; HTTP/1.1 added persistent keep-alive connections and pipelining.
- HTTP/1.1 suffers head-of-line blocking: one slow response stalls everything behind it on the same connection.
- HTTP/2 multiplexes many streams over one connection and compresses headers with HPACK, fixing the blocking problem.
- HTTP/2 still runs on TCP, so packet loss stalls all streams; HTTP/3 moves to QUIC over UDP so streams fail independently.
- TLS is effectively mandatory for HTTP/2 and HTTP/3 in practice; browsers only speak the newer versions over HTTPS.

## In practice
You rarely choose a version directly; you enable them on the server and let negotiation (ALPN during the TLS handshake) pick the best both sides support. The practical takeaways: stop sharding assets across many domains (that was a HTTP/1.1 workaround that hurts HTTP/2), keep header counts modest even with compression, and test over real lossy networks if your users are mobile, because that is where HTTP/3's per-stream independence pays off. When debugging, check which version actually got negotiated; a surprising amount of weirdness is just a middlebox downgrading you to HTTP/1.1.

```text
# See the negotiated protocol with curl
curl -v --http3 https://example.com/ 2>&1 | grep -i "using HTTP"

# Typical ALPN negotiation offers h2 and http/1.1
# Server picks the best mutual option during the TLS handshake
```

## Common mistakes
- Keeping HTTP/1.1-era domain sharding, which defeats HTTP/2 multiplexing and adds connection overhead.
- Assuming HTTP/2 fixes slow networks; it fixes blocking, but lossy links still want HTTP/3.
- Forgetting that plaintext HTTP/2 is barely supported; plan for TLS from the start.

## Checklist
- Does the server negotiate h2/h3 via ALPN where the stack supports it?
- Have HTTP/1.1 workarounds like domain sharding been removed?
- Is behavior verified on the version clients actually negotiate, not just the newest?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
