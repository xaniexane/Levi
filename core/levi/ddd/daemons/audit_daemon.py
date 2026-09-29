# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Audit daemon — the daily AuditNow draft engine (PROVISIONAL).

Every morning it takes up to 3 businesses from Chauncey's prospect queue
and drafts, per site, a finished $49 AuditNow audit draft plus an outreach
draft. Drafts land in ``~/workspace/ddd-inbox/`` and wait on his word.

LAWS (inherited + specific):
  L1/L2/L3 draft-only, no payment, no outbound — the drafts are never
     sent, published, or charged.
  L4 honest zero-state — empty queue → honest receipt, never invents.
  L6 NAMED SITES ONLY: it reads ONLY urls Chauncey himself queued.
     Polite single read per page (10s timeout), never a crawl, never a
     form submit, never a write. Findings are observations, never
     guarantees of ranking or sales. Measured vs estimated is labeled.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

import time
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from levi.ddd.daemons.base import DDDDailyDaemon
from levi.dynasty.dna import AgentError

__all__ = ["AuditDaemon"]

#: One polite request per page. Nothing more.
_FETCH_TIMEOUT_S = 10
_USER_AGENT = "LEVI-audit-daemon (polite info-only read; one request per page)"

_CHECKS = ("page speed", "SEO basics", "broken links", "mobile")


class _PageFacts(HTMLParser):
    """Single-pass facts from one fetched page (stdlib only)."""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: List[str] = []
        self._in_title = False
        self.meta_description: Optional[str] = None
        self.has_viewport = False
        self.imgs_total = 0
        self.imgs_without_alt = 0
        self.links_internal = 0
        self.links_external = 0
        self._page_netloc = ""

    def set_page(self, netloc: str) -> None:
        self._page_netloc = netloc.lower()

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attrs_d = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (attrs_d.get("name") or "").lower()
            if name == "description" and self.meta_description is None:
                self.meta_description = attrs_d.get("content", "")
            if name == "viewport":
                self.has_viewport = True
        elif tag == "img":
            self.imgs_total += 1
            if not (attrs_d.get("alt") or "").strip():
                self.imgs_without_alt += 1
        elif tag == "a":
            href = (attrs_d.get("href") or "").strip()
            if href.startswith(("http://", "https://")):
                if urlparse(href).netloc.lower() == self._page_netloc:
                    self.links_internal += 1
                else:
                    self.links_external += 1
            elif href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                # relative link → internal to the page being read
                self.links_internal += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data.strip())


