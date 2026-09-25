"""Hicomb Android bridge.

JSON in/out wrappers over the on-device engines:
  - hicomb   : the editor engine (buffer/tabs/highlight/search/snippets/themes)
  - quetta_pan : the improver — FRONT AND CENTER in the Hicomb UI
  - surgeon  : the repair agent (syntax check + elite multi-pass repair)
  - builder  : Alpha — scaffold new projects from the loop bar

Every function returns a JSON string (or plain string for text). The Java
side never touches Python objects directly.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

_WORKSPACE: Path | None = None
_QP_ENGINE = None
_QP_TARGET_PROJECT = False

EDITABLE_EXTS = {
    ".py", ".txt", ".md", ".json", ".html", ".css", ".js", ".ts",
    ".xml", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh", ".java",
}


def _ws() -> Path:
    if _WORKSPACE is None:
        raise RuntimeError("workspace not set")
    return _WORKSPACE


def set_workspace(path: str) -> str:
    global _WORKSPACE, _QP_ENGINE
    _WORKSPACE = Path(path)
    _WORKSPACE.mkdir(parents=True, exist_ok=True)
    _QP_ENGINE = None  # rebind the engine to the new workspace
    return "true"


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def seed_workspace() -> str:
    """Seed a starter project on first launch."""
    try:
        ws = _ws()
        main = ws / "main.py"
        if not main.exists():
            main.write_text(
                '''"""Hicomb on Android — your code lives here."""\n\n\ndef greet(name):\n    return f"hello {name}, welcome to hicomb"\n\n\nif __name__ == "__main__":\n    print(greet("chauncey"))\n''',
                encoding="utf-8",
            )
        notes = ws / "notes.md"
        if not notes.exists():
            notes.write_text(
                "# Hicomb notes\n\n- Tap **Quetta-Pan** to improve this file.\n"
                "- Tap **Surgeon** to repair syntax.\n"
                "- Tap **Alpha** to scaffold a new project.\n",
                encoding="utf-8",
            )
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_files() -> str:
    try:
        ws = _ws()
        out = []
        for p in sorted(ws.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ws).as_posix()
            if rel.startswith(".") or ".elite.bak" in rel:
                continue
            if p.suffix.lower() in EDITABLE_EXTS or p.suffix == "":
                out.append(rel)
        return json.dumps(out[:500])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def read_file(rel: str) -> str:
    try:
        from levi.hicomb.buffer import Buffer
        from levi.hicomb.highlight import detect_language

        buf = Buffer.open(str(_ws() / rel))
        text = "\n".join(buf.lines())
        return json.dumps(
            {"ok": True, "text": text, "language": detect_language(rel)}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def write_file(rel: str, text: str) -> str:
    try:
        p = _ws() / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def highlight_spans(rel: str, text: str) -> str:
    """Flattened absolute-offset token spans: [[start, end, kind], ...]."""
    try:
        from levi.hicomb.highlight import detect_language, highlight

        language = detect_language(rel)
        lines = text.split("\n")
        spans = []
        offset = 0
        for i, line_toks in enumerate(highlight(lines, language)):
            for tok in line_toks:
                if tok.kind != "plain":
                    spans.append([offset + tok.start, offset + tok.end, tok.kind])
            offset += len(lines[i]) + 1
        return json.dumps(spans)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def search_in_file(rel: str, query: str) -> str:
    try:
        from levi.hicomb.search import find_all

        text = (_ws() / rel).read_text(encoding="utf-8", errors="replace")
        hits = find_all(text.split("\n"), query)
        return json.dumps([[h.line, h.start] for h in hits][:200])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def theme_list() -> str:
    try:
        from levi.hicomb.themes import list_themes

        return json.dumps(list_themes())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def theme_get(name: str) -> str:
    try:
        from levi.hicomb.themes import get_theme

        t = get_theme(name)
        return json.dumps({"ui": dict(t.ui), "syntax": dict(t.syntax)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------------------------
# The operating laws — taught to the app, not just documented.
# law->guard->prove · originals-first · honesty over polish ·
# nothing-thrown-away · one organism (all of Legion is Levi).
# ---------------------------------------------------------------------------

def laws() -> str:
    return json.dumps(
        [
            {
                "name": "law-guard-prove",
                "text": "Every change declares its law, passes a guard, and carries "
                "proof. Dry-run never writes; apply = backup, write, "
                "guard-evaluate; iterate stops when stable.",
            },
            {
                "name": "originals-first",
                "text": "Originals are never overwritten. Alpha refuses to clobber "
                "an existing build — iterate on the original with Quetta-Pan.",
            },
            {
                "name": "honesty-over-polish",
                "text": "Applied vs guard-held is always reported, with the reason. "
                "Limits are stated, not hidden.",
            },
            {
                "name": "nothing-thrown-away",
                "text": "Every apply leaves a timestamped backup. Every repair "
                "leaves a .elite.bak. Nothing is deleted — this editor has "
                "no delete action at all.",
            },
            {
                "name": "one-organism",
                "text": "All of Legion is Levi, one organism. Hicomb is a limb of "
                "the same body.",
            },
        ]
    )


def qp_history(rel: str) -> str:
    """Backups Quetta-Pan kept for a file — nothing thrown away, all visible."""
    try:
        eng = _engine()
        bdir = eng.backup_dir
        name = Path(rel).name
        items = (
            sorted(p.name for p in bdir.glob(f"{name}_*.bak"))
            if bdir.exists()
            else []
        )
        return json.dumps({"ok": True, "backups": items[-20:]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------------------------
# Quetta-Pan — front and center
# ---------------------------------------------------------------------------

def qp_set_target(is_project: bool) -> str:
    global _QP_TARGET_PROJECT
    _QP_TARGET_PROJECT = bool(is_project)
    return "true"


def _engine():
    global _QP_ENGINE
    if _QP_ENGINE is None:
        from levi.quetta_pan.engine import QuettaPanEngine

        ws = _ws()
        _QP_ENGINE = QuettaPanEngine(
            project_root=str(ws), store_dir=str(ws / ".qp")
        )
    return _QP_ENGINE


def _qp_files() -> list[Path]:
    ws = _ws()
    if _QP_TARGET_PROJECT:
        return [
            p for p in sorted(ws.rglob("*.py"))
            if ".qp" not in p.parts and ".elite.bak" not in p.name
        ][:50]
    return []


def qp_scan() -> str:
    """Dry-run: list improvements per file. No writes."""
    try:
        eng = _engine()
        results = []
        files = _qp_files()
        for f in files:
            try:
                sug = eng.suggest_upgrades(f)
                upgrades = sug.get("upgrades", [])
                if upgrades:
                    results.append(
                        {
                            "file": f.relative_to(_ws()).as_posix(),
                            "upgrades": upgrades,
                            "count": len(upgrades),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "file": f.relative_to(_ws()).as_posix(),
                        "upgrades": [f"(scan error: {exc})"],
                        "count": 0,
                    }
                )
        return json.dumps({"ok": True, "results": results})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def qp_suggest(rel: str) -> str:
    """Dry-run for one file: full suggestion detail."""
    try:
        eng = _engine()
        sug = eng.suggest_upgrades(_ws() / rel)
        safe = {
            "file": str(sug.get("file", rel)),
            "upgrades": list(sug.get("upgrades", [])),
            "suggestions": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "desc": s.get("desc"),
                    "severity": s.get("severity"),
                }
                for s in sug.get("suggestions", [])
            ],
            "diff": str(sug.get("diff", ""))[:8000],
            "suppressed_by_genome": [
                {"id": s.get("id"), "reason": s.get("suppressed_reason", "")}
                for s in sug.get("suppressed_by_genome", [])
            ],
        }
        return json.dumps({"ok": True, "suggestion": safe})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def qp_apply(rel: str) -> str:
    """Apply Quetta-Pan's safe fixes to one file (backup -> write -> guard)."""
    try:
        eng = _engine()
        sug = eng.suggest_upgrades(_ws() / rel)
        if not sug.get("suggestions"):
            return json.dumps({"ok": True, "applied": False, "detail": "no suggestions"})
        res = eng.apply_suggestion(sug)
        return json.dumps(
            {
                "ok": bool(res.ok),
                "applied": bool(res.ok),
                "detail": "" if res.ok else str(res.failure_reason),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def qp_apply_all() -> str:
    try:
        eng = _engine()
        applied, failed, details = 0, 0, []
        for f in _qp_files():
            try:
                sug = eng.suggest_upgrades(f)
                if not sug.get("suggestions"):
                    continue
                res = eng.apply_suggestion(sug)
                if res.ok:
                    applied += 1
                else:
                    failed += 1
                    details.append(f"{f.name}: {res.failure_reason}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                details.append(f"{f.name}: {exc}")
        return json.dumps(
            {"ok": True, "applied": applied, "failed": failed, "details": details[:20]}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def qp_iterate(rounds: int) -> str:
    """Run the improve loop N rounds; stops early when nothing changes."""
    try:
        rounds = max(1, min(int(rounds), 10))
        eng = _engine()
        log: list[str] = []
        applied_total = 0
        passes = 0
        for i in range(rounds):
            passes = i + 1
            changed = 0
            for f in _qp_files():
                try:
                    sug = eng.suggest_upgrades(f)
                    if not sug.get("suggestions"):
                        continue
                    res = eng.apply_suggestion(sug)
                    name = f.relative_to(_ws()).as_posix()
                    if res.ok:
                        changed += 1
                        applied_total += 1
                        log.append(f"pass {passes}: {name} improved")
                    else:
                        log.append(f"pass {passes}: {name} guard-held ({res.failure_reason})")
                except Exception as exc:  # noqa: BLE001
                    log.append(f"pass {passes}: {f.name} error {exc}")
            if changed == 0:
                log.append(f"pass {passes}: no changes — stable")
                break
        return json.dumps(
            {"ok": True, "passes": passes, "applied": applied_total, "log": log[-40:]}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------------------------
# Surgeon — the repair agent
# ---------------------------------------------------------------------------

def surgeon_check_text(text: str) -> str:
    try:
        from levi.surgeon.elite import syntax_error

        err = syntax_error(text, "<editor>")
        return json.dumps({"ok": True, "error": err})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def surgeon_repair(rel: str) -> str:
    """Multi-pass repair of a file. Snapshot-first, always revertible."""
    try:
        from levi.surgeon.elite import elite_repair

        res = elite_repair(_ws() / rel)
        return json.dumps(
            {
                "ok": True,
                "passes": res.passes,
                "fixes": list(res.fixes),
                "clean": bool(res.clean),
                "backup": res.backup,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------------------------
# Alpha (Builder) — scaffold new projects from the loop bar
# ---------------------------------------------------------------------------

def alpha_plan(description: str, stack: str, name: str) -> str:
    try:
        from levi.builder.pipeline import plan_preview

        stack = stack if stack in ("static", "fullstack") else "static"
        return plan_preview(description, stack, name or "untitled")
    except Exception:  # noqa: BLE001
        return traceback.format_exc()[-2000:]


def alpha_build(description: str, stack: str, name: str) -> str:
    """Deterministic offline scaffold: heuristic spec -> file tree."""
    try:
        from levi.builder.scaffolds.spec import heuristic_spec

        stack = stack if stack in ("static", "fullstack") else "static"
        name = (name or "untitled").strip() or "untitled"
        spec = heuristic_spec(description, stack, name)
        if stack == "fullstack":
            from levi.builder.scaffolds.fullstack import render_fullstack as render
        else:
            from levi.builder.scaffolds.static import render_static as render
        files = render(spec)
        dest = _ws() / "builds" / name
        # ORIGINALS-FIRST: an existing original is never overwritten. The user
        # iterates on it with Quetta-Pan instead — the build is refused loudly.
        if dest.exists() and any(dest.iterdir()):
            return json.dumps(
                {
                    "ok": False,
                    "error": "original exists",
                    "detail": (
                        f"{dest.relative_to(_ws()).as_posix()} is an original — "
                        "originals are never overwritten. Open Quetta-Pan and "
                        "iterate on it instead."
                    ),
                    "dest": dest.relative_to(_ws()).as_posix(),
                }
            )
        written = []
        for rel_path, content in files.items():
            p = dest / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(rel_path)
        return json.dumps(
            {"ok": True, "dest": dest.relative_to(_ws()).as_posix(), "files": sorted(written)}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)
