---
skill_id: sys_net_udp_vs_tcp
name: Networking UDP vs TCP
description: Choosing the transport: reliability against latency, and where each wins.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, fundamentals]
version: 1.0.0
---
# Networking UDP vs TCP

## Purpose

Choosing the transport: reliability against latency, and where each wins.

## Overview

TCP is a reliable, ordered, connection-oriented byte stream: handshake, retransmission, congestion control - at the cost of setup latency and head-of-line blocking (one lost packet stalls everything behind it). UDP is connectionless datagrams: each sendto is one packet, delivered best-effort with no ordering, no retransmission, no congestion control - minimal latency, maximal application responsibility. Choose UDP when timeliness beats completeness: live video/voice (a late packet is useless), DNS (single small query, timeout+retry is enough), games (state updates supersede). Choose TCP when every byte matters in order: files, web pages, APIs, email. QUIC (HTTP/3) is the modern synthesis: UDP-based with reliability, streams without head-of-line blocking, and integrated TLS - the best of both for the web. Building on UDP means implementing what you need : sequence numbers, ACKs, retransmission timers - i.e., reinventing TCP's subset, which is justified only when TCP's specific trade-offs (head-of-line blocking, handshake latency) hurt you. Operational notes: UDP has no 'connection', so firewalls/NAT track pseudo-sessions by timeout; and UDP amplification makes open UDP services a DDoS reflection risk - never run one unintentionally exposed.

## Quick reference

- TCP: reliable, ordered, connection-oriented. Costs: handshake + head-of-line blocking.

- UDP: connectionless datagrams, best-effort. Costs: app handles loss/order.

- UDP wins: live media, DNS, games - timeliness over completeness.

- TCP wins: files, web, APIs - every byte, in order.

- QUIC (HTTP/3): UDP + reliability + streams + TLS, no HOL blocking.

- Open UDP services risk DDoS amplification: don't expose unintentionally.


## Worked example

UDP vs TCP in Python:

```
import socket

# UDP: one datagram, no connection
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.sendto(b'ping', ('8.8.8.8', 53))
u.settimeout(2)
try:
    data, addr = u.recvfrom(512)
    print('udp reply from', addr)
except socket.timeout:
    print('udp: no reply (normal for firewalled targets)')
u.close()

# TCP: connected stream (compare the setup cost)
t = socket.create_connection(('example.com', 80), timeout=5)
t.close()
```

- UDP sendto/recvfrom: no handshake, no connection state.

- Timeout + retry is the application's job with UDP.

- TCP create_connection pays the handshake before any data flows.


## Common mistakes

- Using TCP for 60Hz game state: head-of-line blocking adds lag spikes.
  Fix: UDP with latest-state-wins semantics fits real-time updates.

- Assuming UDP delivery in a request/response design without retries.
  Fix: UDP needs application-level timeouts and retries to be dependable.


## Quick checks

Q: Why does DNS use UDP if UDP is unreliable?
A: Queries are tiny and idempotent: a lost query just times out and retries, cheaper than a TCP handshake per lookup. DNS falls back to TCP for large responses (zone transfers, big DNSSEC answers).


Q: When is QUIC better than TCP+TLS?
A: Lossy or high-latency links: no head-of-line blocking across streams, faster handshakes (0-RTT resumption), and connection migration across networks. That is why HTTP/3 exists.


## Mental model

TCP is a phone call: dial, confirm, talk in order, redial on dropout. UDP is shouting across a canyon and listening for an echo: instant, but the wind may eat your words - fine for 'still here?' check-ins, terrible for dictating a contract.
