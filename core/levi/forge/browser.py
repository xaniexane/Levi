"""The Forge browser — LEVI's browsing surface.

A pure LEVI-native recreation of the browser as an *operated surface*,
not an embedded engine. There is no Chromium here, no JavaScript runtime,
no pretending to click what can't be clicked. What the surface does:

* **Fetch pages as data** — stdlib ``urllib`` transport with a session
  cookie jar, a redirect cap, charset sniffing, and a size ceiling.
  Non-document content types and non-http(s) schemes are refused,
  deny-closed, with the refusal on the record.
* **Render to readable text** — a stdlib ``html.parser`` renderer that
  drops scripts/styles entirely and emits headings, lists, paragraphs,
  and numbered link markers. This is the *reading* view; the raw HTML is
  never shown as the page.
* **Navigate as structured actions** — links become a numbered table
  (``follow(2)``), forms become field descriptors (``submit("f0", {...})``).
  History stacks give ``back()``/``forward()``. Nothing is "clicked".
* **Receipt every navigation** — open/follow/back/forward ride the rail
  at LOW; form GET submits at MODERATE, POST submits at HIGH.
* **Injection law** — page content is DATA, never instructions. The
  surface never executes scripts, never evals page text, and runs a
  heuristic directive scan whose flags travel on the Page and in the
  receipt so downstream minds know the text is untrusted.

What this is not:

* ``levi.forge.browse`` — that browses *git repositories*. This browses
  the web. Different module, different world.
* ``levi.automation.browser`` — that emits browser-automation *plans*
  and never opens a URL. This opens URLs (as documents).
* ``levi.agent.tools`` web_search/web_fetch — raw transport primitives
  for the agent loop. This is the structured surface with rendering,
  navigation state, and receipts.

Honest limits: pages that require JavaScript to render their content
are read as their served HTML — the surface says so in the receipt
(``scripts_dropped``) instead of pretending otherwise.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..policy.gates import RiskLevel
from .rail import NeedsApprovalError, Rail, RailError, jsonl_sink, machine_root

ORIGIN = "levi-forge/browser"

USER_AGENT = "LEVI-forge-browser/1.0 (LEVI-native surface; +local)"
DEFAULT_TIMEOUT = 15.0
MAX_BYTES = 1_000_000
MAX_REDIRECTS = 5

#: Content types the surface renders as documents. Anything else is
#: refused — the surface reads pages, not binaries.
DOCUMENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")

#: Heuristic directive shapes flagged by the injection-law scan. A flag is
#: metadata on untrusted data — the text itself is never censored, never
#: executed, never obeyed.
_DIRECTIVE_PATTERNS = (
    (
        "ignore-prior-instructions",
        re.compile(
            r"ignore\s+(all\s+|any\s+)?(previous|prior|earlier)\s+instructions", re.I
        ),
    ),
    ("disregard-instructions", re.compile(r"disregard\s+.*instructions", re.I)),
    (
        "imperative-to-agent",
        re.compile(
            r"\byou\s+(must|should|will|are\s+required\s+to)\b.{0,60}\b(reveal|disclose|send|execute|run|delete|ignore|forget|bypass)\b",
            re.I | re.S,
        ),
    ),
    (
        "system-prompt-claim",
        re.compile(r"\b(system\s+prompt|your\s+instructions\s+are)\b", re.I),
    ),
    (
        "fake-authority",
        re.compile(
            r"\b(as\s+an?\s+(ai|assistant|language\s+model).{0,40}(i\s+(must|order|command)|you\s+must))\b",
            re.I | re.S,
        ),
    ),
)


class BrowserError(Exception):
    """Base error for the browsing surface."""


class FetchError(BrowserError):
    """The page could not be fetched or is not a renderable document."""


# ---------------------------------------------------------------------------
# Readable-text renderer
# ---------------------------------------------------------------------------


class _TextRenderer(HTMLParser):
    """stdlib HTML → readable text with numbered link markers.

    Scripts, styles and noscript blocks are dropped entirely — never
    rendered, never executed, never even kept.
    """

    _BLOCKS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "blockquote",
        "pre",
        "table",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "br",
        "hr",
        "figure",
        "figcaption",
        "nav",
        "aside",
    }
    _DROPPED = {"script", "style", "noscript", "template"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self._in_title = False
        self._drop_depth = 0
        self._chunks: List[str] = []
        self._link_stack: List[Dict[str, Any]] = []
        self.links: List[Dict[str, str]] = []
        self.forms: List[Dict[str, Any]] = []
        self._form: Optional[Dict[str, Any]] = None
        self._select: Optional[Dict[str, Any]] = None
        self._in_pre = False
        self._in_heading: Optional[str] = None
        self.scripts_dropped = 0

    # -- helpers ---------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._drop_depth:
            return
        self._chunks.append(text)

    def _break(self) -> None:
        if self._drop_depth:
            return
        if self._chunks and not self._chunks[-1].endswith("\n"):
            self._chunks.append("\n")

    # -- parser hooks ------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        at = dict(attrs)
        if tag in self._DROPPED:
            self._drop_depth += 1
            self.scripts_dropped += 1
            return
        if self._drop_depth:
            return
        if tag == "title":
            self._in_title = True
        elif tag == "a":
            href = (at.get("href") or "").strip()
            if href and not href.startswith(("#", "javascript:")):
                self._link_stack.append(
                    {
                        "href": urllib.parse.urljoin(self.base_url, href),
                        "text": "",
                    }
                )
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._break()
            self._in_heading = tag
            self._emit("#" * int(tag[1]) + " ")
        elif tag == "li":
            self._break()
            self._emit("- ")
        elif tag == "pre":
            self._in_pre = True
            self._break()
        elif tag == "br":
            self._emit("\n")
        elif tag == "hr":
            self._break()
            self._emit("—" * 8 + "\n")
        elif tag == "img":
            alt = (at.get("alt") or "").strip()
            self._emit(f"[image{': ' + alt if alt else ''}]")
        elif tag == "form":
            self._form = {
                "id": f"f{len(self.forms)}",
                "action": urllib.parse.urljoin(
                    self.base_url, (at.get("action") or "").strip()
                ),
                "method": (at.get("method") or "get").strip().lower() or "get",
                "fields": [],
            }
        elif tag == "input" and self._form is not None:
            self._form["fields"].append(
                {
                    "name": at.get("name") or "",
                    "type": (at.get("type") or "text").lower(),
                    "value": at.get("value") or "",
                }
            )
        elif tag == "textarea" and self._form is not None:
            self._form["fields"].append(
                {
                    "name": at.get("name") or "",
                    "type": "textarea",
                    "value": "",
                }
            )
        elif tag == "select" and self._form is not None:
            self._select = {"name": at.get("name") or "", "options": []}
        elif tag == "option" and self._select is not None:
            self._select["options"].append(at.get("value") or "")
        elif tag in self._BLOCKS:
            self._break()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._DROPPED:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth:
            return
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._link_stack:
            link = self._link_stack.pop()
            text = " ".join(link["text"].split())
            if text:
                n = len(self.links)
                self.links.append({"text": text, "href": link["href"]})
                self._emit(f"[{n}]")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = None
            self._break()
        elif tag == "pre":
            self._in_pre = False
            self._break()
        elif tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None
        elif tag == "select" and self._select is not None and self._form is not None:
            self._form["fields"].append(
                {
                    "name": self._select["name"],
                    "type": "select",
                    "value": "",
                    "options": self._select["options"],
                }
            )
            self._select = None
        elif tag in self._BLOCKS:
            self._break()

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        if self._in_title:
            self.title += data
            return
        if self._link_stack:
            self._link_stack[-1]["text"] += data
        if self._in_pre:
            self._emit(data)
        else:
            # collapse inline whitespace; block breaks already emitted
            self._emit(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        raw = "".join(self._chunks)
        # collapse 3+ newlines, strip trailing space per line
        lines = [ln.rstrip() for ln in raw.split("\n")]
        out: List[str] = []
        blank = 0
        for ln in lines:
            if not ln.strip():
                blank += 1
                if blank <= 1:
                    out.append("")
                continue
            blank = 0
            out.append(ln)
        return "\n".join(out).strip("\n")


def _directive_scan(text: str) -> List[Dict[str, str]]:
    """Flag instruction-shaped content. Heuristic, documented, non-censoring."""
    flags: List[Dict[str, str]] = []
    for kind, pattern in _DIRECTIVE_PATTERNS:
        m = pattern.search(text)
        if m:
            snippet = " ".join(m.group(0).split())[:120]
            flags.append({"kind": kind, "snippet": snippet})
    return flags


# ---------------------------------------------------------------------------
# Pages and the browser
# ---------------------------------------------------------------------------


@dataclass
class Page:
    """A fetched document. All content fields are DATA — never instructions."""

    url: str
    final_url: str
    status: int
    content_type: str
    title: str
    text: str
    links: List[Dict[str, str]] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: str = ""
    sha256: str = ""
    scripts_dropped: int = 0
    directive_flags: List[Dict[str, str]] = field(default_factory=list)
    provenance: str = "untrusted-page-content"

    def describe(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "title": self.title,
            "text_chars": len(self.text),
            "links": len(self.links),
            "forms": len(self.forms),
            "sha256": self.sha256,
            "directive_flags": [f["kind"] for f in self.directive_flags],
            "provenance": self.provenance,
        }


class _RedirectCap(urllib.request.HTTPRedirectHandler):
    """Refuse redirect chains past the cap and off http(s) — deny-closed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if getattr(req, "_levi_hops", 0) >= MAX_REDIRECTS:
            raise FetchError(f"redirect chain past {MAX_REDIRECTS} hops — refused")
        parsed = urllib.parse.urlparse(urllib.parse.urljoin(req.full_url, newurl))
        if parsed.scheme not in ("http", "https"):
            raise FetchError(
                f"redirect to non-http(s) scheme refused: {parsed.scheme!r}"
            )
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        new_req._levi_hops = getattr(req, "_levi_hops", 0) + 1  # type: ignore[attr-defined]
        return new_req


