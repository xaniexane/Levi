---
skill_id: web_ops_reverse_proxy_basics
name: Reverse Proxy Basics
description: What a reverse proxy does: termination, routing, buffering, and shielding app servers from the internet.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment, http]
version: 1.0.0
---
# Reverse Proxy Basics
## Purpose
Place a hardened front door in front of your application servers and understand what it buys you.
## Key ideas
- A reverse proxy sits in front of app servers, accepting client connections and forwarding requests inward.
- It terminates TLS, so app servers speak plain HTTP on a trusted network and certificates live in one place.
- It routes by host or path, letting one public endpoint serve many internal services.
- Slow-client buffering shields app workers: the proxy absorbs the slow read while the app moves on.
- It is also the natural home for rate limiting, compression, caching, and access logging.

## In practice
Terminate TLS at the proxy and keep the internal network private; app servers should never be directly reachable from the internet. Forward the client's real IP and protocol with standard headers (X-Forwarded-For, X-Forwarded-Proto) and teach the app to trust them only from the proxy, never from arbitrary clients. Buffer request bodies at the proxy for slow clients so app workers are not held hostage by a phone on a bad connection. Keep proxy configuration in version control and test routing changes in staging; a misrouted path rule is an outage wearing a config file.

```text
internet -> [reverse proxy: TLS, routing, rate limits]
                |
    +-----------+-----------+
    |                       |
[app server A]        [app server B]   (plain HTTP, private net)

Forwarded headers the app may trust (from the proxy only):
  X-Forwarded-For: 203.0.113.7
  X-Forwarded-Proto: https
```

## Common mistakes
- Exposing app servers directly to the internet beside the proxy, bypassing all its protections.
- Trusting X-Forwarded-For from any client, letting attackers spoof their IP in your logs and logic.
- Holding app workers on slow clients instead of buffering at the proxy.

## Checklist
- Is TLS terminated at the proxy with app servers on a private network?
- Does the app trust forwarded headers only from the proxy's IP?
- Are proxy configs versioned and tested before deploy?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
