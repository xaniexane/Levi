"""Plain-text mbox archive: one file per folder. The archive is truth.

Messages are appended to per-folder mbox files. The search index is
*derived* from the archive: deleting the index and rebuilding from
the mbox yields identical search results (T4).
"""

from __future__ import annotations

import mailbox
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["Archive"]


class Archive:
    """Append-only per-folder mbox archive with a rebuildable index."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home else Path.home() / ".levi" / "sovmail"
        self.home.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, Dict[str, List[str]]] = {}  # folder -> term -> ids

    def _mbox_path(self, folder: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in folder)
        return self.home / f"{safe or 'inbox'}.mbx"

    def append(
        self, folder: str, message: Dict[str, Any], raw: Optional[bytes] = None
    ) -> str:
        """Append a normalized message record to the folder's mbox."""
        msg = EmailMessage()
        msg["From"] = str(message.get("from", ""))
        msg["To"] = (
            ", ".join(message.get("to", []))
            if isinstance(message.get("to"), list)
            else str(message.get("to", ""))
        )
        msg["Subject"] = str(message.get("subject", ""))
        if message.get("id"):
            msg["Message-ID"] = str(message["id"])
        msg.set_content(str(message.get("body", "")))
        box = mailbox.mbox(str(self._mbox_path(folder)), create=True)
        try:
            key = box.add(msg)
        finally:
            box.close()
        self._index.pop(folder, None)  # invalidate derived index
        return str(key)

    def _iter_records(self, folder: str):

        box = mailbox.mbox(str(self._mbox_path(folder)), create=False)
        try:
            for key in box.iterkeys():
                try:
                    msg = box[key]
                except (KeyError, ValueError):
                    continue
                yield key, msg
        finally:
            box.close()

    @staticmethod
    def _terms(text: str) -> List[str]:
        import re

        return sorted(set(re.findall(r"[a-z0-9]{2,}", text.lower())))

    def build_index(self, folder: str) -> Dict[str, List[str]]:
        """Derive the search index from the mbox. Rebuildable from scratch."""
        index: Dict[str, List[str]] = {}
        for key, msg in self._iter_records(folder):
            mid = str(msg.get("Message-ID") or key)
            text = " ".join(
                [
                    str(msg.get("Subject", "")),
                    str(msg.get("From", "")),
                    msg.get_payload() if isinstance(msg.get_payload(), str) else "",
                ]
            )
            for term in self._terms(text):
                index.setdefault(term, []).append(mid)
        for term in index:
            index[term] = sorted(set(index[term]))
        self._index[folder] = index
        return index

    def delete_index(self, folder: str) -> None:
        """Drop the derived index; the archive stays untouched."""
        self._index.pop(folder, None)

    def index_for(self, folder: str) -> Dict[str, List[str]]:
        if folder not in self._index:
            self.build_index(folder)
        return self._index[folder]

    def count(self, folder: str) -> int:
        return sum(1 for _ in self._iter_records(folder))
