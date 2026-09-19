"""OPML escape hatch: the whole subscription list as one portable plain file.

Studied from: fallen-platforms-hunt-20260916/report.md (item 1: shared shelf)

The mechanism: a subscription list is the reader's property. This module
models feeds as (title, xml_url, html_url, category) records and can
serialize the entire list to OPML — an XML document any other reader can
import — and parse an OPML document back into a list. The round-trip is
lossless for the four fields; OPML categories map to ``category``.
Categories nest flat: this model keeps one category level, which is what
the common readers produced.

Honest limits: stdlib XML only; outline attributes beyond the four core
fields are preserved in an ``attrs`` bag and written back verbatim, but
are not first-class citizens of the model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/opml-export"


@dataclass
class Subscription:
    title: str
    xml_url: str
    html_url: str = ""
    category: str = ""
    attrs: Dict[str, str] = field(default_factory=dict)


class SubscriptionList:
    """A portable list of feed subscriptions."""

    def __init__(self) -> None:
        self._feeds: List[Subscription] = []

    # ------------------------------------------------------------------
    # Building the list
    # ------------------------------------------------------------------
    def add(
        self,
        title: str,
        xml_url: str,
        html_url: str = "",
        category: str = "",
        **attrs: str,
    ) -> Subscription:
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        if not xml_url or not xml_url.strip():
            raise ValueError("xml_url must be non-empty")
        sub = Subscription(
            title=title,
            xml_url=xml_url,
            html_url=html_url,
            category=category,
            attrs=dict(attrs),
        )
        self._feeds.append(sub)
        return sub

    def remove(self, xml_url: str) -> bool:
        for i, sub in enumerate(self._feeds):
            if sub.xml_url == xml_url:
                del self._feeds[i]
                return True
        return False

    def in_category(self, category: str) -> List[Subscription]:
        return [s for s in self._feeds if s.category == category]

    # ------------------------------------------------------------------
    # The escape hatch: export and import
    # ------------------------------------------------------------------
    def to_opml(self, owner_name: str = "") -> str:
        """Serialize the whole list to an OPML 1.0 document."""
        opml = ET.Element("opml", version="1.0")
        head = ET.SubElement(opml, "head")
        title = ET.SubElement(head, "title")
        title.text = f"{owner_name} subscriptions" if owner_name else "subscriptions"
        body = ET.SubElement(opml, "body")

        by_category: Dict[str, List[Subscription]] = {}
        for sub in self._feeds:
            by_category.setdefault(sub.category, []).append(sub)

        for category in sorted(by_category):
            subs = by_category[category]
            parent: ET.Element = body
            if category:
                parent = ET.SubElement(body, "outline", text=category, title=category)
            for sub in subs:
                outline_attrs = {
                    "type": "rss",
                    "text": sub.title,
                    "title": sub.title,
                    "xmlUrl": sub.xml_url,
                    "htmlUrl": sub.html_url,
                }
                outline_attrs.update(sub.attrs)
                ET.SubElement(parent, "outline", **outline_attrs)

        xml_decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
        return xml_decl + ET.tostring(opml, encoding="unicode")

    @classmethod
    def from_opml(cls, document: str) -> "SubscriptionList":
        """Parse an OPML document back into a subscription list."""
        root = ET.fromstring(document)
        if root.tag != "opml":
            raise ValueError("not an OPML document")
        body = root.find("body")
        if body is None:
            raise ValueError("OPML document has no body")
        result = cls()
        for outline in body.iter("outline"):
            xml_url = outline.get("xmlUrl")
            if not xml_url:
                # Folder outlines carry no feed; skip.
                continue
            result.add(
                title=outline.get("text") or outline.get("title") or xml_url,
                xml_url=xml_url,
                html_url=outline.get("htmlUrl") or "",
                category=_parent_folder(body, outline) or "",
            )
        return result

    def __len__(self) -> int:
        return len(self._feeds)

    def feeds(self) -> List[Subscription]:
        return list(self._feeds)


def _parent_folder(body: ET.Element, node: ET.Element) -> Optional[str]:
    for parent in body.iter("outline"):
        if node in list(parent):
            return parent.get("text") or parent.get("title")
    return None