class Browser:
    """LEVI's browsing surface: documents, structured navigation, receipts."""

    def __init__(
        self,
        home: "str | Path | None" = None,
        *,
        rail: Optional[Rail] = None,
        actor: str = "operator",
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        self.home = home
        self.state_dir = machine_root(home, "browser")
        self.rail = rail or Rail(
            receipt_sink=jsonl_sink(self.state_dir / "receipts.jsonl"),
            actor=actor,
        )
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            _RedirectCap(),
            urllib.request.HTTPCookieProcessor(self._cookies),
        )
        self._opener.addheaders = [("User-Agent", USER_AGENT)]
        self._history: List[Page] = []
        self._index = -1
        self._pending: Dict[str, Dict[str, Any]] = {}

    # -- transport -----------------------------------------------------------
    @staticmethod
    def _check_url(url: str) -> str:
        url = (url or "").strip()
        if not url:
            raise FetchError("empty URL")
        parts = urllib.parse.urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError(f"only http(s) URLs are fetchable: {url!r}")
        return url

    @staticmethod
    def _charset(content_type: str, head: bytes) -> str:
        m = re.search(r"charset=([^\s;\"']+)", content_type or "", re.I)
        if m:
            return m.group(1)
        m = re.search(rb"<meta[^>]+charset=[\"']?([a-zA-Z0-9_-]+)", head[:4096], re.I)
        if m:
            return m.group(1).decode("ascii", "replace")
        return "utf-8"

    def _fetch(
        self, url: str, *, data: Optional[bytes] = None, method: Optional[str] = None
    ) -> Page:
        url = self._check_url(url)
        req = urllib.request.Request(url, data=data, method=method)
        req._levi_hops = 0  # type: ignore[attr-defined]
        try:
            resp = self._opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} for {url}") from None
        except FetchError:
            raise
        except Exception as exc:  # noqa: BLE001 — transport failures are data
            raise FetchError(f"fetch failed for {url}: {exc}") from None
        with resp:
            ctype = (
                (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            )
            if ctype and not (ctype in DOCUMENT_TYPES or ctype.startswith("text/")):
                raise FetchError(
                    f"refused non-document content type {ctype!r} for {url} — "
                    "the surface reads pages, not binaries"
                )
            raw = resp.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                raise FetchError(f"page exceeds {self.max_bytes} bytes — refused")
            if b"\x00" in raw[:4096]:
                raise FetchError(f"binary content refused for {url}")
            final_url = resp.geturl()
            status = resp.status
        text_raw = raw.decode(self._charset(ctype, raw), errors="replace")
        renderer = _TextRenderer(final_url)
        try:
            renderer.feed(text_raw)
            renderer.close()
        except Exception as exc:  # noqa: BLE001 — malformed HTML still yields a page
            raise FetchError(f"could not parse page {url}: {exc}") from None
        text = renderer.text()
        flags = _directive_scan(text)
        return Page(
            url=url,
            final_url=final_url,
            status=status,
            content_type=ctype or "text/html",
            title=" ".join(renderer.title.split()),
            text=text,
            links=renderer.links,
            forms=renderer.forms,
            fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            sha256=hashlib.sha256(raw).hexdigest(),
            scripts_dropped=renderer.scripts_dropped,
            directive_flags=flags,
        )

    # -- rail plumbing ---------------------------------------------------------
    def _navigated(self, page: Page) -> None:
        """Push a fetched page onto the history stack."""
        self._history = self._history[: self._index + 1]
        self._history.append(page)
        self._index = len(self._history) - 1

    def _receipt_details(self, page: Page) -> Dict[str, Any]:
        return {
            **page.describe(),
            "scripts_dropped": page.scripts_dropped,
            "directive_flag_kinds": [f["kind"] for f in page.directive_flags],
        }

    def _execute_navigation(self, proposal_id: str, fetch: "callable") -> Page:
        """Run an approved navigation: fetch, verify, receipt, push history.

        Fetch failures are receipted (verified=False) and then re-raised as
        their original error — the receipt records it, the caller feels it.
        """
        holder: Dict[str, Any] = {}

        def _fn():
            try:
                page = fetch()
            except Exception as exc:  # noqa: BLE001 — stashed, then re-raised
                holder["error"] = exc
                raise
            holder["page"] = page
            return (
                f"fetched {page.final_url} (HTTP {page.status})",
                self._receipt_details(page),
            )

        def _verify(details):
            ok = 200 <= details.get("status", 0) < 400
            return ok, f"HTTP {details.get('status')}"

        receipt = self.rail.execute(proposal_id, _fn, verify=_verify)
        if "page" not in holder:
            raise holder.get(
                "error", BrowserError(f"navigation failed: {receipt.outcome}")
            )
        page = holder["page"]
        if receipt.verified:
            self._navigated(page)
        return page

    # -- operator decisions ------------------------------------------------------
    def preview(self, proposal_id: str) -> Dict[str, Any]:
        return self.rail.preview(proposal_id)

    def permit(self, proposal_id: str):
        return self.rail.permit(proposal_id)

    def approve(self, proposal_id: str, note: str = "") -> None:
        self.rail.approve(proposal_id, note=note)

    def deny(self, proposal_id: str, note: str = "") -> None:
        self.rail.deny(proposal_id, note=note)

    # -- the surface -------------------------------------------------------------
    @property
    def current(self) -> Optional[Page]:
        if 0 <= self._index < len(self._history):
            return self._history[self._index]
        return None

    def open(self, url: str) -> Page:
        """Fetch a page as a document. LOW — auto-approved, receipted."""
        try:
            url = self._check_url(url)
        except FetchError as exc:
            self.rail.deny_closed(tool="browser.open", reason=str(exc))
        pid = self.rail.plan(
            tool="browser.open",
            description=f"open {url}",
            risk=RiskLevel.LOW,
            reason="read-only document fetch",
            affected=["browser:open"],
            impact=f"fetches {url} as a document (no scripts run)",
            artifacts={"url": url},
        )
        self.rail.permit(pid)  # LOW auto-approves; raises otherwise
        return self._execute_navigation(pid, lambda: self._fetch(url))

    def follow(self, n: int) -> Page:
        """Follow link number *n* from the current page's link table."""
        page = self.current
        if page is None:
            raise BrowserError("follow: no page open")
        try:
            n = int(n)
        except (TypeError, ValueError):
            raise BrowserError(
                f"follow: link number must be an int, got {n!r}"
            ) from None
        if not 0 <= n < len(page.links):
            raise BrowserError(
                f"follow: link [{n}] does not exist (page has {len(page.links)} links)"
            )
        target = page.links[n]
        pid = self.rail.plan(
            tool="browser.follow",
            description=f"follow [{n}] {target['text'][:60]!r} → {target['href']}",
            risk=RiskLevel.LOW,
            reason="read-only navigation within the link table",
            affected=["browser:follow"],
            impact=f"fetches {target['href']}",
            artifacts={"link": n, "href": target["href"]},
        )
        self.rail.permit(pid)
        return self._execute_navigation(pid, lambda: self._fetch(target["href"]))

    def back(self) -> Page:
        return self._step(-1, "browser.back")

    def forward(self) -> Page:
        return self._step(1, "browser.forward")

    def _step(self, delta: int, tool: str) -> Page:
        new_index = self._index + delta
        if not 0 <= new_index < len(self._history):
            raise BrowserError(
                f"{tool}: no {'earlier' if delta < 0 else 'later'} page in history"
            )
        page = self._history[new_index]
        pid = self.rail.plan(
            tool=tool,
            description=f"history {'back' if delta < 0 else 'forward'} → {page.final_url}",
            risk=RiskLevel.LOW,
            reason="history navigation re-renders a fetched document; no fetch",
            affected=["browser:history"],
            artifacts={"url": page.final_url},
        )
        self.rail.permit(pid)

        def _fn():
            return f"history → {page.final_url}", self._receipt_details(page)

        self.rail.execute(pid, _fn)
        self._index = new_index
        return page

    def describe_forms(self) -> List[Dict[str, Any]]:
        """Structured form descriptors for the current page (read-only)."""
        page = self.current
        if page is None:
            raise BrowserError("describe_forms: no page open")
        pid = self.rail.plan(
            tool="browser.describe_forms",
            description=f"describe {len(page.forms)} form(s) on {page.final_url}",
            risk=RiskLevel.INFO,
            reason="read-only inspection of already-fetched structure",
            affected=["browser:forms"],
        )
        self.rail.permit(pid)

        def _fn():
            return f"{len(page.forms)} form(s)", {"forms": len(page.forms)}

        self.rail.execute(pid, _fn)
        return page.forms

    def submit(self, form_id: str, values: Dict[str, str]) -> Page:
        """Submit a form as a structured action. GET→MODERATE, POST→HIGH.

        Both wait for explicit operator approval — submitting a form sends
        operator-supplied data to someone else's server, unlike following a
        link the page offered. NeedsApprovalError carries the proposal id:
        approve it, then call ``run_pending(pid)``.
        """
        page = self.current
        if page is None:
            raise BrowserError("submit: no page open")
        form = next((f for f in page.forms if f["id"] == form_id), None)
        if form is None:
            raise BrowserError(
                f"submit: no form {form_id!r} on this page "
                f"(have: {[f['id'] for f in page.forms]})"
            )
        if not isinstance(values, dict):
            raise BrowserError("submit: 'values' must be a dict of field→value")
        fields: Dict[str, str] = {}
        for fld in form["fields"]:
            name = fld.get("name")
            if not name or fld.get("type") in ("submit", "button", "reset"):
                continue
            fields[name] = str(values.get(name, fld.get("value", "")))
        method = form["method"]
        action = form["action"] or page.final_url
        if method == "get":
            query = urllib.parse.urlencode(fields)
            target = action + ("&" if "?" in action else "?") + query
            data, req_method = None, "GET"
            risk = RiskLevel.MODERATE
        elif method == "post":
            target, data, req_method = (
                action,
                urllib.parse.urlencode(fields).encode(),
                "POST",
            )
            risk = RiskLevel.HIGH
        else:
            raise BrowserError(f"submit: unsupported form method {method!r}")
        pid = self.rail.plan(
            tool="browser.submit",
            description=f"submit {form_id} ({method.upper()}) → {target}",
            risk=risk,
            reason="form submission sends operator-supplied data to the site",
            affected=["browser:submit"],
            impact=f"{method.upper()} {target} with {len(fields)} field(s)",
            reversible=False,
            artifacts={
                "form": form_id,
                "method": method,
                "target": target,
                "fields": sorted(fields),
            },
        )
        decided = self.rail.permit(pid)
        self._pending[pid] = {"target": target, "data": data, "method": req_method}
        if decided.status.value == "awaiting_permission":
            raise NeedsApprovalError(
                f"browser.submit ({method.upper()}) needs explicit operator "
                f"approval — proposal {pid}"
            )
        return self.run_pending(pid)

    def run_pending(self, proposal_id: str) -> Page:
        """Execute an approved pending navigation (e.g. an approved POST)."""
        pending = self._pending.get(proposal_id)
        if pending is None:
            raise RailError(f"run_pending: unknown pending navigation {proposal_id!r}")
        page = self._execute_navigation(
            proposal_id,
            lambda: self._fetch(
                pending["target"], data=pending["data"], method=pending["method"]
            ),
        )
        self._pending.pop(proposal_id, None)
        return page

    def find(self, pattern: str) -> List[Dict[str, Any]]:
        """Search the current page's readable text (read-only)."""
        page = self.current
        if page is None:
            raise BrowserError("find: no page open")
        try:
            rx = re.compile(pattern, re.I)
        except re.error as exc:
            raise BrowserError(f"find: bad pattern: {exc}") from None
        hits = []
        for i, line in enumerate(page.text.split("\n")):
            if rx.search(line):
                hits.append({"line": i + 1, "text": line.strip()[:200]})
                if len(hits) >= 50:
                    break
        pid = self.rail.plan(
            tool="browser.find",
            description=f"find {pattern!r} on {page.final_url}",
            risk=RiskLevel.INFO,
            reason="read-only search over fetched text",
            affected=["browser:find"],
        )
        self.rail.permit(pid)

        def _fn():
            return f"{len(hits)} hit(s)", {"hits": len(hits)}

        self.rail.execute(pid, _fn)
        return hits

    def history(self) -> List[Dict[str, Any]]:
        """The session's navigation history (receipted read)."""
        pid = self.rail.plan(
            tool="browser.history",
            description="list navigation history",
            risk=RiskLevel.INFO,
            reason="read-only session inspection",
            affected=["browser:history"],
        )
        self.rail.permit(pid)

        def _fn():
            return f"{len(self._history)} page(s) in history", {
                "pages": len(self._history)
            }

        self.rail.execute(pid, _fn)
        return [
            {**p.describe(), "current": i == self._index}
            for i, p in enumerate(self._history)
        ]


def open_browser(home: "str | Path | None" = None, **kwargs) -> Browser:
    """Open the Forge browsing surface (state under ``~/.levi/forge/machine/browser/``)."""
    return Browser(home, **kwargs)
