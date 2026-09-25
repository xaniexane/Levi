"""LEVI's phish flagging: client-side suspicious-link inspection.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(Scam-link flagging, client-side.)

The studied shape looked at links *before* you clicked them and said
"this smells wrong" — on your own machine, with plain rules. This
module rebuilds that as LEVI's own link inspector. It extracts URLs
from a message (href targets and bare links), runs a set of stated
heuristics over each one, and reports flags with reasons.

What this is NOT: a verdict. Every flag is a heuristic — a pattern
that *correlates* with phishing, stated as such in the flag's reason.
The module never declares a message safe (absence of flags is not
proof of honesty) and never blocks anything; it annotates, and you or
your filters decide. Rule names and reasons are part of the public
contract so the heuristics stay auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List
from urllib.parse import urlparse


ORIGIN = "levi-revival/phish-flagging"

_HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_BARE_URL = re.compile(r"(?i)\bhttps?://[^\s<>'\"]+")
_DISPLAY_LINK = re.compile(
    r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# TLDs that phishing campaigns historically abuse; a heuristic list,
# not a blocklist. Kept small and reviewable on purpose.
_SUSPICIOUS_TLDS = {
    "zip",
    "mov",
    "top",
    "xyz",
    "click",
    "link",
    "country",
    "stream",
    "download",
    "review",
    "accountant",
    "faith",
    "date",
}

# Words commonly borrowed by deceptive domains to sound legitimate.
_TRUST_WORDS = {
    "secure",
    "login",
    "verify",
    "account",
    "bank",
    "update",
    "support",
    "billing",
    "confirm",
    "signin",
    "security",
    "wallet",
}


@dataclass
class LinkFlag:
    """One heuristic hit on one link: rule name, human reason, link."""

    rule: str
    reason: str
    link: str

    def as_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "reason": self.reason, "link": self.link}


@dataclass
class LinkReport:
    """Everything the inspector found in one message's links."""

    links: List[str] = field(default_factory=list)
    flags: List[LinkFlag] = field(default_factory=list)

    @property
    def suspicious(self) -> bool:
        return bool(self.flags)

    def flags_for(self, link: str) -> List[LinkFlag]:
        return [f for f in self.flags if f.link == link]


class PhishInspector:
    """Inspects links in message text with stated heuristics.

    ``inspect(html_or_text)`` returns a LinkReport. Use
    ``flag_message(subject, body)`` for the common case of checking a
    whole message.
    """

    def inspect(self, text: str) -> LinkReport:
        report = LinkReport()
        seen: List[str] = []

        # links with display text: check display vs target mismatch
        for href, display in _DISPLAY_LINK.findall(text):
            if href not in seen:
                seen.append(href)
                report.links.append(href)
            display_url = display.strip()
            if _BARE_URL.search(display_url):
                disp_host = self._host(display_url)
                href_host = self._host(href)
                if disp_host and href_host and disp_host != href_host:
                    report.flags.append(
                        LinkFlag(
                            rule="display_mismatch",
                            reason=(
                                "heuristic: the visible link text shows a "
                                f"different host ({disp_host}) than the real "
                                f"target ({href_host})"
                            ),
                            link=href,
                        )
                    )

        # every link, bare or href'd
        for link in _HREF.findall(text) + _BARE_URL.findall(text):
            if link not in seen:
                seen.append(link)
                report.links.append(link)
            report.flags.extend(self._check_link(link))
        return report

    def flag_message(self, subject: str, body: str) -> LinkReport:
        """Inspect a whole message. Subject lines rarely hold links,
        but phishers put them everywhere, so check both."""
        subject_report = self.inspect(subject)
        body_report = self.inspect(body)
        merged = LinkReport()
        for report in (subject_report, body_report):
            for link in report.links:
                if link not in merged.links:
                    merged.links.append(link)
            merged.flags.extend(report.flags)
        return merged

    # -- the heuristics ---------------------------------------------------

    def _check_link(self, link: str) -> List[LinkFlag]:
        flags: List[LinkFlag] = []
        host = self._host(link)
        if not host:
            return flags

        if "xn--" in host:
            flags.append(
                LinkFlag(
                    rule="punycode",
                    reason="heuristic: internationalized (punycode) host can "
                    "visually impersonate a familiar domain",
                    link=link,
                )
            )
        if _IP_HOST.match(host):
            flags.append(
                LinkFlag(
                    rule="ip_host",
                    reason="heuristic: link points at a bare IP address "
                    "instead of a named host",
                    link=link,
                )
            )
        tld = host.rsplit(".", 1)[-1].lower() if "." in host else ""
        if tld in _SUSPICIOUS_TLDS:
            flags.append(
                LinkFlag(
                    rule="suspicious_tld",
                    reason=f"heuristic: .{tld} is disproportionately used "
                    "in phishing campaigns",
                    link=link,
                )
            )
        if "@" in link.split("://", 1)[-1].split("/", 1)[0]:
            flags.append(
                LinkFlag(
                    rule="at_sign",
                    reason="heuristic: '@' in the authority section can hide "
                    "the real host",
                    link=link,
                )
            )
        if "%" in link and len(re.findall(r"%[0-9a-fA-F]{2}", link)) >= 3:
            flags.append(
                LinkFlag(
                    rule="heavy_encoding",
                    reason="heuristic: heavily percent-encoded URL may be "
                    "hiding its true destination",
                    link=link,
                )
            )
        parts = host.lower().split(".")
        if len(parts) > 2:
            sub = ".".join(parts[:-2])
            if any(w in sub for w in _TRUST_WORDS):
                flags.append(
                    LinkFlag(
                        rule="deceptive_subdomain",
                        reason="heuristic: trust-evoking words in a subdomain "
                        "of an unrelated root domain",
                        link=link,
                    )
                )
        return flags

    @staticmethod
    def _host(link: str) -> str:
        try:
            parsed = urlparse(link if "://" in link else "http://" + link)
            return parsed.hostname or ""
        except Exception:
            return ""
