"""INCOME BATCH C — audit-services (slots 41-52).

Twelve original, from-scratch, stdlib-only audit generators. Each audits a
user-supplied local path (params["target"]) and writes a real findings
report under <levi_home>/.levi/income/work/<id>/. Defensive/blue-team
only: scanners REPORT, never exploit, never exfiltrate, never touch the
network.

Generator roster:
  41 seo-basics-scanner        — SEO fundamentals of local HTML files
  42 accessibility-spotter     — common a11y issues in local HTML
  43 broken-link-hunter        — broken INTERNAL links across local HTML
  44 readme-health-auditor     — README completeness score for a project dir
  45 dependency-hygiene-reporter — pinned vs floating deps in requirement files
  46 backup-readiness-auditor  — backup gaps in a directory tree
  47 secrets-surface-reporter  — DEFENSIVE scan for exposed secret patterns
  48 doc-coverage-reporter     — undocumented public Python functions/classes
  49 todo-debt-collector       — TODO/FIXME/HACK/XXX debt harvest
  50 git-hygiene-reporter      — branch/commit hygiene from git history
  51 license-header-auditor    — license-header inventory across a project
  52 perf-checklist-generator  — static performance checklist for a static site
"""

from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
import subprocess
import textwrap
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.income.engine import Generator, WorkReport, register

_KIND = "audit-service"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _target(ctx: Dict[str, Any]) -> Optional[Path]:
    raw = (ctx.get("params") or {}).get("target")
    if not raw:
        return None
    p = Path(str(raw)).expanduser()
    return p


def _work_dir(ctx: Dict[str, Any], gid: str) -> Path:
    return Path(ctx["levi_home"]) / ".levi" / "income" / "work" / gid


def _iter_files(root: Path, exts: Tuple[str, ...], max_bytes: int = 2_000_000):
    """Yield readable text-ish files under root matching exts."""
    if root.is_file():
        if root.suffix.lower() in exts and root.stat().st_size <= max_bytes:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in exts:
                try:
                    if p.stat().st_size <= max_bytes:
                        yield p
                except OSError:
                    continue


