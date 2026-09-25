"""static_deploy — build-locally, sync-deltas, serve-statically deployment plan.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 3,
static sites: build HTML, sync to a server, automatic TLS; deletes platform
subscriptions and bandwidth-overage tail-risk).

Functional pattern studied: deployment as a pure function of content —
render pages locally, fingerprint every file, ship only what changed since
the last manifest, and serve the result from a plain web server with
automatic TLS. The cost saving is structural: no build minutes, no
per-seat platform fees, no bandwidth overage surprises.

What this module is: the planning half of that pattern, with no network.
``build()`` renders a site from page sources into hashed output files;
``Manifest`` fingerprints them; ``DeltaPlan`` diffs two manifests into an
add/modify/delete transfer list with byte totals (the rsync-style minimal
transfer set); ``tls_config()`` renders a Caddy-style static-site block
with automatic TLS and sane security headers. Shipping the bytes is the
operator's transport step — the module tells them exactly which bytes.

Honest limits: rendering here is deliberately simple (title + body to HTML
with escaping) — a real generator pipeline plugs in at ``Renderer``. The
delta math is exact for the files given; it cannot see files the operator
never listed.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass, field
from typing import Callable, Dict, List

ORIGIN = "levi-revival/static-deploy"


@dataclass
class Page:
    """One source page."""

    path: str  # e.g. "index.html" (relative, no leading slash)
    title: str
    body: str  # pre-sanitized markup or plain text
    raw_html: bool = False


@dataclass
class BuiltFile:
    path: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def size(self) -> int:
        return len(self.content)


Renderer = Callable[[Page], bytes]


def default_renderer(page: Page) -> bytes:
    """Minimal honest renderer: title + body into a valid HTML document."""
    body = page.body if page.raw_html else html.escape(page.body)
    doc = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        f'<meta charset="utf-8">\n<title>{html.escape(page.title)}</title>\n'
        "</head>\n<body>\n"
        f"<h1>{html.escape(page.title)}</h1>\n<div>{body}</div>\n"
        "</body>\n</html>\n"
    )
    return doc.encode("utf-8")


@dataclass
class Site:
    name: str
    pages: List[Page] = field(default_factory=list)
    renderer: Renderer = default_renderer

    def build(self) -> List[BuiltFile]:
        """Render every page locally. Pure function of the sources."""
        seen = set()
        out: List[BuiltFile] = []
        for page in self.pages:
            if page.path in seen:
                raise ValueError(f"duplicate page path: {page.path}")
            if page.path.startswith("/") or ".." in page.path.split("/"):
                raise ValueError(f"unsafe page path: {page.path}")
            seen.add(page.path)
            out.append(BuiltFile(path=page.path, content=self.renderer(page)))
        return out


@dataclass
class Manifest:
    """Fingerprint of a built site: path -> (sha256, size)."""

    files: Dict[str, tuple] = field(default_factory=dict)  # path -> (sha, size)

    @classmethod
    def from_build(cls, built: List[BuiltFile]) -> "Manifest":
        return cls(files={f.path: (f.sha256, f.size) for f in built})

    def __len__(self) -> int:
        return len(self.files)


@dataclass
class Transfer:
    path: str
    action: str  # "add" | "modify" | "delete"
    bytes: int  # bytes to transfer (0 for delete)


@dataclass
class DeltaPlan:
    """Minimal transfer set between two manifests."""

    transfers: List[Transfer] = field(default_factory=list)

    @classmethod
    def diff(cls, old: Manifest, new: Manifest) -> "DeltaPlan":
        transfers: List[Transfer] = []
        for path, (sha, size) in new.files.items():
            if path not in old.files:
                transfers.append(Transfer(path, "add", size))
            elif old.files[path][0] != sha:
                transfers.append(Transfer(path, "modify", size))
        for path in old.files:
            if path not in new.files:
                transfers.append(Transfer(path, "delete", 0))
        transfers.sort(key=lambda t: (t.action, t.path))
        return cls(transfers=transfers)

    @property
    def upload_bytes(self) -> int:
        return sum(t.bytes for t in self.transfers if t.action in ("add", "modify"))

    @property
    def is_noop(self) -> bool:
        return not self.transfers

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"add": 0, "modify": 0, "delete": 0}
        for t in self.transfers:
            counts[t.action] += 1
        counts["upload_bytes"] = self.upload_bytes
        return counts


def tls_config(site_name: str, domain: str, root: str = "/var/www") -> str:
    """Render a static-site server block: automatic TLS, compression-ready,
    sane security headers. The operator pastes it into their server config;
    this module performs no network I/O and touches no server."""
    site_root = f"{root}/{site_name}".rstrip("/")
    return (
        f"# {site_name} — static site, automatic TLS\n"
        f"{domain} {{\n"
        f"    root * {site_root}\n"
        "    encode gzip\n"
        "    file_server\n"
        "    # automatic TLS: certificate issued and renewed by the server\n"
        "    header {\n"
        "        X-Content-Type-Options nosniff\n"
        "        X-Frame-Options DENY\n"
        "        Referrer-Policy strict-origin-when-cross-origin\n"
        "        -Server\n"
        "    }\n"
        "}\n"
    )


def deploy_script(site_name: str, plan: DeltaPlan, remote: str) -> str:
    """Render the operator's sync commands for a delta plan.

    Pure text generation — the operator reviews and runs it. ``remote`` is a
    transport target like ``user@host:/var/www/<site>``.
    """
    lines = [
        f"# deploy {site_name} -> {remote}",
        f"# {len(plan.transfers)} change(s), {plan.upload_bytes} byte(s) to upload",
    ]
    for t in plan.transfers:
        if t.action == "delete":
            lines.append(f"# delete remote file: {t.path}")
        else:
            lines.append(f"put {t.path}  # {t.action}, {t.bytes} bytes")
    return "\n".join(lines) + "\n"
