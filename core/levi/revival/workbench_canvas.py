"""Local workbench canvas — chat kept apart from versioned work products.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 15].

The mechanism under study: a canvas that splits conversation (chat) from
work product (artifacts). Artifacts are versioned documents with notes
per revision, diffable and exportable to plain text, Markdown, or HTML —
all local, all explicit. This is an original, from-scratch implementation
for LEVI. Chat is an append-only log; artifacts never mingle with it.

Public surface:
- ``Canvas``: new_artifact / revise / get / history / diff / export /
  delete; chat(name, text, role) for the conversation side;
  export_session() to bundle chat + artifacts into one Markdown doc.

stdlib-only. No network. Timestamps are caller-supplied floats.
"""

from __future__ import annotations

import difflib
import html
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/workbench-canvas"


class CanvasError(ValueError):
    """Raised when a canvas operation is invalid."""


@dataclass
class Revision:
    number: int
    text: str
    note: str
    created_at: float


@dataclass
class Artifact:
    name: str
    kind: str = "note"
    revisions: List[Revision] = field(default_factory=list)

    def latest(self) -> Revision:
        return self.revisions[-1]


@dataclass
class ChatMessage:
    role: str
    text: str
    created_at: float


class Canvas:
    """A local workbench: versioned artifacts beside an append-only chat."""

    def __init__(self, title: str = "workbench") -> None:
        self.title = title
        self._artifacts: Dict[str, Artifact] = {}
        self._chat: List[ChatMessage] = []

    # ---- chat side -------------------------------------------------
    def chat(
        self, text: str, role: str = "user", created_at: float = 0.0
    ) -> ChatMessage:
        if not text.strip():
            raise CanvasError("chat text must not be empty")
        msg = ChatMessage(role, text, created_at)
        self._chat.append(msg)
        return msg

    def transcript(self) -> List[ChatMessage]:
        return list(self._chat)

    # ---- artifact side ---------------------------------------------
    def new_artifact(
        self,
        name: str,
        text: str,
        kind: str = "note",
        note: str = "created",
        created_at: float = 0.0,
    ) -> Artifact:
        if not name:
            raise CanvasError("artifact name must not be empty")
        if name in self._artifacts:
            raise CanvasError(f"artifact {name!r} already exists")
        artifact = Artifact(name, kind)
        artifact.revisions.append(Revision(1, text, note, created_at))
        self._artifacts[name] = artifact
        return artifact

    def revise(
        self, name: str, text: str, note: str = "", created_at: float = 0.0
    ) -> Revision:
        artifact = self._require(name)
        rev = Revision(len(artifact.revisions) + 1, text, note, created_at)
        artifact.revisions.append(rev)
        return rev

    def get(self, name: str, revision: Optional[int] = None) -> str:
        artifact = self._require(name)
        if revision is None:
            return artifact.latest().text
        for rev in artifact.revisions:
            if rev.number == revision:
                return rev.text
        raise CanvasError(f"artifact {name!r} has no revision {revision}")

    def history(self, name: str) -> List[Revision]:
        return list(self._require(name).revisions)

    def diff(self, name: str, old: int, new: int) -> str:
        a = self.get(name, old).splitlines(keepends=True)
        b = self.get(name, new).splitlines(keepends=True)
        lines = difflib.unified_diff(
            a, b, fromfile=f"{name}@r{old}", tofile=f"{name}@r{new}"
        )
        return "".join(lines)

    def delete(self, name: str) -> bool:
        return self._artifacts.pop(name, None) is not None

    def list_artifacts(self) -> List[str]:
        return sorted(self._artifacts)

    def _require(self, name: str) -> Artifact:
        try:
            return self._artifacts[name]
        except KeyError:
            raise CanvasError(f"no artifact named {name!r}") from None

    # ---- export ----------------------------------------------------
    def export(self, name: str, fmt: str = "markdown") -> str:
        artifact = self._require(name)
        text = artifact.latest().text
        if fmt == "text":
            return text
        if fmt == "markdown":
            return f"# {artifact.name}\n\n{text}\n"
        if fmt == "html":
            body = html.escape(text).replace("\n", "<br/>\n")
            return (
                f"<!doctype html>\n<html><head><meta charset='utf-8'>"
                f"<title>{html.escape(artifact.name)}</title></head>"
                f"<body><h1>{html.escape(artifact.name)}</h1>"
                f"<p>{body}</p></body></html>"
            )
        raise CanvasError(f"unknown export format {fmt!r}")

    def export_session(self) -> str:
        """Bundle chat + all artifacts into one Markdown document."""
        parts = [f"# {self.title}\n"]
        parts.append("## Chat\n")
        for msg in self._chat:
            parts.append(f"**{msg.role}:** {msg.text}\n")
        parts.append("\n## Artifacts\n")
        for name in self.list_artifacts():
            parts.append(self.export(name, "markdown"))
        return "\n".join(parts)
