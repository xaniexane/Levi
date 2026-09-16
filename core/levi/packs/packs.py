"""Scoped knowledge packs — user-owned persistent context.

A pack is a folder:

    <pack-name>/
        manifest.json        # name, version, description, scope rules
        instructions.md      # standing instructions (any *.md counts)
        content/             # reference material (md/txt/json)

:func:`PackStore` loads packs from ``~/.levi/packs`` (call-time home
resolution, as everywhere). :func:`assemble` builds the scoped context
block for a given project/cwd: only packs whose scope rules match are
included, in explicit priority order, with provenance headers so the
model always knows which pack said what.

Scoping rules (all declared in manifest.json, user-editable):

- ``"always"`` — attach to every session.
- ``"projects": ["slug", ...]`` — attach when the project slug matches.
- ``"paths": ["glob", ...]`` — attach when the cwd matches a glob.
- ``"tags": [...]`` — matched explicitly via ``assemble(tags=[...])``.

Precedence: tags > projects > paths > always. Within a pack, sections
order: manifest metadata, instructions (alphabetical), content
(alphabetical). A byte budget truncates *content first, instructions
never silently* — truncation is reported in the assembly header.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"
MANIFEST = "manifest.json"
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
MAX_FILENAME = 100


def packs_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "packs"


class PackError(Exception):
    pass


def _safe_name(name: str) -> str:
    if not name or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,%d}" % MAX_FILENAME, name
    ):
        raise PackError("bad pack name %r: use letters, digits, . _ -" % name)
    if ".." in name or name.startswith((".", "-")):
        raise PackError("bad pack name %r" % name)
    return name


def default_manifest(name: str) -> Dict[str, Any]:
    return {
        "format": "levi_pack_v1",
        "name": name,
        "version": "0.1.0",
        "description": "",
        "scope": {"always": False, "projects": [], "paths": [], "tags": []},
        "priority": 100,
    }


def validate_manifest(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise PackError("manifest.json must be an object")
    for key in ("format", "name"):
        if key not in data:
            raise PackError("manifest.json missing %r" % key)
    if data["format"] != "levi_pack_v1":
        raise PackError("unsupported pack format: %r" % data.get("format"))
    scope = data.get("scope", {})
    if not isinstance(scope, dict):
        raise PackError("manifest scope must be an object")
    for key in ("projects", "paths", "tags"):
        vals = scope.get(key, [])
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            raise PackError("scope.%s must be a list of strings" % key)
    return data


class Pack:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.name
        mp = path / MANIFEST
        if not mp.exists():
            raise PackError("pack %r has no %s" % (self.name, MANIFEST))
        try:
            data = json.loads(mp.read_text(encoding=ENC))
        except (json.JSONDecodeError, OSError) as exc:
            raise PackError("pack %r manifest unreadable: %s" % (self.name, exc))
        self.manifest = validate_manifest(data)

    @property
    def scope(self) -> Dict[str, Any]:
        s = {"always": False, "projects": [], "paths": [], "tags": []}
        s.update(self.manifest.get("scope", {}))
        return s

    @property
    def priority(self) -> int:
        return int(self.manifest.get("priority", 100))

    def scope_match(
        self, project: Optional[str], cwd: Optional[str], tags: List[str]
    ) -> Optional[str]:
        """Return the matching rule name, or None."""
        s = self.scope
        if tags and set(tags) & set(s["tags"]):
            return "tags"
        if project and project in s["projects"]:
            return "projects"
        if cwd:
            for pat in s["paths"]:
                if fnmatch.fnmatch(cwd, pat):
                    return "paths"
        if s["always"]:
            return "always"
        return None

    def _read_texts(self, files: List[Path]) -> List[tuple]:
        out = []
        for f in sorted(files):
            try:
                out.append((f.name, f.read_text(encoding=ENC)))
            except OSError:
                continue
        return out

    def instructions(self) -> List[tuple]:
        files = [
            p
            for p in self.path.glob("*.md")
            if p.name != MANIFEST and p.suffix.lower() in TEXT_SUFFIXES
        ]
        files += [p for p in self.path.glob("instructions/*.md")]
        return self._read_texts(files)

    def content_files(self) -> List[tuple]:
        cdir = self.path / "content"
        if not cdir.is_dir():
            return []
        files = [
            p
            for p in cdir.rglob("*")
            if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES | {".json"}
        ]
        return self._read_texts(files)


class PackStore:
    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.root = packs_home(home)
        self.root.mkdir(parents=True, exist_ok=True)

    def init(
        self, name: str, description: str = "", scope: Optional[Dict[str, Any]] = None
    ) -> Path:
        _safe_name(name)
        d = self.root / name
        if d.exists():
            raise PackError("pack already exists: %s" % name)
        (d / "content").mkdir(parents=True)
        m = default_manifest(name)
        m["description"] = description
        if scope:
            m["scope"].update(scope)
        (d / MANIFEST).write_text(json.dumps(m, indent=2), encoding=ENC)
        (d / "instructions.md").write_text(
            "# Instructions for %s\n\nStanding instructions go here.\n" % name,
            encoding=ENC,
        )
        return d

    def list_packs(self) -> List[Pack]:
        packs = []
        for p in sorted(self.root.iterdir()):
            if p.is_dir() and (p / MANIFEST).exists():
                try:
                    packs.append(Pack(p))
                except PackError:
                    continue  # broken packs are skipped, not fatal
        return packs

    def get(self, name: str) -> Pack:
        _safe_name(name)
        p = self.root / name
        if not p.is_dir():
            raise PackError("no such pack: %s" % name)
        return Pack(p)

    def delete(self, name: str) -> None:
        pack = self.get(name)
        import shutil

        shutil.rmtree(pack.path)

    def assemble(
        self,
        project: Optional[str] = None,
        cwd: Optional[str] = None,
        tags: Optional[List[str]] = None,
        budget_chars: int = 60000,
    ) -> Dict[str, Any]:
        """Build the scoped context block. Returns {packs, text, truncated}."""
        tags = tags or []
        matched = []
        for pack in self.list_packs():
            rule = pack.scope_match(project, cwd, tags)
            if rule:
                matched.append((pack.priority, rule, pack))
        matched.sort(key=lambda t: (t[0], t[2].name))
        sections = []
        used = []
        truncated: List[str] = []
        for _, rule, pack in matched:
            used.append(
                {
                    "name": pack.name,
                    "rule": rule,
                    "version": pack.manifest.get("version"),
                }
            )
            parts = ["# pack: %s (matched by: %s)" % (pack.name, rule)]
            desc = pack.manifest.get("description")
            if desc:
                parts.append("_%s_" % desc)
            for fname, text in pack.instructions():
                parts.append("## instructions/%s\n%s" % (fname, text))
            content_budget = budget_chars - sum(len(x) for x in parts)
            for fname, text in pack.content_files():
                if len(text) > content_budget and content_budget > 0:
                    text = text[:content_budget] + "\n…[truncated: budget]"
                    truncated.append("%s/%s" % (pack.name, fname))
                elif len(text) > content_budget:
                    truncated.append("%s/%s (skipped: budget)" % (pack.name, fname))
                    continue
                parts.append("## content/%s\n%s" % (fname, text))
                content_budget -= len(text)
            sections.append("\n\n".join(parts))
        header = "[scoped context: %d pack(s) attached%s]" % (
            len(used),
            "; truncated: %s" % ", ".join(truncated) if truncated else "",
        )
        text = header + "\n\n" + "\n\n---\n\n".join(sections) if sections else header
        return {"packs": used, "text": text, "truncated": truncated}