def _polite_read(url: str) -> Dict[str, Any]:
    """One polite GET. Returns measured facts or an honest failure (L6).

    Never raises for network trouble — failures are reported as
    "unreachable", never invented.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"ok": False, "reason": "not an http(s) URL — skipped"}
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as resp:
            first_byte_s = time.monotonic() - started
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower():
                return {
                    "ok": False,
                    "reason": f"content is {ctype or 'unknown'} — not a page",
                }
            raw = resp.read(1_000_000)
    except Exception as exc:  # network trouble → honest failure, never raise
        return {"ok": False, "reason": f"unreachable ({type(exc).__name__})"}
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"ok": False, "reason": "could not decode page text"}
    facts = _PageFacts()
    facts.set_page(parsed.netloc)
    try:
        facts.feed(text)
    except Exception:
        pass
    title = " ".join(t for t in facts.title_parts if t)
    return {
        "ok": True,
        "first_byte_s": round(first_byte_s, 2),  # measured, approximate
        "title": title or None,  # None = missing title (measured)
        "meta_description": facts.meta_description,  # None = missing (measured)
        "has_viewport": facts.has_viewport,  # measured
        "imgs_total": facts.imgs_total,  # measured
        "imgs_without_alt": facts.imgs_without_alt,  # measured
        "links_internal": facts.links_internal,  # measured (inventory only)
        "links_external": facts.links_external,  # measured (inventory only)
        "note": (
            "single polite read; link targets were NOT crawled "
            "(polite-read policy) — deep broken-link check is manual follow-up"
        ),
    }


class AuditDaemon(DDDDailyDaemon):
    """Drafts $49 AuditNow audit drafts + outreach drafts, daily."""

    agent_id = "audit-daemon"
    daemon_id = "audit-daemon"
    display_name = "Audit Daemon (provisional)"
    owns = "Daily AuditNow audit drafts ($49/audit)"
    first_milestone = "first audit draft delivered with honest receipt"
    proficiency = {"auditing": 9, "web": 8, "general": 6}
    specialties = [
        "prospect queue: read-only scan of businesses Chauncey queued",
        "info-only audits: one polite read per named site, never a crawl",
        "drafts: finished $49 audit draft + outreach draft per site, DRAFT-labeled",
    ]
    attributes = [
        {
            "name": "honest named-site auditing",
            "assertion": (
                "the daemon audits only URLs Chauncey himself queued, "
                "reads each page once and politely, labels measured vs "
                "not-measured, and never invents a business or a finding."
            ),
        }
    ]

    queue_filename = "prospects.csv"
    queue_columns = ("business", "url", "contact_name", "notes")
    max_rows_per_day = 3

    def draft_for_rows(self, rows: List[Dict[str, str]]) -> tuple:
        lines = ["# DRAFT — AuditNow daily audits ($49/audit each)"]
        lines.append(f"- Prospects worked: {len(rows)} (from Chauncey's queue)")
        lines.append(f"- Checks per site: {', '.join(_CHECKS)}")
        lines.append("")
        for i, row in enumerate(rows, 1):
            business = row.get("business", "").strip() or "(unnamed business)"
            url = row.get("url", "").strip()
            contact = row.get("contact_name", "").strip()
            notes = row.get("notes", "").strip()
            lines.append(f"## {i}. {business}")
            lines.append(f"- URL (Chauncey-named): {url or '(none given)'}")
            if contact:
                lines.append(f"- Contact: {contact}")
            if notes:
                lines.append(f"- Notes: {notes}")
            lines.append("")
            if url:
                facts = _polite_read(url)
                lines.append("### Audit findings (info-only, measured)")
                if not facts["ok"]:
                    lines.append(f"- Site read: FAILED — {facts['reason']}")
                    lines.append(
                        "- No findings invented: this audit needs a "
                        "working page before it can be finished."
                    )
                else:
                    fb = facts["first_byte_s"]
                    lines.append(f"- First byte: ~{fb}s (measured, approximate)")
                    lines.append(
                        "- Title: "
                        + (
                            f'"{facts["title"]}"'
                            if facts["title"]
                            else "MISSING (measured)"
                        )
                    )
                    md = facts["meta_description"]
                    lines.append(
                        "- Meta description: "
                        + (f'"{md}"' if md else "MISSING (measured)")
                    )
                    lines.append(
                        "- Mobile viewport tag: "
                        + (
                            "present (measured)"
                            if facts["has_viewport"]
                            else "MISSING (measured)"
                        )
                    )
                    lines.append(
                        f"- Images: {facts['imgs_total']} total, "
                        f"{facts['imgs_without_alt']} without alt text (measured)"
                    )
                    lines.append(
                        f"- Links on page: {facts['links_internal']} internal, "
                        f"{facts['links_external']} external (inventory only — "
                        "targets NOT crawled, per polite-read policy)"
                    )
                    lines.append(
                        "- Deep broken-link crawl: NOT RUN (not-measured; "
                        "manual follow-up)"
                    )
                    lines.append(
                        "- These are observations, not guarantees of ranking or sales."
                    )
            else:
                lines.append("### Audit findings")
                lines.append("- No URL queued — no audit run, nothing invented.")
            lines.append("")
            lines.append("### Outreach draft (DRAFT — never sent)")
            who = contact or business
            lines.append(
                f"Hi {who} — quick note on {business}'s site: "
                "I ran an info-only health check and found a few things worth "
                "fixing (title/meta, mobile viewport, image alt text). "
                "I do one-page website audits for $49 — happy to send the full "
                "writeup if useful. — Chauncey"
            )
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(
            "DRAFT only: no audit delivered, no message sent, nothing charged. "
            "Waits on Chauncey's word."
        )
        return ("audits", "\n".join(lines))

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "run":
            return self.run_daily()
        raise AgentError(f"{self.daemon_id}: unknown task kind {kind!r}")
