"""Liveness + port + HTTP(S) probing — connect-scan only, no exploitation.

For each host:
  - TCP connect-scan on a small common-ports list (open/closed only).
  - HTTP(S) GET / with a polite UA: status, Server/X-Powered-By headers,
    <title>, meta generator — banner/tech fingerprinting from ordinary
    responses.
  - TLS certificate details (subject/issuer/expiry) on 443.

Every host passes the scope gate before the first packet. Timeouts on
everything; a dead host never crashes the run.
"""

from __future__ import annotations

import http.client
import re
import socket
import ssl
import time
import urllib.request
from typing import Dict, List, Optional

from levi.bounty.scope import ScopeStore, check_scope

UA = "LEVI-bounty-recon/1.0 (authorized bug-bounty recon; in-scope targets only)"
TIMEOUT = 8
REQUEST_DELAY = 0.5

COMMON_PORTS = [80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 9000]

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_GENERATOR_RE = re.compile(
    r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE
)

_TECH_HINTS = {
    "server": "server",
    "x-powered-by": "x-powered-by",
    "x-aspnet-version": "x-aspnet-version",
    "x-generator": "x-generator",
}


def _tcp_open(host: str, port: int, timeout: int = TIMEOUT) -> bool:
    """TCP connect check. Never raises."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _http_get(
    host: str, port: int, use_tls: bool, timeout: int = TIMEOUT
) -> Optional[Dict[str, object]]:
    """Ordinary GET /. Returns response facts or None. Never raises."""
    scheme = "https" if use_tls else "http"
    url = f"{scheme}://{host}:{port}/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        if use_tls:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return _response_facts(resp)
        else:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _response_facts(resp)
    except Exception:
        return None


def _response_facts(resp) -> Dict[str, object]:
    body = resp.read(500_000).decode("utf-8", "replace")
    headers = {k.lower(): v for k, v in resp.getheaders()}
    facts: Dict[str, object] = {
        "status": resp.status,
        "title": _clean_title(body),
        "tech": [f"{_TECH_HINTS[k]}: {headers[k]}" for k in _TECH_HINTS if k in headers],
    }
    gen = _GENERATOR_RE.search(body)
    if gen:
        facts["tech"].append("generator-meta: " + gen.group(1).strip()[:120])
    return facts


def _clean_title(body: str) -> str:
    m = _TITLE_RE.search(body)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:200]


def _tls_cert(host: str, port: int = 443, timeout: int = TIMEOUT) -> Dict[str, str]:
    """Grab the presented TLS certificate's identity fields. Never raises."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
        out: Dict[str, str] = {}
        subj = cert.get("subject", ())
        iss = cert.get("issuer", ())
        if subj:
            out["subject"] = ", ".join("=".join(p) for rdn in subj for p in rdn)
        if iss:
            out["issuer"] = ", ".join("=".join(p) for rdn in iss for p in rdn)
        if cert.get("notAfter"):
            out["not_after"] = str(cert["notAfter"])
        sans = cert.get("subjectAltName", ())
        if sans:
            out["sans"] = ", ".join(v for _, v in sans[:10])
        return out
    except Exception:
        return {}


def probe_host(
    host: str,
    store: Optional[ScopeStore] = None,
    ports: Optional[List[int]] = None,
    delay: float = REQUEST_DELAY,
) -> Dict[str, object]:
    """Probe one host. Scope gate runs before the first packet."""
    check_scope(host, store)  # raises ScopeError if out of scope
    ports = ports or COMMON_PORTS

    open_ports: List[int] = []
    for port in ports:
        if _tcp_open(host, port):
            open_ports.append(port)
        time.sleep(delay / 2)

    http_facts: Dict[str, object] = {}
    tls_facts: Dict[str, str] = {}
    web_ports = [p for p in open_ports if p in (80, 8080, 8000, 8888, 3000, 5000, 9000)]
    tls_ports = [p for p in open_ports if p in (443, 8443)]
    for port in web_ports[:3]:
        facts = _http_get(host, port, use_tls=False)
        if facts:
            http_facts[f"http:{port}"] = facts
            break
        time.sleep(delay)
    for port in tls_ports[:2]:
        facts = _http_get(host, port, use_tls=True)
        if facts:
            http_facts[f"https:{port}"] = facts
            break
        time.sleep(delay)
    if 443 in open_ports:
        tls_facts = _tls_cert(host)

    return {
        "host": host,
        "open_ports": open_ports,
        "http": http_facts,
        "tls": tls_facts,
    }
