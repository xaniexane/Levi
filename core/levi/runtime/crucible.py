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

    FORBIDDEN_SNIPPETS = ("__import__", "subprocess", "os.system", "eval(", "exec(", "open(", "socket")

    def syntax_probe(self, code: str) -> CrucibleResult:
        cid = str(uuid.uuid4())[:8]
        low = code.lower()
        for bad in self.FORBIDDEN_SNIPPETS:
            if bad.lower() in low:
                return CrucibleResult(id=cid, mode="syntax", ok=False, detail=f"Blocked pattern: {bad}")
        try:
            ast.parse(code)
            return CrucibleResult(id=cid, mode="syntax", ok=True, detail="AST parse OK")
        except SyntaxError as e:
            return CrucibleResult(id=cid, mode="syntax", ok=False, detail=f"SyntaxError: {e}")

    def file_smoke(self, rel_name: str, content: str) -> CrucibleResult:
        cid = str(uuid.uuid4())[:8]
        chamber = self._chamber()
        path = chamber / rel_name
        path.write_text(content, encoding="utf-8")
        if path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
                return CrucibleResult(id=cid, mode="file_smoke", ok=True, detail=f"compiled {path.name}", stdout=str(chamber))
            except Exception as e:
                return CrucibleResult(id=cid, mode="file_smoke", ok=False, detail=str(e), stdout=str(chamber))
        return CrucibleResult(id=cid, mode="file_smoke", ok=True, detail=f"wrote {path.name} (non-py)", stdout=str(chamber))

    def restricted_eval(self, expr: str) -> CrucibleResult:
        """Extremely limited: literals + arithmetic only via AST."""
        cid = str(uuid.uuid4())[:8]
        try:
            tree = ast.parse(expr, mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Call, ast.Attribute, ast.Name)):
                    if isinstance(node, ast.Name) and node.id in ("True", "False", "None"):
                        continue
                    if isinstance(node, ast.Name):
                        return CrucibleResult(id=cid, mode="restricted", ok=False, detail="Names not allowed")
                    if isinstance(node, (ast.Call, ast.Attribute)):
                        return CrucibleResult(id=cid, mode="restricted", ok=False, detail="Calls/attrs not allowed")
            val = ast.literal_eval(expr)
            return CrucibleResult(id=cid, mode="restricted", ok=True, detail="literal_eval OK", stdout=repr(val))
        except Exception as e:
            return CrucibleResult(id=cid, mode="restricted", ok=False, detail=str(e)[:200])

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
