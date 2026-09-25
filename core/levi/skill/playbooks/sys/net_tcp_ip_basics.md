---
skill_id: sys_net_tcp_ip_basics
name: Networking TCP/IP Basics
description: Packets, addresses, and the layers that move data across the world.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, fundamentals]
version: 1.0.0
---
# Networking TCP/IP Basics

## Purpose

Packets, addresses, and the layers that move data across the world.

## Overview

TCP/IP moves data as packets across networks. The mental model is layers, each adding its envelope: link (Ethernet/WiFi frames on one hop), internet (IP packets routed globally by address), transport (TCP/UDP segments with ports), application (HTTP, DNS, SSH). IP addresses identify hosts: IPv4's 32 bits (dotted decimal) are exhausted, so NAT and IPv6's 128-bit hex addresses carry the future. CIDR notation (192.168.1.0/24) names ranges; private ranges (10/8, 172.16/12, 192.168/16) are not globally routable. TCP adds reliability atop IP's best-effort delivery: the three-way handshake (SYN, SYN-ACK, ACK) opens a connection, sequence numbers order bytes, ACKs confirm receipt, retransmission recovers loss, and flow/congestion control pace the sender. That reliability costs latency - the handshake plus head-of-line blocking. Encapsulation means each layer only talks to its peer layer on the other end; debugging follows the stack bottom-up. MTU (~1500 bytes on Ethernet) fragments oversized packets; path MTU discovery avoids it. Practical grasp: ping tests IP, a TCP connect tests the port, and everything above is the application's conversation.

## Quick reference

- Layers: link -> internet (IP) -> transport (TCP/UDP) -> application.

- IPv4 32-bit exhausted; IPv6 128-bit; NAT bridges the gap.

- CIDR 192.168.1.0/24 = range. Private: 10/8, 172.16/12, 192.168/16.

- TCP: handshake, sequence numbers, ACKs, retransmission, flow control.

- Reliability costs latency: handshake + head-of-line blocking.

- Debug bottom-up: ping (IP), connect (TCP), then application.


## Worked example

Seeing the layers with standard tools:

```
# Your addresses and routes (internet layer):
ip -brief addr
ip route

# TCP handshake, timed (transport layer):
time nc -zv example.com 443

# Watch the packets themselves (link+up):
# sudo tcpdump -i any -n 'tcp port 443' -c 5

# Python: what TCP gives you is a reliable byte stream
import socket
with socket.create_connection(('example.com', 80), timeout=5) as s:
    s.sendall(b'GET / HTTP/1.0\r\nHost: example.com\r\n\r\n')
    print(s.recv(200))
```

- ip addr/route: the modern ifconfig/route replacements.

- nc -zv times the TCP handshake specifically.

- TCP presents a byte stream; message framing is the app's job.


## Common mistakes

- Assuming TCP preserves message boundaries: it is a byte stream.
  Fix: Frame messages yourself: length prefixes or delimiters.

- Blocking all ICMP: breaks path MTU discovery, causing weird hangs.
  Fix: Filter ICMP selectively; never drop it entirely.


## Quick checks

Q: Why does TCP need a three-way handshake?
A: To synchronize sequence numbers both ways and confirm both sides can send and receive before data flows. It also (weakly) validates the peer isn't spoofing - SYN cookies harden this against floods.


Q: IPv4 vs IPv6 - what actually changes for me?
A: Address format and abundance (no NAT needed), slightly different headers. Sockets and apps mostly work the same; the operational change is firewall rules and DNS (AAAA records) for both stacks.


## Mental model

Layers are nested envelopes: you write a letter (application), put it in a TCP envelope with tracking (registered mail), address it with IP (postal sorting), and hand it to the local courier (link). Each handler only reads its own envelope and passes the inner one along.
