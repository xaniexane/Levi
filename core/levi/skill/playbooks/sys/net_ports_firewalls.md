---
skill_id: sys_net_ports_firewalls
name: Networking Ports and Firewalls
description: How services are addressed and how packet filters protect them.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, security]
version: 1.0.0
---
# Networking Ports and Firewalls

## Purpose

How services are addressed and how packet filters protect them.

## Overview

Ports (0-65535) multiplex services on one IP: the port in a TCP/UDP header says which application gets the packet. Well-known ports: 22 SSH, 25 SMTP, 53 DNS, 80 HTTP, 443 HTTPS, 3306 MySQL, 5432 Postgres, 6379 Redis, 8080 HTTP-alt. Below 1024 are privileged (root to bind). A listening socket (ss -tlnp) accepts connections; connecting to a closed port gets RST (or silence if filtered). Firewalls filter by address/port/protocol: Linux uses nftables (iptables legacy), fronted by ufw/firewalld for humans. Default-deny inbound is the sane posture: allow only needed ports from needed sources, with rate-limiting on exposed SSH. Stateful firewalls track connections so replies to outbound traffic pass automatically. Order matters: rules evaluate top-down, first match wins - put specific allows before general denies. Cloud security groups are the same idea at the provider layer; defense in depth means host + cloud both filter. Scanning ports you do not own is hostile; scan your own with nmap -sV to verify what is actually exposed. Debugging: connection refused = nothing listening; timeout = filtered/dropped or routing black hole.

## Quick reference

- Ports 0-65535 multiplex services per IP. <1024 privileged (root to bind).

- Know the well-known: 22, 53, 80, 443, 3306, 5432, 6379, 8080.

- Default-deny inbound; allow only needed ports from needed sources.

- Rules evaluate top-down, first match wins.

- Refused = nothing listening. Timeout = filtered or black-holed.

- Scan only what you own (nmap -sV); cloud groups + host firewall = depth.


## Worked example

Seeing listeners and filtering minimally:

```
# What's listening, and who owns it?
ss -tlnp

# Minimal nftables-minded posture via ufw:
# ufw default deny incoming
# ufw allow 22/tcp
# ufw allow 80,443/tcp
# ufw enable

# Is the port reachable from here? (refused vs timeout tells the story)
nc -zv db.internal 5432
curl -sS --max-time 5 -o /dev/null -w '%{http_code}\n' http://web.internal/
```

- ss -tlnp: the ground truth of exposed services.

- Default deny + explicit allows: the whole firewall philosophy in 4 lines.

- refused vs timeout distinguishes 'closed' from 'filtered'.


## Common mistakes

- Binding dev services to 0.0.0.0 on a laptop in a cafe.
  Fix: Bind 127.0.0.1 unless the network genuinely needs it.

- Firewall rule order: broad deny before the specific allow.
  Fix: First match wins - order rules from specific to general.


## Quick checks

Q: Connection refused vs timed out - what's the difference?
A: Refused: reached the host, nothing listens on that port (RST). Timeout: packets dropped (firewall) or lost (routing) - no answer at all. Refused is a server config issue; timeout is network/filtering.


Q: Do I need a firewall if my app binds to localhost?
A: Binding to 127.0.0.1 already excludes the network - good. The firewall still matters for everything else listening, and defense in depth covers the day someone binds 0.0.0.0 by accident.


## Mental model

Ports are apartment numbers in one building (IP): the street address gets the mail to the building, the apartment number to your door. The firewall is the doorman with a list: default-deny means 'no one in unless they're on the list', and he checks top-down.
