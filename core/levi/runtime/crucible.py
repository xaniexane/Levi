"""
Crucible — LEVI-original constrained execution chamber.

Inspired by the *need* for safe trial runs; implementation is original:
  • syntax-only by default
  • optional restricted exec (no import, no open, no network names)
  • workspace isolation under ~/.levi/crucible/<id>
  • HITL recommended for anything beyond syntax

Not unrestricted shell. Not a copy of any commercial sandbox UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
import ast
import py_compile
import uuid


DEFAULT_ROOT = Path.home() / ".levi" / "crucible"

#: Upper bound on the content a single file_smoke probe may write.
_MAX_SMOKE_CONTENT = 10_000_000


@dataclass
class CrucibleResult:
    id: str
    mode: str
    ok: bool
    detail: str
    stdout: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Crucible:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _chamber(self) -> Path:
        p = self.root / str(uuid.uuid4())[:10]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _check_rel_name(rel_name: str) -> None:
        """Reject names that cannot live inside a chamber, before any
        chamber directory is created."""
        if not isinstance(rel_name, str) or not rel_name.strip():
            raise ValueError("file_smoke: 'rel_name' must be a non-empty string")
        candidate = Path(rel_name)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(
                "file_smoke: 'rel_name' must be a relative path inside the "
                f"chamber, got {rel_name!r}"
            )

    @staticmethod
    def _safe_rel_path(chamber: Path, rel_name: str) -> Path:
        """Resolve ``rel_name`` inside ``chamber`` or raise ValueError.

        The smoke test writes caller-controlled names to disk, so the
        name must be a relative path that stays inside the chamber:
        absolute paths, ``..`` segments, and names that resolve outside
        the chamber (e.g. via symlinks) are refused before any disk
        write happens.
        """
        Crucible._check_rel_name(rel_name)
        resolved = (chamber / rel_name).resolve()
        if resolved != chamber.resolve() and chamber.resolve() not in resolved.parents:
            raise ValueError(
                "file_smoke: 'rel_name' escapes the chamber, "
                f"got {rel_name!r}"
            )
        return resolved

    FORBIDDEN_SNIPPETS = (
        "__import__",
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "open(",
        "socket",
    )

    def syntax_probe(self, code: str) -> CrucibleResult:
        cid = str(uuid.uuid4())[:8]
        if not isinstance(code, str):
            return CrucibleResult(
                id=cid,
                mode="syntax",
                ok=False,
                detail="syntax_probe: 'code' must be a string",
            )
        if len(code) > _MAX_SMOKE_CONTENT:
            return CrucibleResult(
                id=cid,
                mode="syntax",
                ok=False,
                detail=(
                    "syntax_probe: 'code' exceeds the "
                    f"{_MAX_SMOKE_CONTENT} character probe limit"
                ),
            )
        low = code.lower()
        for bad in self.FORBIDDEN_SNIPPETS:
            if bad.lower() in low:
                return CrucibleResult(
                    id=cid, mode="syntax", ok=False, detail=f"Blocked pattern: {bad}"
                )
        try:
            ast.parse(code)
            return CrucibleResult(id=cid, mode="syntax", ok=True, detail="AST parse OK")
        except SyntaxError as e:
            return CrucibleResult(
                id=cid, mode="syntax", ok=False, detail=f"SyntaxError: {e}"
            )

    def file_smoke(self, rel_name: str, content: str) -> CrucibleResult:
        cid = str(uuid.uuid4())[:8]
        if not isinstance(content, str):
            return CrucibleResult(
                id=cid,
                mode="file_smoke",
                ok=False,
                detail="file_smoke: 'content' must be a string",
            )
        if len(content) > _MAX_SMOKE_CONTENT:
            return CrucibleResult(
                id=cid,
                mode="file_smoke",
                ok=False,
                detail=(
                    "file_smoke: 'content' exceeds the "
                    f"{_MAX_SMOKE_CONTENT} character smoke-test limit"
                ),
            )
        try:
            self._check_rel_name(rel_name)
        except ValueError as exc:
            return CrucibleResult(
                id=cid, mode="file_smoke", ok=False, detail=str(exc)
            )
        chamber = self._chamber()
        try:
            path = self._safe_rel_path(chamber, rel_name)
            path.parent.mkdir(parents=True, exist_ok=True)
        except ValueError as exc:
            return CrucibleResult(
                id=cid, mode="file_smoke", ok=False, detail=str(exc)
            )
        path.write_text(content, encoding="utf-8")
        if path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
                return CrucibleResult(
                    id=cid,
                    mode="file_smoke",
                    ok=True,
                    detail=f"compiled {path.name}",
                    stdout=str(chamber),
                )
            except Exception as e:
                return CrucibleResult(
                    id=cid,
                    mode="file_smoke",
                    ok=False,
                    detail=str(e),
                    stdout=str(chamber),
                )
        return CrucibleResult(
            id=cid,
            mode="file_smoke",
            ok=True,
            detail=f"wrote {path.name} (non-py)",
            stdout=str(chamber),
        )

    def restricted_eval(self, expr: str) -> CrucibleResult:
        """Extremely limited: literals + arithmetic only via AST."""
        cid = str(uuid.uuid4())[:8]
        try:
            tree = ast.parse(expr, mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Call, ast.Attribute, ast.Name)):
                    if isinstance(node, ast.Name) and node.id in (
                        "True",
                        "False",
                        "None",
                    ):
                        continue
                    if isinstance(node, ast.Name):
                        return CrucibleResult(
                            id=cid,
                            mode="restricted",
                            ok=False,
                            detail="Names not allowed",
                        )
                    if isinstance(node, (ast.Call, ast.Attribute)):
                        return CrucibleResult(
                            id=cid,
                            mode="restricted",
                            ok=False,
                            detail="Calls/attrs not allowed",
                        )
            val = ast.literal_eval(expr)
            return CrucibleResult(
                id=cid,
                mode="restricted",
                ok=True,
                detail="literal_eval OK",
                stdout=repr(val),
            )
        except Exception as e:
            return CrucibleResult(
                id=cid, mode="restricted", ok=False, detail=str(e)[:200]
            )

    def format_result(self, r: CrucibleResult) -> str:
        flag = "PASS" if r.ok else "FAIL"
        lines = [
            f"=== Crucible [{flag}] ===",
            f"id={r.id}  mode={r.mode}",
            r.detail,
        ]
        if r.stdout:
            lines.append(r.stdout[:500])
        lines.append("LEVI Crucible: syntax/file/literal only — no free shell.")
        return "\n".join(lines)
