---
skill_id: web_rest_webhooks
name: REST Webhooks
description: Deliver event notifications reliably: signing, retries, ordering, and the receiver contract.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Webhooks
## Purpose
Build event delivery that receivers can trust and that survives their outages without losing events.
## Key ideas
- A webhook is an HTTP POST your system sends when something happens; the receiver must answer 2xx quickly.
- Sign every payload with HMAC so receivers can verify it came from you and was not tampered with.
- Retry with exponential backoff and jitter; disable endpoints only after sustained failure, with notice.
- Do not promise ordering across event types; include timestamps and ids so receivers can dedupe and sequence.
- Receivers must be idempotent: your retries mean they will see some events twice.

## In practice
Design the receiver contract first: respond within a few seconds, return 2xx only after durable receipt, and make handlers idempotent on the event id. On your side, sign with a per-endpoint secret, rotate it without downtime by supporting two active secrets, and include the event id, type, timestamp, and API version in every payload. Keep a delivery log with attempt history and expose it to the endpoint owner; the fastest way to resolve 'we never got it' is showing the 200 you received from their server at 14:03:22. Version your event payloads like your REST API, because the same breaking-change rules apply.

```http
POST https://client.example.com/hooks/orders HTTP/1.1
Content-Type: application/json
X-Webhook-Id: evt_5f8a1c
X-Webhook-Timestamp: 1726870000
X-Webhook-Signature: sha256=9f2c...

{
  "id": "evt_5f8a1c",
  "type": "order.shipped",
  "api_version": "v1",
  "data": {"order_id": 987}
}
```

## Common mistakes
- Sending unsigned webhooks, letting anyone who guesses the URL inject fake events.
- Retrying aggressively without backoff, turning the receiver's outage into your self-inflicted flood.
- Assuming exactly-once delivery; receivers that are not idempotent corrupt data on every retry.

## Checklist
- Is every payload HMAC-signed with a rotatable per-endpoint secret?
- Do retries use exponential backoff with a documented disable policy?
- Can receivers dedupe on event id and verify signatures from docs alone?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