def _write_artifacts(ctx, gid: str, stamp: str, title: str,
                     md_body: str, summary: Dict[str, Any]) -> List[str]:
    """Write report.md + summary.json. Returns produced (relative) paths."""
    wdir = _work_dir(ctx, gid)
    wdir.mkdir(parents=True, exist_ok=True)
    base = f"{stamp}-{gid}"
    md_path = wdir / f"{base}-report.md"
    json_path = wdir / f"{base}-summary.json"
    md_path.write_text(
        f"# {title}\n\n_Generated {_utc_stamp()} by `{gid}` "
        f"(income batch C, audit-service)._\n\n{md_body}\n",
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return [f"{gid}/{md_path.name}", f"{gid}/{json_path.name}"]


def _missing_target_report(ctx, gid: str, price: float, what: str) -> WorkReport:
    return WorkReport(
        generator_id=gid,
        produced=[],
        quoted_amount_usd=price,
        notes=(f"{what}: no target supplied. Re-run with "
               "params['target'] pointing at the local path to audit."),
    )


# ---------------------------------------------------------------------------
# Shared HTML parse helper (original, html.parser-based)
# ---------------------------------------------------------------------------
class _Tag(HTMLParser):
    """Collects (tag, attrs, line) for every start tag in an HTML file."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: List[Tuple[str, Dict[str, str], int]] = []
        self.text_chunks: List[Tuple[str, int]] = []
        # open-element stack: [tag, line, [text pieces]]; completed ones
        # land in elem_text[(tag, line)]
        self._stack: List[list] = []
        self.elem_text: Dict[Tuple[str, int], str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        self.tags.append((tag, dict(attrs), self.getpos()[0]))
        self._stack.append([tag, self.getpos()[0], []])

    def handle_startendtag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        line = self.getpos()[0]
        self.tags.append((tag, dict(attrs), line))
        self.elem_text[(tag, line)] = ""

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                t, ln, pieces = self._stack.pop(i)
                self.elem_text[(t, ln)] = "".join(pieces).strip()
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_chunks.append((data.strip(), self.getpos()[0]))
            if self._stack:
                self._stack[-1][2].append(data)

    def close(self) -> None:  # flush unclosed elements at EOF
        while self._stack:
            t, ln, pieces = self._stack.pop()
            self.elem_text.setdefault((t, ln), "".join(pieces).strip())
        super().close()


def _parse_html(path: Path) -> Optional[_Tag]:
    try:
        parser = _Tag()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        parser.close()
        return parser
    except OSError:
        return None


def _rel(base: Path, p: Path) -> str:
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# 41 — seo-basics-scanner
# ---------------------------------------------------------------------------
_GID_SEO = "seo-basics-scanner"


def _run_seo(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_SEO, price, "SEO basics scan")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_SEO, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    files = list(_iter_files(target, (".html", ".htm")))
    dry = bool(ctx.get("dry_run"))
    lines: List[str] = []
    findings = 0
    scores: List[int] = []
    for f in files:
        tree = _parse_html(f)
        if tree is None:
            continue
        score, notes = _seo_check_file(tree)
        scores.append(score)
        if notes:
            findings += len(notes)
            lines.append(f"## `{_rel(target, f)}` — score {score}/100")
            lines.extend(f"- {n}" for n in notes)
            lines.append("")
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    body = (
        f"Scanned **{len(files)}** HTML file(s). "
        f"Average SEO score: **{avg}/100**. Findings: **{findings}**.\n\n"
        + ("\n".join(lines) if lines else "No issues found — all checks passed.")
    )
    summary = {"files_scanned": len(files), "avg_score": avg,
               "findings": findings, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_SEO}/{stamp}-{_GID_SEO}-report.md",
                 f"{_GID_SEO}/{stamp}-{_GID_SEO}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_SEO, stamp,
                                            "SEO Basics Scan", body, summary))
    return WorkReport(
        generator_id=_GID_SEO, produced=produced,
        quoted_amount_usd=price,
        notes=f"SEO scan of {len(files)} file(s): avg {avg}/100, "
              f"{findings} finding(s).{' (dry run)' if dry else ''}")


def _seo_check_file(tree: _Tag) -> Tuple[int, List[str]]:
    notes: List[str] = []
    score = 100
    by_tag: Dict[str, List[Tuple[Dict[str, str], int]]] = {}
    for tag, attrs, line in tree.tags:
        by_tag.setdefault(tag, []).append((attrs, line))

    titles = by_tag.get("title", [])
    if not titles:
        notes.append("missing <title> element"); score -= 25
    metas = by_tag.get("meta", [])
    has_desc = any(
        (a.get("name", "").lower() == "description" and a.get("content", "").strip())
        for a, _ in metas)
    if not has_desc:
        notes.append("missing meta description"); score -= 20
    has_viewport = any(a.get("name", "").lower() == "viewport"
                       for a, _ in metas)
    if not has_viewport:
        notes.append("missing viewport meta (mobile)"); score -= 10

    h1s = by_tag.get("h1", [])
    if len(h1s) == 0:
        notes.append("no <h1> found"); score -= 15
    elif len(h1s) > 1:
        notes.append(f"{len(h1s)} <h1> elements (ideally one)"); score -= 10

    # heading order
    last_level = 0
    for tag, attrs, line in tree.tags:
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lvl = int(tag[1])
            if last_level and lvl > last_level + 1:
                notes.append(f"heading level skip at line {line} "
                             f"(h{last_level} -> h{lvl})"); score -= 5
                break
            last_level = lvl

    imgs = by_tag.get("img", [])
    no_alt = [ln for a, ln in imgs if not a.get("alt", "").strip()]
    if no_alt:
        notes.append(f"{len(no_alt)} <img> without alt text "
                     f"(lines {no_alt[:5]})"); score -= 10
    if not by_tag.get("html", []):
        notes.append("missing <html> root element"); score -= 5
    return max(score, 0), notes


# ---------------------------------------------------------------------------
# 42 — accessibility-spotter
# ---------------------------------------------------------------------------
_GID_A11Y = "accessibility-spotter"


def _run_a11y(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_A11Y, price, "Accessibility spot-check")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_A11Y, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    files = list(_iter_files(target, (".html", ".htm")))
    dry = bool(ctx.get("dry_run"))
    lines: List[str] = []
    findings = 0
    for f in files:
        tree = _parse_html(f)
        if tree is None:
            continue
        notes = _a11y_check_file(tree)
        if notes:
            findings += len(notes)
            lines.append(f"## `{_rel(target, f)}`")
            lines.extend(f"- {n}" for n in notes)
            lines.append("")
    body = (f"Spot-checked **{len(files)}** HTML file(s). "
            f"Flagged **{findings}** potential accessibility issue(s).\n\n"
            "_Heuristic, static-only: a real assistive-technology test "
            "still needs a human._\n\n"
            + ("\n".join(lines) if lines else "No issues flagged."))
    summary = {"files_scanned": len(files), "findings": findings,
               "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_A11Y}/{stamp}-{_GID_A11Y}-report.md",
                 f"{_GID_A11Y}/{stamp}-{_GID_A11Y}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_A11Y, stamp,
                                            "Accessibility Spot-Check",
                                            body, summary))
    return WorkReport(
        generator_id=_GID_A11Y, produced=produced,
        quoted_amount_usd=price,
        notes=f"a11y spot-check of {len(files)} file(s): "
              f"{findings} flagged.{' (dry run)' if dry else ''}")


def _a11y_check_file(tree: _Tag) -> List[str]:
    notes: List[str] = []
    for tag, attrs, line in tree.tags:
        if tag == "img" and not attrs.get("alt", "").strip():
            role = attrs.get("role", "")
            if role != "presentation":
                notes.append(f"line {line}: <img> missing alt text")
        if tag == "input":
            itype = attrs.get("type", "text").lower()
            if itype in ("hidden", "submit", "button", "image"):
                continue
            if not attrs.get("id") and not attrs.get("aria-label") \
                    and not attrs.get("aria-labelledby"):
                notes.append(f"line {line}: <input type={itype}> has no "
                             "id/aria-label (unlabelled)")
        if tag == "button":
            pass
    # empty buttons / links: no text content of their own and no aria-label
    flagged_empty = 0
    for tag, attrs, line in tree.tags:
        if tag in ("button", "a") and not attrs.get("aria-label", "").strip():
            if not tree.elem_text.get((tag, line), ""):
                notes.append(f"line {line}: <{tag}> has no visible text "
                             "or aria-label")
                flagged_empty += 1
                if flagged_empty > 8:
                    break
    # heading skips
    last = 0
    for tag, attrs, line in tree.tags:
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lvl = int(tag[1])
            if last and lvl > last + 1:
                notes.append(f"line {line}: heading skips h{last} -> h{lvl}")
                break
            last = lvl
    html_tags = [a for t, a, _ in tree.tags if t == "html"]
    if html_tags and not html_tags[0].get("lang", "").strip():
        notes.append("<html> missing lang attribute")
    return notes


# ---------------------------------------------------------------------------
# 43 — broken-link-hunter
# ---------------------------------------------------------------------------
_GID_LINKS = "broken-link-hunter"


def _run_links(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.5
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_LINKS, price, "Broken internal link hunt")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_LINKS, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    base = target if target.is_dir() else target.parent
    files = list(_iter_files(base, (".html", ".htm")))
    dry = bool(ctx.get("dry_run"))
    broken: List[Tuple[str, int, str]] = []  # (file, line, href)
    checked = 0
    id_cache: Dict[Path, set] = {}
    for f in files:
        tree = _parse_html(f)
        if tree is None:
            continue
        for tag, attrs, line in tree.tags:
            url = attrs.get("href") if tag == "a" else attrs.get("src")
            if tag not in ("a", "img", "script", "link") or not url:
                continue
            url = url.strip()
            if not url or url.startswith(
                    ("http://", "https://", "mailto:", "tel:", "data:",
                     "javascript:")):
                continue
            checked += 1
            path_part, _, frag = url.partition("#")
            if not path_part:  # pure fragment -> check id in same file
                if frag and frag not in _ids_of(tree):
                    broken.append((_rel(base, f), line, url))
                continue
            resolved = (f.parent / path_part).resolve()
            try:
                resolved.relative_to(base.resolve())
            except ValueError:
                continue  # points outside the scanned tree; out of scope
            if not resolved.exists():
                broken.append((_rel(base, f), line, url))
            elif frag:
                ids = id_cache.get(resolved)
                if ids is None:
                    t2 = _parse_html(resolved) if resolved.suffix.lower() \
                        in (".html", ".htm") else None
                    ids = _ids_of(t2) if t2 else set()
                    id_cache[resolved] = ids
                if ids and frag not in ids:
                    broken.append((_rel(base, f), line, url))
    lines = [f"- `{fn}` line {ln}: `{u}`" for fn, ln, u in broken]
    body = (f"Checked **{checked}** internal link(s) across "
            f"**{len(files)}** HTML file(s). Broken: **{len(broken)}**.\n\n"
            + ("\n".join(lines) if lines else "No broken internal links found."))
    summary = {"files_scanned": len(files), "links_checked": checked,
               "broken": len(broken), "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_LINKS}/{stamp}-{_GID_LINKS}-report.md",
                 f"{_GID_LINKS}/{stamp}-{_GID_LINKS}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_LINKS, stamp,
                                            "Broken Internal Link Hunt",
                                            body, summary))
    return WorkReport(
        generator_id=_GID_LINKS, produced=produced,
        quoted_amount_usd=price,
        notes=f"{checked} internal link(s) checked, {len(broken)} broken."
              f"{' (dry run)' if dry else ''}")


def _ids_of(tree: Optional[_Tag]) -> set:
    if tree is None:
        return set()
    return {a.get("id", "") for _, a, _ in tree.tags if a.get("id")}


# ---------------------------------------------------------------------------
# 44 — readme-health-auditor
# ---------------------------------------------------------------------------
_GID_README = "readme-health-auditor"

_README_SECTIONS = [
    ("title", re.compile(r"^#\s+\S+", re.M), 15, "top-level # title"),
    ("description", re.compile(r"(?i)\b(description|overview|about)\b"), 10,
     "description/overview section"),
    ("install", re.compile(r"(?im)^#{1,3}\s*(install|getting started|setup)\b"),
     15, "installation section"),
    ("usage", re.compile(r"(?im)^#{1,3}\s*(usage|quick ?start|examples?)\b"),
     15, "usage/examples section"),
    ("config", re.compile(r"(?im)^#{1,3}\s*(config|options|settings|api)\b"),
     5, "configuration/API reference"),
    ("contributing", re.compile(r"(?im)^#{1,3}\s*contribut"), 5,
     "contributing section"),
    ("license", re.compile(r"(?im)^#{1,3}\s*licen[cs]e\b|\(c\)|copyright"), 10,
     "license mention"),
    ("badges", re.compile(r"!\[.*?\]\(https?://"), 5, "status badges"),
    ("code_sample", re.compile(r"```"), 10, "fenced code sample"),
    ("links", re.compile(r"\[.*?\]\(https?://"), 5, "external links"),
    ("length", None, 5, "substantive length (>= 40 lines)"),
]


def _run_readme(ctx: Dict[str, Any]) -> WorkReport:
    price = 2.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_README, price, "README health audit")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_README, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    root = target if target.is_dir() else target.parent
    dry = bool(ctx.get("dry_run"))
    candidates = sorted(
        p for p in root.iterdir()
        if p.is_file() and p.name.lower().startswith("readme"))
    if not candidates:
        body = (f"No README file found in `{root}`.\n\n"
                "Recommendation: add a README.md with at least a title, "
                "description, install, and usage section.")
        summary = {"readme_found": False, "score": 0, "target": str(target)}
    else:
        readme = candidates[0]
        text = readme.read_text(encoding="utf-8", errors="replace")
        hits, total, rows = [], 0, []
        for key, rx, weight, label in _README_SECTIONS:
            if key == "length":
                ok = len(text.splitlines()) >= 40
            else:
                ok = bool(rx.search(text)) if rx else False
            hits.append(ok)
            total += weight if ok else 0
            rows.append(f"| {label} | {'yes' if ok else 'no'} | {weight} |")
        missing = [label for (_, _, _, label), ok in
                   zip(_README_SECTIONS, hits) if not ok]
        body = (f"Audited `{readme.name}` ({len(text.splitlines())} lines). "
                f"Health score: **{total}/100**.\n\n"
                "| Check | Found | Weight |\n|---|---|---|\n"
                + "\n".join(rows) + "\n\n"
                + ("Missing: " + ", ".join(missing) + "."
                   if missing else "All checks passed."))
        summary = {"readme_found": True, "file": readme.name, "score": total,
                   "missing": missing, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_README}/{stamp}-{_GID_README}-report.md",
                 f"{_GID_README}/{stamp}-{_GID_README}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_README, stamp,
                                            "README Health Audit", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_README, produced=produced,
        quoted_amount_usd=price,
        notes=f"README health: {summary['score']}/100."
              f"{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# 45 — dependency-hygiene-reporter
# ---------------------------------------------------------------------------
_GID_DEPS = "dependency-hygiene-reporter"

_DEP_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+(?:\[[A-Za-z0-9_,\s]+\])?)\s*"
    r"([=<>!~]+)?\s*([^\s;#]+)?")


def _run_deps(ctx: Dict[str, Any]) -> WorkReport:
    price = 2.5
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_DEPS, price, "Dependency hygiene report")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_DEPS, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    root = target if target.is_dir() else target.parent
    dry = bool(ctx.get("dry_run"))
    req_files = sorted(root.glob("requirements*.txt")) + \
        sorted(root.glob("requirements/*.txt"))
    rows: List[Dict[str, str]] = []
    for rf in req_files:
        for raw in rf.read_text(encoding="utf-8",
                                errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "-", " ")):
                continue
            m = _DEP_LINE.match(line)
            if not m:
                rows.append({"file": rf.name, "spec": line,
                             "status": "unparseable"})
                continue
            name, op, ver = m.group(1), m.group(2), m.group(3)
            if op == "==" and ver:
                status = "pinned"
            elif op in (">=", "~=", ">", "<=", "<", "!=") or not op:
                status = "floating"
            else:
                status = "other"
            rows.append({"file": rf.name, "name": name,
                         "constraint": f"{op or ''}{ver or ''}".strip() or
                         "(none)", "status": status})
    pinned = sum(1 for r in rows if r["status"] == "pinned")
    floating = sum(1 for r in rows if r["status"] == "floating")
    md_rows = "\n".join(
        f"| {r.get('name', r.get('spec', '?'))} "
        f"| {r.get('constraint', '—')} | {r['status']} | {r['file']} |"
        for r in rows)
    body = (f"Found **{len(req_files)}** requirements file(s), "
            f"**{len(rows)}** dependency spec(s): "
            f"**{pinned}** pinned, **{floating}** floating.\n\n"
            "| Package | Constraint | Status | File |\n|---|---|---|---|\n"
            + (md_rows if md_rows else "_no parseable specs_"))
    if floating:
        body += ("\n\nFloating specs make builds non-reproducible; pin with "
                 "`pip freeze` or use `==`.")
    summary = {"requirements_files": [p.name for p in req_files],
               "total": len(rows), "pinned": pinned, "floating": floating,
               "rows": rows, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_DEPS}/{stamp}-{_GID_DEPS}-report.md",
                 f"{_GID_DEPS}/{stamp}-{_GID_DEPS}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_DEPS, stamp,
                                            "Dependency Hygiene Report",
                                            body, summary))
    return WorkReport(
        generator_id=_GID_DEPS, produced=produced,
        quoted_amount_usd=price,
        notes=f"{pinned} pinned / {floating} floating of {len(rows)} specs."
              f"{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# 46 — backup-readiness-auditor
# ---------------------------------------------------------------------------
_GID_BACKUP = "backup-readiness-auditor"
_LARGE_BYTES = 10 * 1024 * 1024  # 10 MiB


def _run_backup(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_BACKUP, price, "Backup readiness audit")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_BACKUP, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    root = target if target.is_dir() else target.parent
    dry = bool(ctx.get("dry_run"))
    large: List[Tuple[str, int]] = []
    total = 0
    nfiles = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                size = p.stat().st_size
            except OSError:
                continue
            nfiles += 1
            total += size
            if size >= _LARGE_BYTES:
                large.append((_rel(root, p), size))
    manifest_hits = [p.name for p in root.iterdir()
                     if p.is_file() and re.search(
                         r"(?i)backup|manifest|snapshot", p.name)]
    large.sort(key=lambda t: -t[1])
    gaps = []
    if large:
        gaps.append(f"{len(large)} file(s) >= 10 MiB with no manifest entry")
    if not manifest_hits:
        gaps.append("no backup/manifest/snapshot file found at tree root")
    score = max(0, 100 - 15 * len(gaps) - 2 * min(len(large), 10))
    lines = [f"- `{name}` — {size / 1048576:.1f} MiB"
             for name, size in large[:25]]
    body = (f"Audited `{root}`: **{nfiles}** file(s), "
            f"**{total / 1048576:.1f} MiB** total. "
            f"Backup-readiness score: **{score}/100**.\n\n"
            f"Manifest-like files at root: "
            f"{', '.join(manifest_hits) if manifest_hits else '_none_'}\n\n"
            "## Large files (>= 10 MiB)\n"
            + ("\n".join(lines) if lines else "_none_") + "\n\n"
            "## Gaps\n"
            + ("\n".join(f"- {g}" for g in gaps) if gaps else "_none found_"))
    summary = {"files": nfiles, "total_bytes": total, "score": score,
               "large_files": [{"path": n, "bytes": s} for n, s in large],
               "manifest_hits": manifest_hits, "gaps": gaps,
               "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_BACKUP}/{stamp}-{_GID_BACKUP}-report.md",
                 f"{_GID_BACKUP}/{stamp}-{_GID_BACKUP}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_BACKUP, stamp,
                                            "Backup Readiness Audit", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_BACKUP, produced=produced,
        quoted_amount_usd=price,
        notes=f"Backup readiness {score}/100, {len(gaps)} gap(s)."
              f"{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# 47 — secrets-surface-reporter (DEFENSIVE — report only, values never stored)
# ---------------------------------------------------------------------------
_GID_SECRETS = "secrets-surface-reporter"

_SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("generic_assignment", re.compile(
        r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|apikey|auth[_-]?token|"
        r"access[_-]?token|client[_-]?secret|db[_-]?pass)\b\s*[:=]\s*\S+")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]{16,}={0,2}")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
]
_SCAN_EXTS = (".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
              ".ini", ".cfg", ".conf", ".env", ".sh", ".xml", ".txt", ".md")


def _run_secrets(ctx: Dict[str, Any]) -> WorkReport:
    price = 4.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_SECRETS, price, "Secrets surface scan")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_SECRETS, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    dry = bool(ctx.get("dry_run"))
    findings: List[Dict[str, Any]] = []
    scanned = 0
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    roots = [target] if target.is_file() else list(
        p for p in _iter_files(target, _SCAN_EXTS, max_bytes=1_000_000))
    for f in roots:
        if any(part in skip_dirs for part in f.parts):
            continue
        scanned += 1
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for kind, rx in _SECRET_PATTERNS:
                m = rx.search(line)
                if m:
                    # NEVER store the matched value — key name + line only.
                    findings.append({
                        "file": _rel(target if target.is_dir()
                                     else target.parent, f),
                        "line": lineno,
                        "pattern": kind,
                        "context": _redact_key_name(line),
                    })
                    break
    lines = [f"- `{fd['file']}:{fd['line']}` — {fd['pattern']} "
             f"({fd['context']})" for fd in findings]
    body = ("**Defensive scan — report only.** No secret values are stored "
            "in this report; only file, line, and pattern type.\n\n"
            f"Scanned **{scanned}** file(s). Potential exposures: "
            f"**{len(findings)}**.\n\n"
            + ("\n".join(lines) if lines else "_none found_")
            + "\n\nRecommended: rotate anything real, move secrets to a "
              "vault/env store, add the files to .gitignore.")
    summary = {"files_scanned": scanned, "findings": len(findings),
               "detail": findings, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_SECRETS}/{stamp}-{_GID_SECRETS}-report.md",
                 f"{_GID_SECRETS}/{stamp}-{_GID_SECRETS}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_SECRETS, stamp,
                                            "Secrets Surface Report", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_SECRETS, produced=produced,
        quoted_amount_usd=price,
        notes=f"Defensive secrets scan: {len(findings)} potential "
              f"exposure(s) in {scanned} file(s); values never stored."
              f"{' (dry run)' if dry else ''}")


def _redact_key_name(line: str) -> str:
    """Keep only the variable/key name left of : or =, never the value."""
    m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*[:=]", line)
    if m:
        return f"key `{m.group(1)}`"
    return "matched pattern"


# ---------------------------------------------------------------------------
# 48 — doc-coverage-reporter
# ---------------------------------------------------------------------------
_GID_DOCS = "doc-coverage-reporter"


def _run_docs(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_DOCS, price, "Doc coverage report")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_DOCS, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    dry = bool(ctx.get("dry_run"))
    files = list(_iter_files(target, (".py",)))
    rows: List[Dict[str, Any]] = []
    total_defs = total_doc = 0
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"),
                             filename=str(f))
        except (SyntaxError, OSError):
            continue
        defs, missing = _doc_defs(tree)
        total_defs += len(defs)
        total_doc += len(defs) - len(missing)
        rel = _rel(target if target.is_dir() else target.parent, f)
        rows.append({"file": rel, "public_defs": len(defs),
                     "undocumented": sorted(missing)})
    cov = round(100 * total_doc / total_defs, 1) if total_defs else 100.0
    md = [f"## `{r['file']}` — "
          f"{r['public_defs'] - len(r['undocumented'])}/{r['public_defs']} documented"
          for r in rows if r["public_defs"]]
    detail = []
    for r in rows:
        if r["undocumented"]:
            detail.append(f"### `{r['file']}`")
            detail.extend(f"- `{n}`" for n in r["undocumented"])
    body = (f"Scanned **{len(files)}** Python file(s): **{total_defs}** public "
            f"definition(s), docstring coverage **{cov}%**.\n\n"
            + ("\n".join(md) if md else "_no public definitions found_")
            + ("\n\n## Undocumented\n" + "\n".join(detail)
               if detail else "\n\nEverything public is documented."))
    summary = {"files_scanned": len(files), "public_defs": total_defs,
               "coverage_pct": cov, "rows": rows, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_DOCS}/{stamp}-{_GID_DOCS}-report.md",
                 f"{_GID_DOCS}/{stamp}-{_GID_DOCS}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_DOCS, stamp,
                                            "Doc Coverage Report", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_DOCS, produced=produced,
        quoted_amount_usd=price,
        notes=f"Doc coverage {cov}% across {total_defs} public def(s)."
              f"{' (dry run)' if dry else ''}")


def _doc_defs(tree: ast.AST) -> Tuple[List[str], List[str]]:
    """Return (all public def names, undocumented public def names)."""
    all_defs: List[str] = []
    missing: List[str] = []

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = child.name
                if name.startswith("_") and name != "__init__":
                    # still recurse into classes for public methods
                    if isinstance(child, ast.ClassDef):
                        visit(child, prefix + name + ".")
                    continue
                qual = prefix + name
                all_defs.append(qual)
                if not ast.get_docstring(child):
                    missing.append(qual)
                visit(child, qual + ".")
            else:
                visit(child, prefix)

    visit(tree)
    return all_defs, missing


# ---------------------------------------------------------------------------
# 49 — todo-debt-collector
# ---------------------------------------------------------------------------
_GID_TODO = "todo-debt-collector"

_DEBT_RX = re.compile(
    r"(TODO|FIXME|XXX|HACK|BUG|DEPRECATED)\b\s*:?\s*(.*)", re.IGNORECASE)
_PRIORITY = {"FIXME": "P1", "BUG": "P1", "XXX": "P1",
             "TODO": "P2", "HACK": "P2", "DEPRECATED": "P3"}
_SCAN_ALL_EXTS = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                  ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".sh", ".md",
                  ".yaml", ".yml", ".toml", ".txt")


def _run_todo(ctx: Dict[str, Any]) -> WorkReport:
    price = 2.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_TODO, price, "TODO debt collection")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_TODO, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    dry = bool(ctx.get("dry_run"))
    items: List[Dict[str, Any]] = []
    scanned = 0
    for f in _iter_files(target, _SCAN_ALL_EXTS, max_bytes=1_000_000):
        if any(part in {".git", "node_modules", "__pycache__"}
               for part in f.parts):
            continue
        scanned += 1
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _DEBT_RX.search(line)
            if m:
                kind = m.group(1).upper()
                items.append({
                    "file": _rel(target if target.is_dir()
                                 else target.parent, f),
                    "line": lineno,
                    "kind": kind,
                    "priority": _PRIORITY.get(kind, "P3"),
                    "note": m.group(2).strip()[:120],
                })
    items.sort(key=lambda i: (i["priority"], i["file"]))
    counts = {}
    for i in items:
        counts[i["priority"]] = counts.get(i["priority"], 0) + 1
    md = [f"- `{i['file']}:{i['line']}` **{i['priority']}** [{i['kind']}] "
          f"{i['note']}" for i in items]
    body = (f"Harvested **{len(items)}** debt marker(s) from **{scanned}** "
            f"file(s): " + ", ".join(f"{k}={v}" for k, v in
                                    sorted(counts.items()))
            + ".\n\nPriority: P1 = fix soon (FIXME/BUG/XXX), "
              "P2 = plan it (TODO/HACK), P3 = note (DEPRECATED).\n\n"
            + ("\n".join(md) if md else "_no debt markers found_"))
    summary = {"files_scanned": scanned, "items": len(items),
               "by_priority": counts, "detail": items, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_TODO}/{stamp}-{_GID_TODO}-report.md",
                 f"{_GID_TODO}/{stamp}-{_GID_TODO}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_TODO, stamp,
                                            "TODO Debt Report", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_TODO, produced=produced,
        quoted_amount_usd=price,
        notes=f"Debt harvest: {len(items)} marker(s) "
              f"({', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'none'})."
              f"{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# 50 — git-hygiene-reporter
# ---------------------------------------------------------------------------
_GID_GIT = "git-hygiene-reporter"


def _run_git(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.5
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_GIT, price, "Git hygiene report")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_GIT, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    root = target if target.is_dir() else target.parent
    dry = bool(ctx.get("dry_run"))
    repo = root if (root / ".git").exists() else None
    if repo is None:
        # walk up a couple levels, cheap heuristic
        for parent in list(root.parents)[:3]:
            if (parent / ".git").exists():
                repo = parent
                break
    if repo is None:
        return WorkReport(
            generator_id=_GID_GIT, produced=[], quoted_amount_usd=price,
            notes=f"No git repository found at or above {root}. "
                  "Point target at a git checkout.")
    log = _git(repo, ["log", "--format=%H|%s|%an|%ad", "--date=short",
                      "-n", "200"])
    branches = _git(repo, ["branch", "--format=%(refname:short)|"
                           "%(committerdate:short)|%(upstream:trackshort)"])
    commits = [c.split("|") for c in log.splitlines() if c.count("|") >= 3]
    weak = []
    for sha, subject, author, date in commits:
        if len(subject.strip()) < 10:
            weak.append((sha[:7], subject, "too short"))
        elif subject.strip().lower().startswith(
                ("wip", "fix", "update", "tmp", "test commit")):
            weak.append((sha[:7], subject, "vague"))
        elif len(subject) > 72:
            weak.append((sha[:7], subject, "over 72 chars"))
    branch_rows = []
    for b in branches.splitlines():
        parts = b.split("|")
        if parts:
            branch_rows.append({"branch": parts[0],
                                "last_commit": parts[1] if len(parts) > 1
                                else "",
                                "tracking": parts[2] if len(parts) > 2
                                else ""})
    score = max(0, 100 - 3 * len(weak) - 2 * max(0, len(branch_rows) - 5))
    md = [f"- `{sha}` “{subj}” — {why}" for sha, subj, why in weak[:30]]
    bm = [f"- `{b['branch']}` (last commit {b['last_commit'] or 'n/a'})"
          for b in branch_rows]
    body = (f"Repo `{repo}`: **{len(commits)}** recent commit(s) analyzed, "
            f"**{len(branch_rows)}** local branch(es). Hygiene score: "
            f"**{score}/100**.\n\n"
            "## Weak commit messages\n"
            + ("\n".join(md) if md else "_none_") + "\n\n"
            "## Branches\n" + ("\n".join(bm) if bm else "_none_"))
    summary = {"repo": str(repo), "target": str(target),
               "commits_analyzed": len(commits),
               "weak_messages": len(weak), "branches": branch_rows,
               "score": score}
    stamp = _utc_stamp()
    produced = ([f"{_GID_GIT}/{stamp}-{_GID_GIT}-report.md",
                 f"{_GID_GIT}/{stamp}-{_GID_GIT}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_GIT, stamp,
                                            "Git Hygiene Report", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_GIT, produced=produced,
        quoted_amount_usd=price,
        notes=f"Git hygiene {score}/100: {len(weak)} weak message(s), "
              f"{len(branch_rows)} branch(es).{' (dry run)' if dry else ''}")


def _git(repo: Path, args: List[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo)] + args, capture_output=True, text=True,
            timeout=30)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------------------
# 51 — license-header-auditor
# ---------------------------------------------------------------------------
_GID_LICENSE = "license-header-auditor"

_LICENSE_RX = [
    ("SPDX identifier", re.compile(r"SPDX-License-Identifier:\s*(\S+)")),
    ("Copyright notice", re.compile(r"(?i)copyright\s*(?:\(c\))?\s*\d{4}")),
    ("License block", re.compile(
        r"(?i)licensed under|MIT License|Apache License|GPL|BSD [23]-Clause|"
        r"All rights reserved")),
]
_CODE_EXTS = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
              ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".sh", ".swift",
              ".kt")


def _run_license(ctx: Dict[str, Any]) -> WorkReport:
    price = 2.5
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_LICENSE, price, "License header audit")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_LICENSE, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    dry = bool(ctx.get("dry_run"))
    rows: List[Dict[str, Any]] = []
    for f in _iter_files(target, _CODE_EXTS, max_bytes=1_000_000):
        if any(part in {".git", "node_modules", "__pycache__", "venv"}
               for part in f.parts):
            continue
        try:
            head = "".join(f.read_text(
                encoding="utf-8", errors="replace").splitlines(True)[:40])
        except OSError:
            continue
        found = []
        spdx = None
        for label, rx in _LICENSE_RX:
            m = rx.search(head)
            if m:
                found.append(label)
                if label == "SPDX identifier":
                    spdx = m.group(1)
        rows.append({"file": _rel(target if target.is_dir()
                                  else target.parent, f),
                     "has_header": bool(found), "signals": found,
                     "spdx": spdx})
    with_header = sum(1 for r in rows if r["has_header"])
    gaps = [r["file"] for r in rows if not r["has_header"]]
    spdx_kinds: Dict[str, int] = {}
    for r in rows:
        if r["spdx"]:
            spdx_kinds[r["spdx"]] = spdx_kinds.get(r["spdx"], 0) + 1
    cov = round(100 * with_header / len(rows), 1) if rows else 100.0
    body = (f"Scanned **{len(rows)}** source file(s): **{with_header}** carry "
            f"a license signal ({cov}%).\n\n"
            "## License signals seen\n"
            + ("\n".join(f"- {k}: {v} file(s)"
                         for k, v in sorted(spdx_kinds.items()))
               if spdx_kinds else "_no SPDX identifiers found_") + "\n\n"
            "## Files missing any license header\n"
            + ("\n".join(f"- `{g}`" for g in gaps[:50])
               + (f"\n- …and {len(gaps) - 50} more" if len(gaps) > 50 else "")
               if gaps else "_none_"))
    summary = {"files_scanned": len(rows), "with_header": with_header,
               "coverage_pct": cov, "spdx_kinds": spdx_kinds,
               "missing": gaps, "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_LICENSE}/{stamp}-{_GID_LICENSE}-report.md",
                 f"{_GID_LICENSE}/{stamp}-{_GID_LICENSE}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_LICENSE, stamp,
                                            "License Header Audit", body,
                                            summary))
    return WorkReport(
        generator_id=_GID_LICENSE, produced=produced,
        quoted_amount_usd=price,
        notes=f"License headers: {with_header}/{len(rows)} files ({cov}%)."
              f"{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# 52 — perf-checklist-generator
# ---------------------------------------------------------------------------
_GID_PERF = "perf-checklist-generator"
_IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg")


def _run_perf(ctx: Dict[str, Any]) -> WorkReport:
    price = 3.0
    target = _target(ctx)
    if target is None:
        return _missing_target_report(
            ctx, _GID_PERF, price, "Static-site performance checklist")
    if not target.exists():
        return WorkReport(
            generator_id=_GID_PERF, produced=[], quoted_amount_usd=price,
            notes=f"Target path does not exist: {target}")
    root = target if target.is_dir() else target.parent
    dry = bool(ctx.get("dry_run"))
    pages = list(_iter_files(root, (".html", ".htm")))
    checks: List[str] = []
    img_total = 0
    img_big: List[Tuple[str, int]] = []
    script_total = 0
    render_blocking = 0
    inline_kb = 0
    for f in pages:
        tree = _parse_html(f)
        if tree is None:
            continue
        rel = _rel(root, f)
        imgs = [a for t, a, _ in tree.tags if t == "img"]
        for attrs in imgs:
            src = (attrs.get("src") or "").strip()
            if not src or src.startswith(("http", "data:")):
                continue
            p = (f.parent / src.split("#")[0].split("?")[0])
            try:
                size = p.stat().st_size if p.exists() else -1
            except OSError:
                size = -1
            img_total += 1
            if size > 200 * 1024:
                img_big.append((f"{rel} -> {src}", size))
        for tag, attrs, line in tree.tags:
            if tag == "script" and attrs.get("src"):
                script_total += 1
                if not (attrs.get("defer") is not None or
                        attrs.get("async") is not None):
                    render_blocking += 1
                    if render_blocking <= 8:
                        checks.append(
                            f"- `{rel}` line {line}: render-blocking script "
                            f"`{attrs['src'][:60]}` (no defer/async)")
            if tag == "style":
                inline_kb += 1
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            try:
                total_bytes += (Path(dirpath) / fn).stat().st_size
            except OSError:
                pass
    items = [
        f"**Pages scanned:** {len(pages)}",
        f"**Total site weight on disk:** {total_bytes / 1048576:.1f} MiB",
        f"**Images referenced:** {img_total} — {len(img_big)} over 200 KB "
        "(compress/resize/convert to WebP)",
        f"**External scripts:** {script_total} — {render_blocking} "
        "render-blocking (add defer/async or move to end of body)",
        f"**Inline <style> blocks:** {inline_kb} (consider extracting to "
        "a cached stylesheet)",
        "**Checklist:** enable gzip/brotli · set long cache headers on "
        "hashed assets · lazy-load below-fold images (loading=lazy) · "
        "preconnect to third-party origins · minify CSS/JS · "
        "serve responsive images (srcset).",
    ]
    big = [f"- `{p}` — {s / 1024:.0f} KB" for p, s in
           sorted(img_big, key=lambda t: -t[1])[:20]]
    body = ("## Static performance checklist\n\n"
            + "\n".join(f"- {i}" for i in items) + "\n\n"
            "## Oversized images\n"
            + ("\n".join(big) if big else "_none over 200 KB_") + "\n\n"
            "## Render-blocking script notes\n"
            + ("\n".join(checks[:8]) if checks else "_none flagged_")
            + "\n\n_Static heuristics only — confirm with a real "
              "Lighthouse/WebPageTest run._")
    summary = {"pages": len(pages), "total_bytes": total_bytes,
               "images": img_total, "oversized_images": len(img_big),
               "external_scripts": script_total,
               "render_blocking": render_blocking,
               "target": str(target)}
    stamp = _utc_stamp()
    produced = ([f"{_GID_PERF}/{stamp}-{_GID_PERF}-report.md",
                 f"{_GID_PERF}/{stamp}-{_GID_PERF}-summary.json"]
                if dry else _write_artifacts(ctx, _GID_PERF, stamp,
                                            "Static-Site Performance Checklist",
                                            body, summary))
    return WorkReport(
        generator_id=_GID_PERF, produced=produced,
        quoted_amount_usd=price,
        notes=f"Perf checklist: {len(pages)} page(s), "
              f"{len(img_big)} oversized image(s), {render_blocking} "
              f"render-blocking script(s).{' (dry run)' if dry else ''}")


# ---------------------------------------------------------------------------
# Registration — slots 41-52
# ---------------------------------------------------------------------------
_SPECS = [
    (41, _GID_SEO, "SEO Basics Scanner",
     "Scans local HTML files for SEO fundamentals: titles, meta "
     "descriptions, heading order, and image alts. Writes a scored report.",
     3.0, _run_seo),
    (42, _GID_A11Y, "Accessibility Spotter",
     "Flags common accessibility issues in local HTML: missing alts, "
     "unlabelled inputs, empty buttons/links, heading skips, missing lang.",
     3.0, _run_a11y),
    (43, _GID_LINKS, "Broken Link Hunter",
     "Finds broken INTERNAL links across local HTML docs: missing files "
     "and dangling #fragment anchors. External URLs are out of scope.",
     3.5, _run_links),
    (44, _GID_README, "README Health Auditor",
     "Scores README completeness for a project directory against a "
     "10-point sections checklist. Writes a scored report.",
     2.0, _run_readme),
    (45, _GID_DEPS, "Dependency Hygiene Reporter",
     "Reports pinned vs floating dependencies from requirements*.txt "
     "files. Flags reproducibility risk.",
     2.5, _run_deps),
    (46, _GID_BACKUP, "Backup Readiness Auditor",
     "Checks a directory for backup gaps: large files, missing manifests, "
     "total footprint. Writes a readiness score.",
     3.0, _run_backup),
    (47, _GID_SECRETS, "Secrets Surface Reporter",
     "DEFENSIVE scan of text/config files for exposed secret patterns "
     "(keys, tokens, assignments). Reports locations only — secret values "
     "are never stored or exfiltrated.",
     4.0, _run_secrets),
    (48, _GID_DOCS, "Doc Coverage Reporter",
     "Reports undocumented public functions/classes/methods in Python "
     "files, with per-file and overall docstring coverage.",
     3.0, _run_docs),
    (49, _GID_TODO, "TODO Debt Collector",
     "Harvests TODO/FIXME/HACK/XXX/BUG markers into a prioritized "
     "(P1/P2/P3) technical-debt report.",
     2.0, _run_todo),
    (50, _GID_GIT, "Git Hygiene Reporter",
     "Branch/commit hygiene from git history: weak message detection, "
     "branch inventory, and a hygiene score.",
     3.5, _run_git),
    (51, _GID_LICENSE, "License Header Auditor",
     "Inventories license headers across a project (SPDX, copyright, "
     "license blocks) and lists files with gaps.",
     2.5, _run_license),
    (52, _GID_PERF, "Static-Site Perf Checklist",
     "Static performance checklist for a static-site directory: image "
     "sizes, script counts, render-blocking notes, and total weight.",
     3.0, _run_perf),
]

for _slot, _gid, _name, _desc, _price, _fn in _SPECS:
    register(
        Generator(id=_gid, name=_name, kind=_KIND, description=_desc,
                  version="1.0.0", entry_price_usd=_price, run=_fn),
        slot=_slot,
    )
del _slot, _gid, _name, _desc, _price, _fn
