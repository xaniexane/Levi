"""One-command full export — the thing GitHub refuses to ship.

``export_repo()`` dumps EVERYTHING about a repo into a documented open
directory (format ``forge-export-v1``, spec in docs/FORGE.md):

- ``repo.bundle`` — every ref, via ``git bundle`` (stock git reads it back)
- ``issues.jsonl`` / ``prs.jsonl`` — the full discussion record
- ``stars.json`` — portable reputation (stars travel with the repo)
- ``ci/`` — pipeline definition, run records, and every step log
- ``contrib.json`` — contribution graph data (commits per day per author)
- ``meta.json`` + ``FORGE-EXPORT.md`` manifest + ``SHA256SUMS``

``import_repo()`` verifies the checksums and rebuilds an identical Forge
repo from the directory. Reputation is portable: leave anytime, take it
all with you, come back whenever.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import ci as _ci
from . import issues as _issues
from . import prs as _prs
from . import stars as _stars
from .gitx import GitError, run_git
from .home import forge_home, validate_name
from .jsonl import read_jsonl, write_json
from .repos import create_repo, repo_dir, repo_exists

FORMAT = "forge-export-v1"


def contrib(home, name):
    """Contribution graph: [{'date', 'author', 'commits'}, ...] from git log."""
    name = validate_name(name)
    if not repo_exists(home, name):
        raise GitError("no such repo: %r" % name)
    out = run_git(
        ["log", "--all", "--format=%an%x00%ad", "--date=short"],
        cwd=repo_dir(home, name),
        check=False,
    ).stdout.decode("utf-8", "replace")
    counts = {}
    for line in out.splitlines():
        if "\x00" not in line:
            continue
        author, date = line.split("\x00", 1)
        counts[(date.strip(), author.strip())] = counts.get((date.strip(), author.strip()), 0) + 1
    return [
        {"date": d, "author": a, "commits": n}
        for (d, a), n in sorted(counts.items())
    ]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def export_repo(home, name, dest) -> Path:
    """Export everything into ``dest`` (created fresh; must not exist)."""
    name = validate_name(name)
    if not repo_exists(home, name):
        raise GitError("no such repo: %r" % name)
    dest = Path(dest).expanduser()
    if dest.exists():
        raise GitError("export destination already exists: %s" % dest)
    dest.mkdir(parents=True)

    meta = {"format": FORMAT, "name": name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": "LEVI Forge"}

    # 1. git bundle — every ref, stock-git readable. An empty repo (no
    # commits yet) has nothing to bundle; record that honestly instead.
    bundle = dest / "repo.bundle"
    bundle_proc = run_git(["bundle", "create", str(bundle), "--all"],
                          cwd=repo_dir(home, name), check=False)
    has_history = bundle_proc.returncode == 0
    if not has_history and bundle.is_file():
        bundle.unlink()
    meta["has_history"] = has_history

    # 2/3. issues + PRs
    shutil.copyfile(_issues._path(home, name), dest / "issues.jsonl") \
        if _issues._path(home, name).is_file() else (dest / "issues.jsonl").write_text("")
    shutil.copyfile(_prs._path(home, name), dest / "prs.jsonl") \
        if _prs._path(home, name).is_file() else (dest / "prs.jsonl").write_text("")

    # 4. stars (portable reputation)
    star_rec = _stars.starred(home).get(name)
    write_json(dest / "stars.json", {"name": name, "starred": bool(star_rec),
                                     "record": star_rec})

    # 5. CI: pipeline + run records + logs
    ci_dest = dest / "ci"
    pipe_src = _ci.pipeline_path(home, name)
    if pipe_src.is_file():
        ci_dest.mkdir(exist_ok=True)
        shutil.copyfile(pipe_src, ci_dest / "pipeline.json")
    runs_src = _ci.runs_path(home, name)
    if runs_src.is_file():
        ci_dest.mkdir(exist_ok=True)
        shutil.copyfile(runs_src, ci_dest / "runs.jsonl")
    logs_src = forge_home(home) / "ci" / name / "runs"
    if logs_src.is_dir():
        shutil.copytree(logs_src, ci_dest / "logs", dirs_exist_ok=True)

    # 6. contribution graph + meta
    write_json(dest / "contrib.json", contrib(home, name))
    write_json(dest / "meta.json", meta)

    # 7. checksums + human-readable manifest
    files = sorted(
        str(p.relative_to(dest))
        for p in dest.rglob("*")
        if p.is_file()
    )
    sums = {f: _sha256(dest / f) for f in files}
    with open(dest / "SHA256SUMS", "w", encoding="utf-8") as fh:
        for f in files:
            fh.write("%s  %s\n" % (sums[f], f))
    manifest = _manifest_text(meta, sums)
    (dest / "FORGE-EXPORT.md").write_text(manifest, encoding="utf-8")
    return dest


def _manifest_text(meta: dict, sums: dict) -> str:
    lines = [
        "# LEVI Forge export — %s" % meta["name"],
        "",
        "Format: `%s` (spec: LEVI repo `docs/FORGE.md`, section "
        "\"Export format\")." % FORMAT,
        "Exported: %s" % meta["exported_at"],
        "",
        "## What is in this directory",
        "",
        "- `repo.bundle` — complete git history, all refs (`git clone repo.bundle`)"
        + (" (absent: repo has no commits yet)" if not meta.get("has_history") else ""),
        "- `issues.jsonl` — every issue, one JSON object per line",
        "- `prs.jsonl` — every pull request, one JSON object per line",
        "- `stars.json` — star/favorite record (portable reputation)",
        "- `ci/pipeline.json` — CI pipeline definition",
        "- `ci/runs.jsonl` — CI run records",
        "- `ci/logs/` — every CI step log",
        "- `contrib.json` — contribution graph (commits per day per author)",
        "- `meta.json` — export metadata",
        "",
        "## Integrity",
        "",
        "`SHA256SUMS` lists the SHA-256 of every file above. "
        "`levi forge import` verifies these before rebuilding.",
        "",
        "## Files",
        "",
    ]
    for f in sorted(sums):
        lines.append("- `%s` — sha256 `%s`" % (f, sums[f]))
    lines.append("")
    return "\n".join(lines)


def import_repo(home, src, name: "str | None" = None) -> dict:
    """Verify checksums, then rebuild a Forge repo from an export dir."""
    src = Path(src).expanduser()
    meta_path = src / "meta.json"
    if not meta_path.is_file() or not (src / "FORGE-EXPORT.md").is_file():
        raise GitError("not a forge export directory: %s" % src)
    import json

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("format") != FORMAT:
        raise GitError("unsupported export format: %r" % meta.get("format"))
    name = validate_name(name or meta.get("name") or "")
    if repo_exists(home, name):
        raise GitError(
            "repo %r already exists in this forge — refusing to overwrite" % name
        )

    # Verify integrity BEFORE touching the forge.
    sums_path = src / "SHA256SUMS"
    if not sums_path.is_file():
        raise GitError("export is missing SHA256SUMS — refusing to import")
    expected = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, _, fname = line.partition("  ")
        if digest and fname:
            expected[fname.strip()] = digest.strip()
    for fname, digest in expected.items():
        p = src / fname
        if not p.is_file() or _sha256(p) != digest:
            raise GitError("checksum mismatch for %s — export is corrupt" % fname)

    # Rebuild: bare repo from the bundle, then the JSONL sidecars.
    create_repo(home, name, description="imported from forge export")
    bare = repo_dir(home, name)
    bundle = src / "repo.bundle"
    if bundle.is_file():
        run_git(["fetch", str(bundle), "+refs/*:refs/*"], cwd=bare)
        # bundle may define HEAD; point the bare repo at the default branch
        run_git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=bare, check=False)
        # ...but honor whatever branch the bundle actually has:
        heads = run_git(
            ["for-each-ref", "--format=%(refname:short)", "refs/heads/"], cwd=bare
        ).stdout.decode().split()
        if heads:
            preferred = "main" if "main" in heads else heads[0]
            run_git(["symbolic-ref", "HEAD", "refs/heads/" + preferred], cwd=bare)

    root = forge_home(home)
    for fname in ("issues.jsonl", "prs.jsonl"):
        srcf = src / fname
        if srcf.is_file() and srcf.stat().st_size:
            dst = (root / ("issues" if fname.startswith("issues") else "prs")
                   / (name + ".jsonl"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(srcf, dst)
            os.chmod(dst, 0o600)

    star_data = {}
    try:
        star_data = json.loads((src / "stars.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if star_data.get("starred"):
        _stars.star(home, name)

    ci_src = src / "ci"
    if ci_src.is_dir():
        ci_dst = root / "ci" / name
        shutil.copytree(ci_src, ci_dst, dirs_exist_ok=True)

    return {"name": name, "imported_from": str(src), "format": FORMAT}
