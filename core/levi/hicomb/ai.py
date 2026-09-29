"""Hicomb's AI pair programmer — Copilot qualities, offline-first honesty.

LAWS (declared up front, machine-checked in tests/test_hicomb_studio.py):
  I4 HONEST-SOURCE  Every Completion carries source in {"local", "model"}.
                    source="model" is emitted ONLY when a backend whose
                    available() returns True is wired. The local engine
                    NEVER claims to be a model — it labels itself "local".
  I5 LOCAL-ALWAYS   With no backend wired, suggest() still returns useful
                    local completions and status() reports "local-only".
                    Degradation is explicit, never faked.

Architecture: PairProgrammer(backend=None). The backend is a slot for a
real model (LEVI's own trained brain, llama-server, etc.) conforming to
the ModelBackend protocol. Until Chauncey seats one, the local engine —
word/fragment index, line-continuation memory, snippet triggers, and
deterministic code analysis — does the work and says so plainly.

Stdlib only. Deterministic. No network calls in any path here.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Protocol

SOURCES = ("local", "model")

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_DEF_RE = re.compile(r"^\s*(?:def|class|function|fn)\s+([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class Completion:
    text: str  # the completion text to insert after the caret
    source: str  # "local" | "model"  (I4)
    label: str = ""  # human-readable provenance, e.g. "local · word"
    confidence: float = 0.0


@dataclass(frozen=True)
class Analysis:
    engine: str  # always "local" until a model backend is seated
    kind: str  # "explain" | "review" | "fix" | "refactor"
    summary: str
    details: list[str] = field(default_factory=list)
    new_text: str | None = None  # for fix/refactor: proposed replacement


class ModelBackend(Protocol):
    """A real model plugged into the pair programmer."""

    def name(self) -> str: ...
    def available(self) -> bool: ...
    def complete(self, prefix: str, context: str, language: str) -> list[Completion]: ...
    def chat(self, prompt: str, context: str, language: str) -> str: ...


# ------------------------------------------------------------ local engine
class LocalEngine:
    """Deterministic completion + analysis. Labels everything 'local'."""

    def __init__(self, max_suggestions: int = 5) -> None:
        self.max_suggestions = max_suggestions

    # -- completions -----------------------------------------------------
    def complete(
        self, text: str, caret_line: int, caret_col: int, language: str
    ) -> list[Completion]:
        """Ghost-text candidates at the caret. Pure local signal."""
        lines = text.split("\n")
        if not (0 <= caret_line < len(lines)):
            return []
        line = lines[caret_line]
        prefix_m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", line[:caret_col])
        prefix = prefix_m.group(0) if prefix_m else ""
        out: list[Completion] = []
        seen: set[str] = set()

        def add(text_: str, label: str, conf: float) -> None:
            if text_ and text_ not in seen and len(out) < self.max_suggestions:
                seen.add(text_)
                out.append(
                    Completion(
                        text=text_, source="local", label=f"local · {label}",
                        confidence=conf,
                    )
                )

        # 1. word completions: distinct words from the buffer, longest first.
        if prefix:
            words = {w for w in _WORD_RE.findall(text) if w != prefix}
            for w in sorted(words, key=len, reverse=True):
                if w.startswith(prefix):
                    add(w[len(prefix):], "word", 0.6)
        # 2. line continuation: the last non-empty line above reappears
        #    elsewhere -> suggest the line that followed it there.
        stripped = line.strip()
        if stripped:
            for i in range(len(lines) - 1):
                if lines[i].strip() == stripped and i != caret_line:
                    nxt = lines[i + 1]
                    if nxt.strip():
                        add("\n" + nxt, "line-memory", 0.5)
                        break
        # 3. snippet triggers from the hicomb snippet registry.
        try:
            from levi.hicomb.snippets import expand, triggers

            for trig in triggers(language):
                if prefix and trig.startswith(prefix) and trig != prefix:
                    body = expand(language, trig)
                    if body:
                        add(body, f"snippet:{trig}", 0.7)
        except Exception:
            pass
        return out

    # -- analysis --------------------------------------------------------
    def explain(self, text: str, language: str) -> Analysis:
        """Structure summary of the file. Deterministic, labeled local."""
        lines = text.split("\n")
        defs = [m.group(1) for line in lines if (m := _DEF_RE.match(line))]
        todos = [line.strip() for line in lines
                 if "TODO" in line or "FIXME" in line][:8]
        summary = (
            f"{len(lines)} lines, {len(defs)} definitions "
            f"({', '.join(defs[:6])}{'…' if len(defs) > 6 else ''}), "
            f"{language}."
        )
        details = [f"defines: {', '.join(defs)}" if defs else "no definitions found"]
        if todos:
            details.append(f"open markers: {len(todos)}")
            details.extend(f"  • {t}" for t in todos)
        return Analysis(engine="local", kind="explain", summary=summary,
                        details=details)

    def review(self, text: str, language: str) -> Analysis:
        """Lint pass: problems list with line numbers. Labeled local."""
        problems: list[str] = []
        lines = text.split("\n")
        for i, line in enumerate(lines, 1):
            if line != line.rstrip():
                problems.append(f"L{i}: trailing whitespace")
            if "\t" in line:
                problems.append(f"L{i}: tab indentation")
            if len(line) > 100:
                problems.append(f"L{i}: long line ({len(line)} chars)")
            if "TODO" in line or "FIXME" in line:
                problems.append(f"L{i}: open marker: {line.strip()[:60]}")
        if language == "python":
            try:
                compile(text, "<review>", "exec")
            except SyntaxError as exc:
                problems.append(f"syntax error: line {exc.lineno}: {exc.msg}")
        if language == "json":
            import json as _json

            try:
                _json.loads(text)
            except _json.JSONDecodeError as exc:
                problems.append(f"json error: {exc}")
        summary = f"{len(problems)} problem(s) found" if problems else "clean"
        return Analysis(engine="local", kind="review", summary=summary,
                        details=problems[:40])

    def fix(self, text: str, language: str) -> Analysis:
        """Auto-fixable problems only. Returns proposed new_text + what changed."""
        from levi.hicomb.pollen import format_text

        applied: list[str] = []
        lines = text.split("\n")
        if any(ln != ln.rstrip() for ln in lines):
            applied.append("stripped trailing whitespace")
        if any("\t" in ln for ln in lines):
            applied.append("expanded tabs to 4 spaces")
        try:
            new_text = format_text(language, text)
        except Exception as exc:
            return Analysis(engine="local", kind="fix",
                            summary=f"cannot auto-fix: {exc}", details=[])
        if new_text != text:
            applied.append("ran pollen normalization")
        summary = f"applied {len(applied)} fix(es)" if applied else "nothing to fix"
        return Analysis(engine="local", kind="fix", summary=summary,
                        details=[f"  • {a}" for a in applied], new_text=new_text)

    def refactor(self, text: str, language: str) -> Analysis:
        """Refactor = pollen normalization + structural suggestions."""
        from levi.hicomb.pollen import format_text

        suggestions: list[str] = []
        try:
            new_text = format_text(language, text)
        except Exception as exc:
            return Analysis(engine="local", kind="refactor",
                            summary=f"refactor blocked: {exc}", details=[])
        if language == "python":
            try:
                tree = ast.parse(new_text)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if len(node.body) > 40:
                            suggestions.append(
                                f"consider splitting {node.name} "
                                f"({len(node.body)} statements)")
                        if not ast.get_docstring(node):
                            suggestions.append(
                                f"{node.name} has no docstring")
            except SyntaxError:
                pass
        if not suggestions:
            suggestions.append("no structural smells detected locally")
        summary = f"pollen-normalized, {len(suggestions)} suggestion(s)"
        return Analysis(engine="local", kind="refactor", summary=summary,
                        details=[f"  • {s}" for s in suggestions],
                        new_text=new_text if new_text != text else None)


# ------------------------------------------------------------ pair programmer
class PairProgrammer:
    """The Copilot-quality surface. backend=None -> honest local-only mode."""

    def __init__(self, backend: ModelBackend | None = None) -> None:
        self.backend = backend
        self.local = LocalEngine()

    def _backend_live(self) -> bool:
        """A broken backend never kills local completions (I5)."""
        try:
            return self.backend is not None and bool(self.backend.available())
        except Exception:
            return False

    def status(self) -> str:
        if self._backend_live():
            try:
                return f"model:{self.backend.name()}"
            except Exception:
                return "local-only"
        return "local-only"  # I5: degradation is explicit

    def suggest(
        self, text: str, caret_line: int, caret_col: int, language: str
    ) -> list[Completion]:
        """Local completions always; model completions only when wired (I4)."""
        out = self.local.complete(text, caret_line, caret_col, language)
        if self._backend_live():
            lines = text.split("\n")
            prefix = lines[caret_line][:caret_col] if 0 <= caret_line < len(lines) else ""
            try:
                model_out = self.backend.complete(prefix, text, language)
            except Exception:
                model_out = []
            for comp in model_out:
                if comp.source != "model":
                    continue  # I4: backend must not smuggle other sources
                out.append(comp)
        return out

    # -- chat actions: local analysis until a model is seated ---------------
    def explain(self, text: str, language: str) -> Analysis:
        return self.local.explain(text, language)

    def review(self, text: str, language: str) -> Analysis:
        return self.local.review(text, language)

    def fix(self, text: str, language: str) -> Analysis:
        return self.local.fix(text, language)

    def refactor(self, text: str, language: str) -> Analysis:
        return self.local.refactor(text, language)

    def ask(self, question: str, text: str, language: str) -> Analysis:
        """Free-form chat over the open file. Local heuristics, labeled."""
        q = question.lower()
        if any(w in q for w in ("explain", "what does", "summar")):
            return self.explain(text, language)
        if any(w in q for w in ("fix", "bug", "error", "broken")):
            rev = self.review(text, language)
            fx = self.fix(text, language)
            details = rev.details + ["---"] + fx.details
            return Analysis(engine="local", kind="fix",
                            summary=f"{rev.summary}; {fx.summary}",
                            details=details, new_text=fx.new_text)
        if any(w in q for w in ("refactor", "clean", "improve")):
            return self.refactor(text, language)
        if "todo" in q or "marker" in q:
            lines = text.split("\n")
            found = [f"L{i}: {line.strip()[:80]}"
                     for i, line in enumerate(lines, 1)
                     if "TODO" in line or "FIXME" in line]
            return Analysis(engine="local", kind="explain",
                            summary=f"{len(found)} open marker(s)",
                            details=found[:20])
        exp = self.explain(text, language)
        exp.details.insert(
            0, "local engine: I can explain, review, fix, or refactor "
               "this file. Ask with one of those words.")
        return exp
