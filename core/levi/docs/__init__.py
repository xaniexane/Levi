"""LEVI document skills: read and create common office document formats.

LEVI-native, stdlib-only implementations (``zipfile`` + ``xml.etree``
for OOXML; ``zlib`` for PDF content streams). No third-party
dependencies, no paid APIs, fully local.

Submodules
----------
``docx`` — read/create ``.docx`` (paragraphs, tables).
``xlsx`` — read/create ``.xlsx`` (headers + rows, shared strings).
``pptx`` — read/create ``.pptx`` (title + bullet slides).
``pdf``  — BEST-EFFORT text extraction only (see ``pdf`` docstring for
the honest limits: no layout, no scanned-image OCR, encrypted PDFs
refused).

Skill registration lives in :mod:`levi.docs.skills` (``DOC_SKILLS``,
consumed by :class:`levi.skill.registry.SkillRegistry`); CLI surface is
``levi doc`` in :mod:`levi.docs.cli`.
"""

from __future__ import annotations

__all__ = ["docx", "xlsx", "pptx", "pdf", "skills", "cli"]
