"""LEVI's self-instrumentation: DWIM correction + Masterscope cross-reference
analysis over LEVI's own modules.

Inspired by Interlisp-D (Xerox PARC, 1970s–1980s; D-machines; the Medley
restoration is active today). The ahead-of-its-time mechanisms: DWIM
(do-what-I-mean) spelling correction, structure editing, automatic change
logging, and *Masterscope* — a queryable cross-reference database of the
whole program ("who calls what, where is this used"). It died with the
Lisp-machine market collapse (Symbolics/TI/Xerox) — a commercial decline,
not a technical failure.

Remix delta: Interlisp's DWIM/Masterscope reimagined as LEVI analyzing
*itself* — not a Lisp environment clone. Masterscope indexes LEVI's own
modules with stdlib ``ast`` so the assistant can answer "what depends on
this fact/tool?" before acting (impact analysis is a first-class query);
DWIM corrects mistyped commands against LEVI's own symbol tables and
always *reports* the correction — never applied silently. No structure
editor, no image-based world; the load-bearing mechanism is the
queryable cross-reference database, turned inward.

This is an original, from-scratch reimplementation for LEVI — no
Interlisp code is used. Two parts:

(a) DWIM: typo-tolerant correction of names and command tokens against a
    known vocabulary (Levenshtein distance with a threshold). Ambiguous
    user commands are corrected against the symbol table instead of
    failing — but a correction is always *reported* as a correction, never
    applied silently; nothing within the distance threshold returns None
    rather than a wild guess.

(b) Masterscope: a cross-reference database over LEVI's *own* modules,
    built with stdlib ``ast``. For each module it records definitions
    (functions, classes), imports (who imports what), and per-function
    name references (an approximate call graph). Queries: "who calls
    this?", "who imports this module?", "what does this function touch?"
    — the instrument for answering "what depends on this fact/tool?"
    before acting (e.g. before "delete the meeting notes", resolve which
    notes via reference analysis and show impact first).

Honesty: LOAD-BEARING — with stated static-analysis limits: dynamic
calls (getattr, eval, plugin registries) are invisible; references are
name-based, not type-resolved; nested scopes are flattened to
``module.function``. An approximation, documented as one.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# (a) DWIM — do-what-I-mean correction
# ---------------------------------------------------------------------------


def levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings (classic DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[len(b)]


def dwim(
    name: str,
    candidates: list[str],
    max_distance: int = 2,
    case_insensitive: bool = True,
) -> Optional[str]:
    """Correct ``name`` to the closest candidate within ``max_distance``.

    Returns the best candidate, or None if nothing is close enough —
    DWIM suggests, it never hallucinates. Ties prefer the
    lexicographically smallest candidate (deterministic).
    """
    if not name or not candidates:
        return None
    key = name.lower() if case_insensitive else name
    best: Optional[str] = None
    best_dist = max_distance + 1
    for cand in candidates:
        ckey = cand.lower() if case_insensitive else cand
        d = levenshtein(key, ckey)
        if d < best_dist or (d == best_dist and best is not None and cand < best):
            best, best_dist = cand, d
    return best if best_dist <= max_distance else None


def correct_tokens(
    text: str, vocabulary: list[str], max_distance: int = 2
) -> tuple[str, list[tuple[str, str]]]:
    """Typo-tolerant token correction over whitespace-separated tokens.

    Returns ``(corrected_text, corrections)`` where corrections lists
    ``(original, corrected)`` — the caller must show these to the user;
    correction is never silent.
    """
    vocab = list(vocabulary)
    out_tokens: list[str] = []
    corrections: list[tuple[str, str]] = []
    for token in text.split():
        if token in vocab:
            out_tokens.append(token)
            continue
        fix = dwim(token, vocab, max_distance=max_distance)
        if fix is not None:
            out_tokens.append(fix)
            corrections.append((token, fix))
        else:
            out_tokens.append(token)
    return " ".join(out_tokens), corrections


# ---------------------------------------------------------------------------
# (b) Masterscope — cross-reference database over LEVI's own modules
# ---------------------------------------------------------------------------


@dataclass
class ModuleInfo:
    """What Masterscope knows about one module."""

    name: str  # dotted name relative to the indexed root
    path: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # imported module names
    references: dict[str, list[str]] = field(default_factory=dict)  # func -> names used


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: list[str] = []
        self.classes: list[str] = []
        self.imports: list[str] = []
        self.references: dict[str, set[str]] = {}
        self._current: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        prev = self._current
        self._current = node.name
        self.references.setdefault(node.name, set())
        self.generic_visit(node)
        self._current = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and self._current is not None:
            self.references.setdefault(self._current, set()).add(node.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name: Optional[str] = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name is not None and self._current is not None:
            self.references.setdefault(self._current, set()).add(name)
        self.generic_visit(node)


class Masterscope:
    """Queryable cross-reference database over a tree of Python modules."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.modules: dict[str, ModuleInfo] = {}
        self._failed: list[str] = []

    def index_file(self, path: str | Path) -> ModuleInfo:
        """Parse one file; syntax errors are recorded in ``failed`` and the
        file is skipped — the database never half-ingests a module."""
        p = Path(path)
        try:
            rel = p.relative_to(self.root)
        except ValueError:
            rel = p
        dotted = ".".join(rel.with_suffix("").parts)
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except (OSError, SyntaxError, UnicodeDecodeError):
            self._failed.append(str(p))
            info = ModuleInfo(name=dotted, path=str(p))
            self.modules[dotted] = info
            return info
        visitor = _Visitor()
        visitor.visit(tree)
        info = ModuleInfo(
            name=dotted,
            path=str(p),
            functions=sorted(set(visitor.functions)),
            classes=sorted(set(visitor.classes)),
            imports=sorted(set(visitor.imports)),
            references={f: sorted(names) for f, names in visitor.references.items()},
        )
        self.modules[dotted] = info
        return info

    def index_tree(self, pattern: str = "*.py") -> int:
        """Index every matching file under root (skips __pycache__)."""
        count = 0
        for p in sorted(self.root.rglob(pattern)):
            if "__pycache__" in p.parts:
                continue
            self.index_file(p)
            count += 1
        return count

    @property
    def failed(self) -> list[str]:
        return list(self._failed)

    # -- queries ------------------------------------------------------------------
    def definitions(self, module: str) -> dict:
        """Functions and classes defined in ``module``."""
        info = self._require(module)
        return {"functions": list(info.functions), "classes": list(info.classes)}

    def imports_of(self, module: str) -> list[str]:
        return list(self._require(module).imports)

    def imported_by(self, module: str) -> list[str]:
        """Modules whose import list mentions ``module`` (substring match on
        the dotted name — honest about the approximation)."""
        return sorted(
            m
            for m, info in self.modules.items()
            if any(module in imp or imp in module for imp in info.imports)
        )

    def references(self, name: str) -> list[str]:
        """``module.function`` entries whose body references ``name``."""
        out = []
        for mod, info in self.modules.items():
            for func, names in info.references.items():
                if name in names:
                    out.append(f"{mod}.{func}")
        return sorted(out)

    def what_uses(self, module: str, name: str) -> dict:
        """Impact analysis for ``module.name``: definitions, importers, and
        every function that references it — the "show impact before acting"
        instrument."""
        return {
            "defined_in": module,
            "imported_by": self.imported_by(module),
            "referenced_by": self.references(name),
        }

    def _require(self, module: str) -> ModuleInfo:
        try:
            return self.modules[module]
        except KeyError:
            raise KeyError(f"masterscope: module {module!r} is not indexed") from None


def default_root() -> Path:
    """The LEVI package directory — Masterscope analyzing LEVI itself."""
    import levi

    return Path(levi.__file__).resolve().parent


__all__ = [
    "levenshtein",
    "dwim",
    "correct_tokens",
    "ModuleInfo",
    "Masterscope",
    "default_root",
]
