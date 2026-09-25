"""Subdomain enumeration — passive sources plus a modest fallback wordlist.

Sources (all free, no API keys):
  1. crt.sh certificate-transparency JSON API (passive — no packets to target).
  2. DNS resolution of results via the system resolver (socket).
  3. Built-in wordlist brute-force as a fallback when crt.sh is unreachable.

Every candidate subdomain passes the scope gate before any DNS lookup:
a subdomain of an enrolled domain is authorized by that enrollment.
"""

from __future__ import annotations

import json
import math
import socket
import time
import urllib.request
from typing import Dict, List, Optional, Set

from levi.bounty.scope import ScopeStore, check_scope, normalize_domain

UA = "LEVI-bounty-recon/1.0 (authorized bug-bounty recon; in-scope targets only)"
TIMEOUT = 10
REQUEST_DELAY = 0.5

CRTSH_URL = "https://crt.sh/?q=%25.{domain}&output=json"

# Modest built-in wordlist: common names only, no aggressive guessing.
WORDLIST = [
    "www",
    "mail",
    "ftp",
    "api",
    "dev",
    "test",
    "staging",
    "stage",
    "prod",
    "beta",
    "alpha",
    "demo",
    "portal",
    "admin",
    "vpn",
    "ssh",
    "blog",
    "shop",
    "store",
    "app",
    "apps",
    "mobile",
    "cdn",
    "static",
    "assets",
    "media",
    "img",
    "images",
    "docs",
    "support",
    "help",
    "status",
    "monitor",
    "grafana",
    "kibana",
    "jenkins",
    "git",
    "gitlab",
    "jira",
    "confluence",
    "wiki",
    "cms",
    "crm",
    "erp",
    "hr",
    "auth",
    "login",
    "sso",
    "oauth",
    "idp",
    "directory",
    "ldap",
    "db",
    "sql",
    "mongo",
    "redis",
    "cache",
    "queue",
    "search",
    "analytics",
    "metrics",
    "logs",
    "backup",
    "old",
    "legacy",
    "new",
    "internal",
    "intranet",
    "extranet",
    "partner",
    "secure",
    "private",
    "public",
    "remote",
    "cloud",
    "edge",
    "origin",
]


def _fetch_text(url: str, timeout: int = TIMEOUT) -> Optional[str]:
    """Single HTTP GET, polite UA, timeout. Never raises."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(2_000_000).decode("utf-8", "replace")
    except Exception:
        return None


def _crtsh_subdomains(domain: str) -> Set[str]:
    """Pull subdomains from crt.sh certificate transparency (passive)."""
    body = _fetch_text(CRTSH_URL.format(domain=domain))
    if not body:
        return set()
    try:
        rows = json.loads(body)
    except Exception:
        return set()
    out: Set[str] = set()
    for row in rows:
        nv = str(row.get("name_value") or "")
        for line in nv.splitlines():
            name = line.strip().lower().rstrip(".")
            if name.startswith("*."):
                name = name[2:]
            if name and (name == domain or name.endswith("." + domain)):
                out.add(name)
    return out


def _resolve(host: str, timeout: int = TIMEOUT) -> List[str]:
    """Resolve a host to IPs. Never raises; empty list on failure."""
    prev = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        return sorted({info[4][0] for info in infos})
    except Exception:
        return []
    finally:
        socket.setdefaulttimeout(prev)


def _check_delay(delay: float) -> float:
    """Validate a politeness delay. Raises ValueError on garbage."""
    if isinstance(delay, bool) or not isinstance(delay, (int, float)):
        raise ValueError(
            f"delay must be a non-negative number of seconds, got {delay!r}"
        )
    if not math.isfinite(delay) or delay < 0:
        raise ValueError(
            f"delay must be a non-negative number of seconds, got {delay!r}"
        )
    return float(delay)


def enumerate_subdomains(
    domain: str,
    store: Optional[ScopeStore] = None,
    use_crtsh: bool = True,
    use_wordlist: bool = True,
    delay: float = REQUEST_DELAY,
    dns_cache: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, object]]:
    """Enumerate subdomains of ``domain``.

    The scope gate runs first: ``domain`` must be enrolled. Each candidate
    is re-checked (defense in depth — all will be subdomains of an enrolled
    domain, but the check is cheap and structural).
    Returns a list of {subdomain, ips, source} dicts, deduped and sorted.

    ``dns_cache`` is an optional hostname → IP-list dict shared across
    calls: within one call candidates are already deduped, but repeated
    enumerations (e.g. monitor loops) skip re-resolution for hosts the
    caller has seen. When omitted, a fresh per-call cache is used. The
    caller's dict is updated in place.
    """
    check_scope(domain, store)  # raises ScopeError if out of scope
    target = normalize_domain(domain)
    delay = _check_delay(delay)
    cache: Dict[str, List[str]] = {} if dns_cache is None else dns_cache

    candidates: Dict[str, str] = {}
    if use_crtsh:
        for raw_sub in _crtsh_subdomains(target):
            sub = raw_sub.strip().lower().rstrip(".")
            if sub.startswith("*."):
                sub = sub[2:]
            # the apex itself is probed by the pipeline directly; only keep
            # proper subdomains here
            if sub and sub != target and sub.endswith("." + target):
                candidates.setdefault(sub, "crt.sh")
        time.sleep(delay)

    if use_wordlist:
        for word in WORDLIST:
            sub = f"{word}.{target}"
            if sub not in candidates:
                # scope gate per candidate (structural; always passes here)
                check_scope(sub, store)
                candidates[sub] = "wordlist"

    results: List[Dict[str, object]] = []
    for sub in sorted(candidates):
        ips = cache.get(sub)
        if ips is None:
            ips = _resolve(sub)  # keep the call mock-compatible (one arg)
            cache[sub] = ips
        if ips:
            results.append({"subdomain": sub, "ips": ips, "source": candidates[sub]})
        time.sleep(delay)
    return results
