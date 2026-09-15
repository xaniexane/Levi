"""Deterministic fictional target organizations for LEVI simulations.

Everything in a :class:`SimWorld` is invented and quarantined:

* Domains use the ``.test`` TLD (RFC 2606 — guaranteed non-routable, and
  ``levi.bounty``'s scope regex accepts it), so nothing real is ever
  touched or named.
* IPs come from TEST-NET-3 ``203.0.113.0/24`` (RFC 5737 — documentation
  only, never assigned to a real host).
* Banners, page titles and "exposed secrets" are fictional prose. Planted
  exposures are deliberately fake values (``SIMULATED-FAKE-KEY-...``) that
  only *match the shape* of the detector regexes in ``levi.bounty.content``
  so the real detection logic can be exercised.

A world is a pure function of its integer seed: same seed -> identical
hosts, ports, JS, exposures and archived URLs, via ``random.Random``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from levi.bounty.enum import WORDLIST

# Labels that are deliberately NOT in the bounty wordlist and NOT in the
# simulated crt.sh feed: hosts carrying them are planted assets the real
# pipeline cannot discover (they "don't resolve"), which is what makes the
# coverage metric meaningful.
_DARK_POOL = ["darkops", "quarry", "basalt", "nightdesk", "obsidian", "cinder"]

_TITLES = [
    "SimTarget Customer Portal",
    "SimTarget Status Page",
    "SimTarget API Gateway",
    "SimTarget Developer Docs",
    "SimTarget Billing Console",
    "SimTarget Support Desk",
    "SimTarget Analytics",
    "SimTarget Asset CDN",
    "SimTarget Internal Wiki",
    "SimTarget Staging App",
]

_SERVERS = [
    "nginx/1.24.0 (simulated)",
    "Apache/2.4.57 (simulated)",
    "Caddy/2.7.6 (simulated)",
]

_JS_PATHS = [
    "/static/app.js",
    "/assets/main.js",
    "/js/bundle.js",
    "/static/vendor.js",
    "/assets/chunk.js",
]

_ENDPOINTS = [
    "/api/v1/users",
    "/api/v1/orders",
    "/api/v2/auth/login",
    "/graphql",
    "/rest/search",
    "/internal/metrics",
    "/admin/panel",
    "/v3/billing",
    "/api/v1/tokens",
]

_ARCHIVE_PAGES = [
    "old/about",
    "old/pricing",
    "blog/2019/launch",
    "docs/v1",
    "old/team",
    "old/contact",
    "archive/2021/report",
]

# Fake secret value: matches the *shape* of levi.bounty.content's
# generic_api_key_assign regex but is unmistakably fictional.
_FAKE_API_KEY = "SIMULATED-FAKE-KEY-0123456789ABCDEF"


@dataclass
class SimHost:
    """One fictional host in the simulated target org."""

    fqdn: str
    ips: List[str]
    ports: List[int]
    title: str
    server: str
    js_paths: List[str] = field(default_factory=list)
    endpoints: Dict[str, List[str]] = field(default_factory=dict)
    exposures: Dict[str, str] = field(default_factory=dict)  # js_path -> js body
    discoverable: bool = True


class SimWorld:
    """A deterministic fictional target organization.

    Also acts as the network shim: its methods share signatures with the
    low-level functions in ``levi.bounty.enum`` / ``probe`` / ``content``
    so they can be monkeypatched in place (see :mod:`levi.sim.shims`).
    """

    def __init__(self, seed: int):
        self.seed = int(seed)
        rng = random.Random(self.seed)

        # Sanitized into the domain so it is always a valid hostname and
        # never resembles a real domain: simtarget-<n>.test
        self.domain = f"simtarget-{abs(self.seed) % 100000}.test"

        n_subs = rng.randint(8, 20)
        labels = rng.sample(WORDLIST, n_subs)
        dark_labels = rng.sample(_DARK_POOL, 2)

        self.apex = self._make_host(rng, self.domain, "203.0.113.10", apex=True)
        self.hosts: List[SimHost] = []
        for i, label in enumerate(labels):
            fqdn = f"{label}.{self.domain}"
            self.hosts.append(
                self._make_host(rng, fqdn, f"203.0.113.{11 + i}", apex=False)
            )
        for label in dark_labels:
            fqdn = f"{label}.{self.domain}"
            host = self._make_host(rng, fqdn, "203.0.113.240", apex=False)
            host.discoverable = False
            self.hosts.append(host)

        # Plant 0-2 exposures on JS files of *discoverable* hosts so the
        # real exposure detector has something to flag.
        discoverable = [h for h in [self.apex, *self.hosts] if h.discoverable]
        n_exp = rng.randint(0, 2)
        chosen = rng.sample(
            [(h, p) for h in discoverable for p in h.js_paths],
            min(n_exp, sum(len(h.js_paths) for h in discoverable)),
        )
        for host, path in chosen:
            eps = sorted(rng.sample(_ENDPOINTS, rng.randint(2, 4)))
            host.exposures[path] = self._js_body(path, eps, exposed=True)
        self.planted_exposures = len(chosen)

        # DNS view: only discoverable hosts resolve.
        self._dns: Dict[str, List[str]] = {
            h.fqdn: h.ips for h in [self.apex, *self.hosts] if h.discoverable
        }
        self._by_fqdn: Dict[str, SimHost] = {
            h.fqdn: h for h in [self.apex, *self.hosts]
        }

        # crt.sh feed: the apex plus a random subset of discoverable subs.
        crtsh_hosts = [self.domain] + [
            h.fqdn
            for h in self.hosts
            if h.discoverable and rng.random() < 0.5
        ]
        self._crtsh_json = json.dumps(
            [{"name_value": fqdn} for fqdn in sorted(set(crtsh_hosts))]
        )

        # Wayback feed: a handful of archived URLs.
        archived = []
        pool = [self.apex, *[h for h in self.hosts if h.discoverable]]
        for _ in range(rng.randint(4, 10)):
            h = rng.choice(pool)
            page = rng.choice(_ARCHIVE_PAGES)
            archived.append(f"http://{h.fqdn}/{page}")
        rows = [["urlkey", "timestamp", "original", "mimetype",
                 "statuscode", "digest", "length"]]
        for url in sorted(set(archived)):
            rows.append([url, "20240101000000", url, "text/html", "200", "-", "-"])
        self._cdx_json = json.dumps(rows)
        self.archived_urls = sorted(set(archived))

        # JS bodies keyed by every URL the pipeline could construct for them
        # (http/https x web/tls port), so harvest_js always hits.
        self._js_urls: Dict[str, str] = {}
        for host in [self.apex, *self.hosts]:
            for path in host.js_paths:
                body = host.exposures.get(path) or self._js_body(
                    path, host.endpoints[path]
                )
                for port in host.ports:
                    scheme = "https" if port in (443, 8443) else "http"
                    if scheme == "https" and port not in (443, 8443):
                        continue
                    if scheme == "http" and port in (443, 8443):
                        continue
                    self._js_urls[f"{scheme}://{host.fqdn}:{port}{path}"] = body

    # -- world construction -------------------------------------------------
    def _make_host(self, rng: random.Random, fqdn: str, ip: str, apex: bool) -> SimHost:
        if apex:
            ports = [80, 443]
        else:
            web = rng.choice([80, 8080, 8000, 3000, 5000])
            tls = rng.choice([443, 8443, None, None])
            ports = sorted([web] + ([tls] if tls else []))
        js_paths = rng.sample(_JS_PATHS, rng.randint(1, 2))
        endpoints = {
            p: sorted(rng.sample(_ENDPOINTS, rng.randint(2, 4))) for p in js_paths
        }
        return SimHost(
            fqdn=fqdn,
            ips=[ip],
            ports=ports,
            title=rng.choice(_TITLES),
            server=rng.choice(_SERVERS),
            js_paths=js_paths,
            endpoints=endpoints,
        )

    @staticmethod
    def _js_body(path: str, endpoints: List[str], exposed: bool = False) -> str:
        eps = ",\n  ".join(f'"{e}"' for e in endpoints)
        if exposed:
            return (
                "// simulated config - fictional values only, never real secrets\n"
                "window.SIM_CONFIG = {\n"
                '  api_base: "/api/v1",\n'
                f'  api_key: "{_FAKE_API_KEY}",\n'
                f"  endpoints: [\n  {eps}\n  ]\n"
                "};\n"
            )
        return (
            f"// {path} - simulated bundle\n"
            "(function(){\n"
            f"  var ENDPOINTS = [\n  {eps}\n  ];\n"
            "  console.log('sim bundle loaded');\n"
            "})();\n"
        )

    def _html(self, host: SimHost) -> str:
        scripts = "\n".join(
            f'<script src="{p}"></script>' for p in host.js_paths
        )
        return (
            "<html><head>"
            f"<title>{host.title}</title>"
            '<meta name="generator" content="SimPress 1.2 (fictional)">'
            "</head><body>"
            f"<h1>{host.title}</h1>"
            f"<p>Simulated page for {host.fqdn}. Nothing here is real.</p>"
            f"{scripts}"
            "</body></html>"
        )

    # -- shim surface: signatures mirror the real low-level functions ------
    def fetch_text(self, url: str, timeout: int = 10) -> Optional[str]:
        """Serve crt.sh / Wayback / JS URLs from the world. Never raises."""
        if url.startswith("https://crt.sh/"):
            return self._crtsh_json if self.domain in url else "[]"
        if "web.archive.org" in url:
            return self._cdx_json
        body = self._js_urls.get(url)
        if body is not None:
            return body
        return None

    def wayback(self, domain: str, delay: float = 0.5) -> List[str]:
        """Simulated Wayback CDX results. Never raises."""
        if domain == self.domain:
            return list(self.archived_urls)
        return []

    def resolve(self, host: str, timeout: int = 10) -> List[str]:
        """Simulated DNS: only discoverable hosts resolve. Never raises."""
        return list(self._dns.get(host, []))

    def tcp_open(self, host: str, port: int, timeout: int = 8) -> bool:
        """Simulated TCP connect: open iff the world says so. Never raises."""
        rec = self._by_fqdn.get(host)
        return bool(rec and port in rec.ports)

    def http_get(
        self, host: str, port: int, use_tls: bool, timeout: int = 8
    ) -> Optional[Dict[str, object]]:
        """Simulated GET /: response facts for open web ports. Never raises."""
        rec = self._by_fqdn.get(host)
        if not rec or port not in rec.ports:
            return None
        scheme = "https" if use_tls else "http"
        url = f"{scheme}://{host}:{port}/"
        return {
            "status": 200,
            "title": rec.title,
            "tech": [
                f"server: {rec.server}",
                "generator-meta: SimPress 1.2 (fictional)",
            ],
            "body": self._html(rec),
            "url": url,
        }

    def tls_cert(self, host: str, port: int = 443, timeout: int = 8) -> Dict[str, str]:
        """Simulated TLS certificate. Never raises."""
        rec = self._by_fqdn.get(host)
        if not rec or port not in rec.ports:
            return {}
        return {
            "subject": f"CN={host}",
            "issuer": "CN=LEVI Sim CA (fictional)",
            "not_after": "Jan  1 00:00:00 2030 GMT",
            "sans": host,
        }
