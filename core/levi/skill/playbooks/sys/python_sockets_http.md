---
skill_id: sys_python_sockets_http
name: Python Sockets and HTTP Clients
description: Low-level sockets and high-level HTTP: talking to the network from Python.
risk: info
permissions: []
requires_confirmation: false
tags: [python, networking]
version: 1.0.0
---
# Python Sockets and HTTP Clients

## Purpose

Low-level sockets and high-level HTTP: talking to the network from Python.

## Overview

The socket module is Python's thin wrapper over BSD sockets. A TCP client: socket.create_connection((host, port)) (with timeout), then sendall() to transmit - send() may send partial data, sendall loops until done - and recv(n) in a loop until it returns b'' meaning the peer closed. Wrap sockets in with blocks or close explicitly; leaked sockets exhaust file descriptors. A TCP server: bind, listen, accept in a loop, handling each connection (threads or selectors for concurrency). UDP sockets (SOCK_DGRAM) use sendto/recvfrom with no connection and no delivery guarantees. For HTTP, prefer urllib (stdlib) or requests/httpx (third-party): they handle redirects, encoding, chunked bodies, and TLS. urllib.request.urlopen with a Request object covers simple GET/POST; always set timeouts - the default waits forever. Defensive networking: validate hostnames/URLs before connecting (SSRF defense), verify TLS certificates (never disable verification to 'fix' an error), bound response sizes before reading bodies into memory, and treat everything received as untrusted bytes until decoded and validated.

## Quick reference

- create_connection((host, port), timeout=): TCP client with timeout.

- sendall() transmits fully; send() may be partial. recv() loop until b''.

- Server pattern: bind -> listen -> accept loop; threads/selectors for concurrency.

- UDP: SOCK_DGRAM, sendto/recvfrom, no guarantees.

- Prefer urllib/requests for HTTP; always set timeouts.

- Validate URLs (SSRF), verify TLS, bound response sizes, distrust received bytes.


## Worked example

A tiny TCP echo client and server:

```
import socket, threading

def serve_once(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024)
            conn.sendall(b'echo:' + data)

t = threading.Thread(target=serve_once, args=(9999,), daemon=True)
t.start()

with socket.create_connection(('127.0.0.1', 9999), timeout=5) as c:
    c.sendall(b'hello')
    print(c.recv(1024))
```

- SO_REUSEADDR lets you rebind quickly during development.

- sendall guarantees the full message goes out; recv may return partial data.

- create_connection with timeout avoids hanging forever on dead hosts.


## Common mistakes

- No timeout on sockets: a dead peer hangs the program forever.
  Fix: Set timeouts on every connect and read path.

- Using send() once and assuming the whole buffer went out.
  Fix: Use sendall(), or loop on send()'s return count.


## Quick checks

Q: Why does recv sometimes return less than I asked for?
A: TCP is a byte stream, not a message protocol: recv returns whatever has arrived, up to your size. Loop until you have the full message (using a length prefix or delimiter) or until b'' signals close.


Q: urllib vs requests - when does stdlib suffice?
A: Simple GET/POST with timeouts: urllib is fine. Anything with sessions, auth flows, retries, or connection pooling: requests/httpx earn their dependency.


## Mental model

A TCP socket is a phone call: dial (connect), talk in turns (send/recv), and the line stays open until someone hangs up (close). UDP is sending postcards - no call setup, no guarantee of delivery, no order. HTTP libraries are hiring a courier service instead of driving the truck yourself.
