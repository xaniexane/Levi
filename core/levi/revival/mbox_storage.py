"""LEVI's mbox archive: mail stored as plain text, not a database.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(Plain-text modified-mbox storage.)

The studied shape refused the proprietary database: your archive was
yours — a folder of plain-text files you could back up, grep, and
carry away. This module rebuilds that as LEVI's own mbox archive. One
file per mailbox, messages appended in mbox framing (a ``From `` line
per message, ``>``-escaped body lines), headers and bodies readable by
any text tool on earth.

What this is NOT: a database. There are no indexes, no locking, no
transactions. Reads scan the file; writes append. For a personal
archive that is the honest trade — portability over speed — and the
search module exists to make the scan fast enough.
"""

from __future__ import annotations

import time
from email import message_from_string
from email.message import Message as EmailMessage
from email.utils import formatdate
from typing import Dict, Iterator, List, Optional


ORIGIN = "levi-revival/mbox-storage"


class MboxError(Exception):
    """Base error for mbox archive failures."""


class MboxArchive:
    """One plain-text mailbox file: append, read, count, compact.

    The file format is mbox: each message starts with a ``From `` line
    (sender address plus date), followed by RFC-style headers, a blank
    line, then the body. Body lines that begin with ``From `` are
    escaped as ``>From `` so the framing never lies.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    # -- writing --------------------------------------------------------

    def append(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
        now: Optional[int] = None,
    ) -> int:
        """Append one message. Returns the byte offset where it starts.

        Offsets are cheap bookmarks into a plain-text file — useful for
        the search module, invalid the moment the file is compacted.
        """
        now = int(time.time()) if now is None else now
        lines = [f"From {sender} {formatdate(now, usegmt=True)}"]
        full_headers = {
            "From": sender,
            "To": ", ".join(recipients),
            "Subject": subject,
            "Date": formatdate(now, usegmt=True),
        }
        full_headers.update(headers or {})
        for key, value in full_headers.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        for body_line in body.splitlines():
            if body_line.startswith("From "):
                body_line = ">" + body_line
            lines.append(body_line)
        lines.append("")
        text = "\n".join(lines) + "\n"
        with open(self.path, "a", encoding="utf-8") as fh:
            offset = fh.tell()
            fh.write(text)
        return offset

    # -- reading --------------------------------------------------------

    def _iter_raw(self) -> Iterator[str]:
        """Yield raw text chunks, one per message."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                content = fh.read()
        except FileNotFoundError:
            return
        chunk: List[str] = []
        for line in content.splitlines(keepends=True):
            if line.startswith("From ") and chunk:
                yield "".join(chunk)
                chunk = [line]
            else:
                chunk.append(line)
        if chunk:
            yield "".join(chunk)

    def _parse(self, chunk: str) -> EmailMessage:
        text = chunk
        if text.startswith("From "):
            text = text.split("\n", 1)[1] if "\n" in text else ""
        unescaped = "\n".join(
            line[1:] if line.startswith(">From ") else line for line in text.split("\n")
        )
        return message_from_string(unescaped)

    def read_all(self) -> List[EmailMessage]:
        """Parse and return every message, oldest first."""
        return [self._parse(chunk) for chunk in self._iter_raw()]

    def count(self) -> int:
        """Number of messages, without parsing any of them."""
        return sum(1 for _ in self._iter_raw())

    def get(self, index: int) -> EmailMessage:
        """The message at ``index`` (0-based, oldest first)."""
        for i, chunk in enumerate(self._iter_raw()):
            if i == index:
                return self._parse(chunk)
        raise IndexError(f"no message at index {index}")

    # -- maintenance ----------------------------------------------------

    def compact(self) -> int:
        """Rewrite the file, dropping any zero-length message chunks.

        Returns the number of messages kept. Offsets recorded by
        :meth:`append` are invalid after this call.
        """
        messages = [c for c in self._iter_raw() if c.strip()]
        with open(self.path, "w", encoding="utf-8") as fh:
            for chunk in messages:
                fh.write(chunk if chunk.endswith("\n") else chunk + "\n")
        return len(messages)
