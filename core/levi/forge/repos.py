"""Repository management: bare repos under ``<forge>/repos/<name>.git``.

Repos are plain bare git repositories. Forge adds nothing proprietary to
the format — that is the portability strategy. Any repo can be cloned with
stock git over the Forge smart-HTTP server (or copied straight off disk).
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .gitx import GitError, run_git
from .home import ensure_home, forge_home, validate_name


def repo_dir(home, name) -> Path:
    return forge_home(home) / "repos" / (validate_name(name) + ".git")


def list_repos(home=None):
    """Return [{'name', 'description', 'created', 'size_bytes'}, ...]."""
    root = ensure_home(home)
    repos = []
    for d in sorted((root / "repos").iterdir()):
        if not d.is_dir() or not d.name.endswith(".git"):
            continue
        meta = _read_meta(d)
        repos.append(
            {
                "name": d.name[: -len(".git")],
                "description": meta.get("description", ""),
                "created": meta.get("created", ""),
                "default_branch": meta.get("default_branch", ""),
                "size_bytes": _dir_size(d),
            }
        )
    return repos


def repo_exists(home, name) -> bool:
    try:
        return repo_dir(home, name).is_dir()
    except ValueError:
        return False


def create_repo(home, name, description: str = "", default_branch: str = "main") -> dict:
    """Create a bare repo. Raises GitError/ValueError on failure/duplicates."""
    name = validate_name(name)
    root = ensure_home(home)
    target = root / "repos" / (name + ".git")
    if target.exists():
        raise GitError("repo %r already exists" % name)
    run_git(["init", "--bare", "-b", default_branch, str(target)])
    # Stock `git push` over our smart-HTTP server needs this on the server side.
    run_git(["config", "http.receivepack", "true"], cwd=target)
    _write_meta(target, {
        "name": name,
        "description": description,
        "created": datetime.now(timezone.utc).isoformat(),
        "default_branch": default_branch,
    })
    return {"name": name, "path": str(target), "default_branch": default_branch}


def delete_repo(home, name) -> None:
    """Permanently delete a repo AND its forge metadata. No undo."""
    name = validate_name(name)
    root = forge_home(home)
    target = root / "repos" / (name + ".git")
    if not target.is_dir():
        raise GitError("no such repo: %r" % name)
    shutil.rmtree(target)
    # Companion metadata leaves with the repo — forge never orphans your data.
    for f in (
        root / "issues" / (name + ".jsonl"),
        root / "prs" / (name + ".jsonl"),
    ):
        try:
            f.unlink()
        except OSError:
            pass
    for d in (root / "ci" / name,):
        if d.is_dir():
            shutil.rmtree(d)


def _meta_path(repo_path: Path) -> Path:
    return repo_path / "forge-meta.json"


def _read_meta(repo_path: Path) -> dict:
    import json

    try:
        return json.loads(_meta_path(repo_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_meta(repo_path: Path, meta: dict) -> None:
    import json
    import tempfile

    tmp = tempfile.NamedTemporaryFile(
        "w", dir=str(repo_path), prefix=".meta-", delete=False, encoding="utf-8"
    )
    try:
        json.dump(meta, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        os.replace(tmp.name, str(_meta_path(repo_path)))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total
