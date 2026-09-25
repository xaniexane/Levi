---
skill_id: sys_linux_network_tools
name: Linux Network Tools
description: Diagnosing connectivity: ping, ss, curl, dig, and the layer-by-layer method.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, networking]
version: 1.0.0
---
# Linux Network Tools

## Purpose

Diagnosing connectivity: ping, ss, curl, dig, and the layer-by-layer method.

## Overview

Diagnose bottom-up through the layers. ping tests IP reachability and latency (some hosts block ICMP - no reply is not proof of death). traceroute/mtr shows the path and where it breaks. dig (+short) queries DNS directly: dig example.com, dig @8.8.8.8 to bypass local resolvers; getent hosts checks the system resolver including /etc/hosts. ss -tlnp lists listening TCP ports and owning processes (netstat is deprecated); ss -tnp shows connections. curl is the HTTP Swiss knife: -i headers, -sS silent-but-errors, -o/-O output, -X POST -d data, -H headers, --max-time timeouts, -v for the full handshake trace. ip addr/route replaced ifconfig/route. tcpdump/wireshark capture packets when you must see the wire. The method: 1) DNS resolves? (dig) 2) IP reachable? (ping) 3) port open? (curl -v / nc -zv) 4) app responding correctly? (curl -i, check status/body). Most 'network is down' reports die at step 1 or 3. Defensive notes: do not scan networks you do not own, and treat curl | bash as remote code execution - inspect before piping.

## Quick reference

- ping: L3 reachability. mtr/traceroute: path and break point.

- dig +short: DNS. getent hosts: system resolver incl. /etc/hosts.

- ss -tlnp: listening ports + processes. curl -v: full handshake trace.

- curl -sS --max-time N: script-friendly fetch with timeout.

- Debug order: DNS -> ping -> port -> HTTP status/body.

- Never curl | bash uninspected; never scan networks you do not own.


## Worked example

Layer-by-layer diagnosis of a web service:

```
# 1. DNS?
dig +short example.com
getent hosts example.com

# 2. Reachable? 3. Port open?
ping -c 3 example.com
nc -zv example.com 443

# 4. HTTP healthy?
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' \
  --max-time 10 https://example.com/health

# Who is listening locally?
ss -tlnp | head
```

- dig +short gives just the answer IPs, script-friendly.

- curl -w prints code and timing without downloading the body.

- ss -tlnp needs privileges to show all process owners.


## Common mistakes

- Assuming ping failure = host down (ICMP often blocked).
  Fix: Test the actual port with nc/curl instead.

- Debugging from the top (app logs) when DNS is broken.
  Fix: Go bottom-up: DNS, ping, port, then HTTP.


## Quick checks

Q: ping works but curl fails - what layer is broken?
A: Above L3: the port is closed/filtered or the app is down. Check ss -tlnp on the server (is it listening?), firewalls, then curl -v to see how far the handshake gets.


Q: Why is curl | bash dangerous?
A: It executes whatever the server returns, right now, with your privileges - a compromised server or MITM owns your machine. Download, inspect, then run.


## Mental model

Network debugging is checking why a letter did not arrive: is the address right (DNS), does the road exist (ping), is the mailbox open (port), did anyone answer the door (HTTP). Start at the address - most lost letters never left the post office.
