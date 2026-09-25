---
skill_id: sys_net_dns
name: Networking DNS
description: The phone book of the internet: resolution, records, and caching.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, fundamentals]
version: 1.0.0
---
# Networking DNS

## Purpose

The phone book of the internet: resolution, records, and caching.

## Overview

DNS maps names to addresses through a distributed hierarchy: root servers delegate to TLD servers (.com), which delegate to authoritative servers for the domain. Resolvers (your configured nameserver) walk this chain and cache results per their TTL. Record types: A (IPv4), AAAA (IPv6), CNAME (alias to another name), MX (mail exchangers, with preference), TXT (free text - SPF/DKIM/verification), NS (authoritative servers), SOA (zone metadata), SRV (service location), PTR (reverse lookup). CNAME at the apex is illegal (it would swallow NS/SOA) - ALIAS/ANAME are provider hacks around it. Caching is why DNS changes take time: lower TTLs before migrations. /etc/hosts overrides DNS locally; /etc/resolv.conf (or systemd-resolved) picks resolvers; getent hosts tests the full system path. Security: classic DNS is unencrypted and spoofable - DNSSEC adds signatures (validation, not privacy), DoH/DoT encrypt the transport. Operationally, DNS is the most common 'network is down': always test resolution (dig +short, dig @8.8.8.8 to bypass local) before blaming connectivity. Negative caching means even failures get cached briefly.

## Quick reference

- Hierarchy: root -> TLD -> authoritative; resolvers walk it and cache per TTL.

- A/AAAA: addresses. CNAME: alias. MX: mail. TXT: verification/SPF/DKIM.

- Lower TTLs before migrations; changes propagate as caches expire.

- /etc/hosts overrides DNS. dig @server bypasses local resolvers.

- DNSSEC: signatures (not privacy). DoH/DoT: encrypted transport.

- 'Network down' is often DNS: test resolution first.


## Worked example

Interrogating DNS directly:

```
# Basic resolution, short output:
dig +short example.com A
dig +short example.com AAAA

# Bypass local resolver (is it a local problem?):
dig +short @8.8.8.8 example.com

# Mail and text records:
dig +short example.com MX
dig +short example.com TXT

# Trace the delegation chain:
dig +trace example.com | tail -5

# What does the SYSTEM resolver see (includes /etc/hosts)?
getent hosts example.com
```

- +short: just the answers, script-friendly.

- @8.8.8.8 isolates local resolver vs authoritative problems.

- getent hosts tests NSS: hosts file, mDNS, then DNS.


## Common mistakes

- Blaming the network when DNS resolution fails.
  Fix: dig first: resolution, then ping, then ports - bottom-up.

- Forgetting negative caching: a failed lookup is cached too.
  Fix: Brief NXDOMAIN caching means 'fixed' records need moments to work.


## Quick checks

Q: I changed a DNS record - why hasn't it propagated?
A: Caches: resolvers worldwide hold the old value until its TTL expires. Lower the TTL well before changes; after, wait it out. Check authoritative directly (dig @auth-server) to confirm the change itself is live.


Q: Why can't I put a CNAME at the domain apex?
A: A CNAME claims ALL record types for the name, conflicting with the apex's mandatory SOA and NS records. Providers offer ALIAS/ANAME records that resolve the target and serve A/AAAA instead.


## Mental model

DNS is a phone book with branch offices: your local office (resolver) asks the national registry (root), which points to the regional office (TLD), which points to the business's own listing (authoritative). Offices photocopy answers (cache) until the printed expiry date (TTL).
