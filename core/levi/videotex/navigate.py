"""The videotex navigator: a small state machine over the page tree.

History is a stack of page ids. Every input line parses to exactly one
:class:`~levi.videotex.keys.KeyAction`, and every action resolves to a
page id — navigation only, never execution. ``run_script()`` replays a
list of inputs non-interactively so whole sessions are testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import CHOICES_PER_SCREEN
from .keys import parse
from .pages import Page, build_tree, render


@dataclass
class Navigator:
    pages: dict[str, Page]
    history: list[str] = field(default_factory=list)
    current: str = "home"

    @classmethod
    def build(cls, root: Path | None = None) -> "Navigator":
        return cls(pages=build_tree(root))

    # -- internals --------------------------------------------------------
    def _page(self) -> Page:
        return self.pages[self.current]

    def _visible(self) -> list:
        page = self._page()
        total = len(page.choices)
        pages = max(1, (total + CHOICES_PER_SCREEN - 1) // CHOICES_PER_SCREEN)
        chunk = min(page.chunk, pages - 1)
        start = chunk * CHOICES_PER_SCREEN
        return page.choices[start : start + CHOICES_PER_SCREEN]

    def _goto(self, pid: str) -> str:
        if pid not in self.pages:
            return "page inconnue."
        if pid != self.current:
            self.history.append(self.current)
        self.current = pid
        self.pages[pid].chunk = 0
        return ""

    def _back(self) -> str:
        if not self.history:
            return "deja a l'accueil."
        self.current = self.history.pop()
        return ""

    # -- public -------------------------------------------------------------
    def handle(self, line: str) -> tuple[str, bool]:
        """Handle one input line. Returns (output_text, quit_flag)."""
        action = parse(line)
        page = self._page()

        if action.kind == "choice":
            visible = self._visible()
            idx = action.number - 1
            if 0 <= idx < len(visible):
                note = self._goto(visible[idx].target)
                return self._render(note), False
            return self._render(
                "choix %d inconnu (1-%d)." % (action.number, len(visible))
            ), False
        if action.kind == "retour":
            if not self.history:
                return self._render(""), True  # * at root: hang up, Minitel-style
            note = self._back()
            return self._render(note), False
        if action.kind == "sommaire":
            self.history.clear()
            self.current = "home"
            self.pages["home"].chunk = 0
            return self._render(""), False
        if action.kind == "suite":
            total = len(page.choices)
            pages = max(1, (total + CHOICES_PER_SCREEN - 1) // CHOICES_PER_SCREEN)
            if page.chunk < pages - 1:
                page.chunk += 1
                return self._render(""), False
            return self._render("pas d'autre page."), False
        if action.kind == "guide":
            note = self._goto("guide")
            return self._render(note), False
        if action.kind == "repetition" or action.kind == "correction":
            return self._render(""), False
        if action.kind == "envoi":
            return self._render("rien a confirmer."), False
        if action.kind == "annulation":
            if not self.history:
                return "Au revoir.\n", True
            note = self._back()
            return self._render(note), False
        return self._render("touche inconnue — 'guide' pour l'aide."), False

    def _render(self, note: str = "") -> str:
        page = self._page()
        trail = [self.pages[pid].title for pid in self.history[-2:]] + [page.title]
        text = render(page, trail)
        if note:
            text += "\n! " + note
        return text

    def run_script(self, inputs: list[str]) -> list[str]:
        """Replay inputs non-interactively; returns outputs per input."""
        outputs = [self._render("")]
        for line in inputs:
            text, quit_flag = self.handle(line)
            outputs.append(text)
            if quit_flag:
                break
        return outputs
